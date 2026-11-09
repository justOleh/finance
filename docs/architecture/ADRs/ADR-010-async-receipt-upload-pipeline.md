# ADR-010: Asynchronous receipt pipeline (presigned S3 upload, SQS, parser worker)

**Status** Accepted (pipeline deployed with a dummy engine; the real model comes later). **Partly superseded by [ADR-013](ADR-013-lambda-receipt-pipeline-with-png-conversion.md) (proposed):** the Fargate worker, and the S3-to-SQS notification on the upload bucket, are to be replaced by a convert Lambda, a second bucket and a parse Lambda. The presigned POST, receipt record, key layout, idempotent writes and the `Engine` interface stay.
**Date** 2026-11-09

## Context
Receipts were parsed synchronously: the image went through the backend, which called the parser over HTTP and saved the file on local disk. On ECS that cannot work: the parser is not deployed, the disk is ephemeral (ADR-007) and parser errors were swallowed into an "Unknown / 0.00" expense. The owner wants a self-hosted model later; the infrastructure should exist first. Implements [plan 01](../../implementation/01-receipt-upload-pipeline.md) with the deviations below.

## Decision
```
Browser --1--> Backend POST /receipts/upload-url   (creates RECEIPT#<id> = UPLOADING)
Browser --2--> S3 receipts bucket (presigned POST, size + type enforced by S3)
S3 --3--> SQS queue (ObjectCreated, prefix receipts/)  [+ DLQ after 3 receives]
Parser worker --4--> GET image, run engine, UPDATE RECEIPT#<id> = PARSED | FAILED
Browser --5--> Backend GET /receipts/{id} (poll) --> editable draft --> POST /expenses
```
- **Presigned POST** (not PUT): the policy pins `Content-Type` and `content-length-range` (10 MB), so S3 rejects bad uploads without the backend seeing bytes. Expiry 5 minutes.
- **Receipt record (plan D3 option A)**: same table as expenses, `pk = USER#<sub>`, `sk = RECEIPT#<id>`, no `gsi1*` attributes, so it never appears in expense listings. Statuses `UPLOADING`, `PARSED`, `FAILED`. Another user's receipt id is a 404 (same isolation as ADR-009).
- **Object key** `receipts/<sub>/<id>.<ext>` is the contract between backend and worker: the worker derives owner and id from it and needs nothing else.
- **Deviation from the plan: the worker does not create the expense.** It stores a draft (`result`) on the receipt. The frontend shows the existing editable review form and Save calls `POST /expenses`, so a wrong parse never lands in the user's data unreviewed.
- **Worker** (`receipt_parser/worker`, image `Dockerfile.worker`): a Fargate service in the backend's cluster with no port and no inbound rule. A long-polling loop (`WaitTimeSeconds=20`) calls `process_message`; the message is deleted only after success. Updates use `attribute_exists(pk)`, so an upload without a record fails into the DLQ instead of creating a ghost item, and redelivery is idempotent. On the last attempt (`ApproximateReceiveCount >= MAX_RECEIVE_COUNT`) the receipt is marked `FAILED` and the message goes to the DLQ.
- **Engine interface** `extract(image_bytes, content_type) -> ParsedReceipt`; `DummyEngine` returns fixed data (and proves the image was read). Swapping in a real model changes only `engine.py` and the worker's resources.
- **Least privilege, separate roles**: backend `s3:PutObject` on `receipts/*` only (needed to sign); worker `sqs:Receive/Delete/ChangeVisibility`, `s3:GetObject` on `receipts/*`, `dynamodb:UpdateItem`. The queue policy lets only this bucket in this account send.
- **Writer duplicated, not shared**: backend and worker both know the key layout (`USER#`, `RECEIPT#`). Recorded here instead of building a shared package for two small functions.
- The old synchronous `/receipts/parse` and `/receipts/upload` endpoints are kept for now (the frontend no longer uses them); remove them once the real engine works.

## Consequences
- **+** Failures are visible (`FAILED` + DLQ) instead of silently producing an empty expense; the backend stays stateless and never handles image bytes.
- **+** Every piece (bucket, queue, DLQ, worker, roles) is exercised now, so the model work later is only the engine.
- **−** The worker runs 24/7 (about $9/month for 0.25 vCPU / 0.5 GB ARM64). Set `parser_desired_count = 0` when idle; uploads then wait in the queue.
- **−** HEIC is no longer converted by the backend. The dummy ignores image content; the real engine (or the worker) must convert HEIC to JPEG.
- **−** The browser polls every 2 s for up to 2 minutes; no push notification.
- **−** No lifecycle rule on the receipts bucket yet, and no alarm on the DLQ: inspect it with `aws sqs receive-message --queue-url $(terraform output -raw receipts_dlq_url)`.
- **−** S3 CORS allows only the frontend website origin; local frontend development against the real bucket needs that origin added.
- **−** Backend tests do not cover S3 itself (presigning is local); the S3 to SQS notification and IAM only surface against real AWS.
- Cost cleanup: `./deploy.sh --env aws --down` removes the worker service; the bucket, queues and ECR repository remain until `terraform destroy` of the full stack (the bucket has `force_destroy` through `force_destroy_buckets`).
