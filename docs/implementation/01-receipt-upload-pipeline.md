# Implementation plan 1: receipt upload and parsing pipeline

**Status** Draft, open decisions marked **[DECIDE]**
**Date** 2026-11-08
**Goal** Upload a receipt image from the browser and have the extracted expense appear in the app, without the image passing through the backend.

```
Frontend --1--> Backend (presigned PUT URL) --2--> Frontend
Frontend --3--> S3 receipts bucket (direct PUT)
S3 --4--> SQS queue (ObjectCreated)  [+ DLQ]
Parser worker --5--> poll SQS, GET image from S3, run engine
Parser worker --6--> DynamoDB (update receipt / create expense)
Frontend --7--> Backend (poll status, list expenses)
```

## 1. Current state (what changes)
- `backend/app/api/v1/receipts.py` has two **synchronous** endpoints: `POST /receipts/parse` (draft) and `POST /receipts/upload` (creates the expense). Both receive the file, call the parser over HTTP (`RECEIPT_PARSER_URL`) and store the image on local disk (`receipt_service.persist_receipt_file`).
- `receipt_parser/` is a FastAPI service (`POST /parse_receipt`) with two engines hard-wired in `services/parser.py`: local Qwen3.5-2B (8.5 GB weights, mounted from the host) and OpenAI `gpt-4o-mini`.
- Local `docker-compose` flow keeps working until the cloud flow replaces it. Decide at the end whether to keep the sync endpoints for local dev.

Known issues to fix on the way:
- OpenAI path overwrites the receipt date with today's date.
- `parse_receipt_image` returns `None` on invalid JSON; there is no validation.
- Qwen path leaks temp files (`delete=False`).
- `receipt_parser/pyproject.toml` is a full `pip freeze` (torch, vllm, mlx, ...), and the `Dockerfile` has a broken `RUN apt-get` line.

## 2. Decisions

### [DECIDE] D1. Inference engine
| Engine | Fits | Notes |
|---|---|---|
| Bedrock vision model | Lambda or ECS | No secrets (IAM role), pay per call. Model access must be enabled per account/region; check availability in the chosen region. |
| OpenAI API | Lambda or ECS | Existing code; API key needs Secrets Manager (about $0.40/month). |
| Textract `AnalyzeExpense` | Lambda or ECS | Built for receipts, about a cent per page, less flexible. |
| Qwen 2B local | ECS Fargate only | No GPU on Fargate; needs roughly 8-16 GB RAM; always-on task roughly $80+/month; weights must be baked into the image or fetched from S3. |

**Update 2026-11-08: the owner wants to run a custom model with their own weights.** So the primary engine is self-hosted (Qwen today, any fine-tune later). The engine stays behind the interface, so a hosted API (Bedrock/OpenAI) remains an easy fallback for comparing quality or for local development.

### D2. Compute for the worker (follows from D1)
Self-hosted weights rule out Lambda (10 GB image limit, no GPU). Remaining options:

| Option | GPU | Notes |
|---|---|---|
| ECS Fargate (ARM/x86, CPU) | No | Same module style as the backend. Needs about 8-16 GB RAM; slow per receipt but fine for async processing. Cheapest to start. |
| ECS on EC2 GPU instance (g4dn/g5) | Yes | Fast inference, but the instance bills while it runs (roughly $0.5-1/hour); scale the ASG to 0 when idle. More Terraform (capacity provider, ASG, AMI). |
| SageMaker async inference endpoint | Yes | Managed hosting, can scale to 0, but a different service and API to learn. |

Proposed: start with **ECS Fargate on CPU** using a smaller artifact (bf16 or 4-bit quantized weights, for example GGUF with llama.cpp, or bitsandbytes), and move to a GPU instance only if latency or throughput demands it.

**Delivering the weights** (not mountable from a laptop folder on AWS):
1. Upload weights once to a private S3 bucket (`models/<name>/<version>/`); the worker downloads them to ephemeral storage on startup. Keeps the image small and lets you swap weights without a rebuild; cost is startup time (configure Fargate ephemeral storage above the 20 GB default if needed).
2. Bake them into the image: simplest, but huge images, slow pulls and ECR storage cost ($0.10/GB-month).
3. EFS: shared and persistent, but adds cost and networking.

Proposed: option 1. Model version is configuration (`MODEL_S3_URI`), recorded on each parsed receipt so results are traceable.

The core logic stays one function, `process_message(body) -> None`, called by an SQS long-polling loop (scale on queue depth, or keep `desired_count` at 0/1 by hand to control cost).

### [DECIDE] D3. Receipt record with status
Option A (proposed): the backend creates a receipt record `status=UPLOADING` when it issues the presigned URL; the worker sets `PARSED` (with extracted fields) or `FAILED`. The frontend polls. Failures are visible instead of silently landing in the DLQ.
Option B: only the worker writes, on success. Simpler, but failed parses are invisible.

### Fixed choices
- S3 notifies SQS directly (no EventBridge/SNS needed).
- Worker deletes the message only after a successful DynamoDB write; SQS redelivers otherwise; DLQ after `maxReceiveCount` = 3.
- Idempotency: ids derive from the S3 key, writes use `attribute_not_exists`, so duplicate deliveries are harmless.
- Object key layout: `receipts/<owner>/<receipt_id>.<ext>`. Use `owner = "local"` until auth ([plan 2](02-cognito-authentication.md)) supplies the user id, so no key migration later.

## 3. Work breakdown

### Phase A: parser logic (no AWS needed)
1. `ParsedReceipt` pydantic model (store, date, items, total, raw_text) with validation; invalid output raises.
2. Engine interface `extract(image_bytes, content_type) -> ParsedReceipt`; a fake engine for tests.
3. Reuse existing HEIC to JPEG conversion; fix the date-overwrite and temp-file issues.
4. `process_message(body)`: parse S3 event JSON (skip `s3:TestEvent`; **URL-decode the object key**), download image, call engine, write to DynamoDB.
5. Tests with `moto` (S3, SQS, DynamoDB) and the fake engine, as in the backend.

### Phase B: storage shape
- Parser writes expense items in the backend's DynamoDB layout (ADR-003: `pk=EXPENSE#<id>`, `sk=META`, `gsi1pk`, `gsi1sk`, `store_lower`, `Decimal`; ids per ADR-004).
- **[DECIDE]** share a small module between backend and parser, or duplicate the writer and record it in an ADR. The parser cannot call the backend API (IP-restricted, no auth).
- Add receipt fields: `receipt_s3_key`, `status`, `error` (if D3 = A).

### Phase C: backend
1. `POST /receipts/upload-url`: validate content type and size, create the receipt record (D3 = A), return `{receipt_id, upload_url, fields/headers}`. Prefer a presigned **POST** if a size limit (`content-length-range`) is wanted; presigned **PUT** is simpler.
2. `GET /receipts/{id}`: status plus expense id when parsed.
3. IAM: add `s3:PutObject` on `receipts/*` to the backend role (ADR-005 pattern).
4. Config: `RECEIPTS_BUCKET`, upload URL expiry (for example 5 minutes).

### Phase D: Terraform
- S3 receipts bucket: private, block public access, SSE-S3, **CORS** allowing `PUT`/`POST` from the frontend origin (first thing that breaks otherwise), lifecycle rule for old objects.
- SQS queue + DLQ (`maxReceiveCount` 3), queue policy allowing `s3.amazonaws.com` from the bucket ARN, **visibility timeout greater than the worker timeout**.
- `aws_s3_bucket_notification` on `s3:ObjectCreated:*`, prefix `receipts/`.
- Worker compute (D2) with a **separate least-privilege role**: `sqs:ReceiveMessage/DeleteMessage/ChangeMessageVisibility`, `s3:GetObject` on `receipts/*`, DynamoDB write on the table and index ARNs, plus `s3:GetObject` on the model weights prefix (or the engine permission, for example `bedrock:InvokeModel`, if a hosted API is used as fallback).
- ECR repo and image push in `deploy.sh` (`deploy_parser` is currently a stub). Split dependencies: the worker image should not contain torch/vllm unless D1 = Qwen.

### Phase E: frontend
1. `UploadReceipt.jsx`: request URL, `PUT` the file straight to S3 (do not send the app's auth header to S3), then poll `GET /receipts/{id}` until `PARSED`/`FAILED`.
2. Show the extracted draft or error.

### Phase F: cleanup
- Remove or gate the synchronous `/receipts/parse` and `/receipts/upload` endpoints and `RECEIPT_PARSER_URL` once the cloud flow works.
- Write ADR-008 (upload pipeline: presigned URL, S3 to SQS, DLQ, worker model) and update README status table and `TODO.md`.

## 4. Failure modes to test
- Same message delivered twice (no duplicate expense).
- Model returns invalid JSON (message retried, then DLQ, record `FAILED`).
- Worker crashes mid-processing (visibility timeout expires, retry).
- Upload of a non-image or oversized file.
- Presigned URL expired.
- DLQ has messages: alarm or at least a documented way to inspect and redrive.

## 5. Cost and cleanup
- S3, SQS, DynamoDB: near zero at personal scale.
- Bedrock/OpenAI/Textract: per receipt, small.
- Fargate worker: billed while running; set desired count to 0 when idle. Qwen on CPU is the expensive path.
- Teardown: empty the receipts bucket (`force_destroy`), delete queues, ECR images (storage cost is small but non-zero).

## 6. Definition of done
Upload a receipt in the deployed frontend; within a minute the expense appears; a deliberately broken image ends as `FAILED` and in the DLQ; `terraform destroy` removes everything new.
