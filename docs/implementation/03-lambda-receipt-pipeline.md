# Implementation plan 3: Lambda receipt pipeline (PNG conversion, parse with Claude)

**Status** Done: deployed to AWS and tested by the owner with a real receipt. Remaining: the ADR-012 accuracy evaluation and the cleanup in phase F. Decisions and reasons: [ADR-013](../architecture/ADRs/ADR-013-lambda-receipt-pipeline-with-png-conversion.md); model choice and evaluation: [ADR-012](../architecture/ADRs/ADR-012-claude-sonnet-for-receipt-parsing.md). This plan replaces the consumer side of [plan 01](01-receipt-upload-pipeline.md) (ADR-010).
**Date** 2026-11-09
**Goal** Any image format uploaded to the receipts bucket is converted to PNG in a second bucket by a Lambda; a second Lambda, fed by SQS, parses the PNG with Claude Sonnet 5.5 and stores the draft on the receipt record. The Fargate worker is gone.

```
Browser --1--> S3 uploads bucket (presigned POST, unchanged)    receipts/<sub>/<id>.<ext>
S3 uploads --2--> Lambda convert-image --3--> S3 converted bucket   receipts/<sub>/<id>.png
S3 converted --4--> SQS queue [+ DLQ]
SQS --5--> Lambda parse-receipt --6--> Anthropic API (Claude Sonnet 5.5)
Lambda parse-receipt --7--> DynamoDB RECEIPT#<id> = PARSED (draft) | FAILED
Browser --8--> Backend GET /receipts/{id} (poll) --> editable draft --> POST /expenses (Save)
```

## 1. Layout (what exists)
```
lambdas/
  pyproject.toml, uv.lock       test environment + ruff config (not shipped)
  conftest.py                   dummy AWS credentials for every test
  convert_image/
    Dockerfile, requirements.txt
    convert_image/{handler,converter}.py
    tests/
  parse_receipt/
    Dockerfile, requirements.txt
    parse_receipt/{handler,processor,engine,claude_engine}.py
    tests/
terraform/convert_lambda, terraform/parse_lambda     one module per function
terraform/storage/s3                                 gained optional expiration_days
deploy.sh                                            builds, pushes and updates both Lambdas
```
Removed: `terraform/worker`, `receipt_parser/worker`, `receipt_parser/Dockerfile.worker`, the parser ECS service and ECR repo `parser`.

## 2. Decisions taken
- **D1 (Bedrock or API): the Anthropic API directly**, key in the `ANTHROPIC_API_KEY` Lambda environment variable set in the console. Terraform sets a placeholder and ignores later changes to that one variable. Bedrock stays the alternative (IAM role instead of a key).
- **D2 (conversion failure): leave the receipt `UPLOADING`**, keep the failed event in the `convert-failures` SQS queue. Marking `FAILED` is a follow-up.
- **D3 (image size): downscale to 2000 px longest side** (`MAX_IMAGE_EDGE`), PNG as requested. Revisit with the evaluation.
- **Packaging: container images for both functions** (native libraries; same arm64 build as the backend), `--provenance=false`, code updated with `aws lambda update-function-code` because the tag is always `:latest`.
- **Defaults**: model `claude-sonnet-5-5`, effort `medium`, parse timeout 120 s, queue visibility timeout 720 s (6x), `maximum_concurrency` 2, converted bucket expires after 30 days, logs 14 days.

## 3. Work breakdown

### Phase A: parse logic (done)
- `ClaudeEngine`: base64 image block, structured outputs with a strict JSON schema, explicit effort, no parameters Sonnet 5.5 rejects, refusal / `max_tokens` / invalid JSON raise, invalid or missing date falls back to today with a note, media type allow-list.
- `handler.py`: SQS batch, `batchItemFailures`, `FAILED` on the last receive, `ENGINE=claude|dummy`.
- Tests: fake Anthropic client (request shape, error paths), moto S3 + DynamoDB for the handler and processor.

### Phase B: convert Lambda (done)
- `converter.py`: `is_ready_png` (copy as is when the file is already a complete PNG, at most 4 MB, within `MAX_IMAGE_EDGE`, no EXIF rotation) and `convert_to_png` (EXIF orientation, alpha flattened onto white, downscale, PNG) and `handler.py` (URL-decoded key, `receipts/<owner>/<id>` layout check, deterministic output key).
- Tests with generated JPEG, HEIC, WebP, rotated, transparent, palette, CMYK and corrupt files; for the copy path: ready PNG, wrong format, too many pixels, too many bytes, rotated, truncated; moto S3 for the handler (a ready PNG arrives byte for byte identical).

### Phase C: Terraform (done, `terraform validate` and a read-only `terraform plan` pass)
- Converted bucket (second entry of `module.receipts_bucket`), `aws_s3_bucket_notification.uploads` (Lambda) and `.converted` (SQS), queue policy for the converted bucket, ECR repos `convert_image` and `parse_receipt`.
- `convert_lambda`: function, role, log group, failures queue, async invoke config, S3 invoke permission.
- `parse_lambda`: function, role, log group, SQS event source mapping.
- Variables `parse_max_concurrency`, `claude_model`, `claude_effort`; `parser_desired_count` removed.

### Phase D: deploy script (done)
- `push_lambda_images` (after the registry step, before `terraform apply`), `deploy_lambdas` (update code, wait, warn if the API key is still the placeholder). `--down` no longer touches the Lambdas.

### Phase E: deploy and verify (to do)
1. `./deploy.sh --env aws` (first run creates the ECR repos, pushes both images, applies Terraform).
2. In the AWS console: Lambda > `...-parse-receipt` > Configuration > Environment variables > set `ANTHROPIC_API_KEY`. Set a spend limit in the Anthropic console.
3. Upload a JPEG and a HEIC from the frontend. Check: the PNG in the converted bucket, both Lambda logs, the `PARSED` record, the review form.
4. Run the ADR-012 evaluation, choose model and effort, change `claude_model` / `claude_effort` if needed.

### Phase E2: result handling (decided)
- Tried: no waiting in the UI, the Lambda creates the expense, an info note and a redirect to the dashboard. Reverted at the owner's request: reviewing and editing the data in the preview before it is saved is preferred, so the ADR-010 flow stays (the Lambda stores a draft, the user's Save creates the expense).
- Kept from that work: a photo with neither items nor a total marks the receipt `FAILED` with a readable message and no retry, and the upload page tells the user to photograph the whole receipt.

### Phase F: cleanup (to do after phase E works)
- Remove the old synchronous `/receipts/parse` and `/receipts/upload` endpoints, `RECEIPT_PARSER_URL` and the legacy `receipt_parser/app` service.
- Decide the open questions in ADR-013 (conversion failure status, Secrets Manager or Bedrock).

## 4. Running the tests
```bash
cd lambdas
uv sync --extra dev
uv run pytest            # 50+ tests, no AWS or network needed
../scripts/ruff-fix.sh lambdas      # from the repo root
```
Container smoke test (no AWS): build with `docker build --platform linux/arm64 --provenance=false lambdas/<function>`, run it with `-p 9000:8080` and `curl -XPOST http://localhost:9000/2015-03-31/functions/function/invocations -d '<event json>'`.

## 5. Failure modes covered or to check on AWS
- PNG upload: copied unchanged when ready; converted when too large, rotated or damaged (unit-tested).
- Corrupt or non-image file: convert fails, retries twice, event lands in the failures queue; receipt stays `UPLOADING` (unit-tested up to the exception).
- Same event twice: PNG overwritten, parse idempotent (unit-tested).
- Rotated phone photo and transparency (unit-tested). Large photo: memory and timeout (check on AWS with a real 12 MP HEIC).
- Photo with no readable items or total (first real test: only the bottom of a long receipt): receipt `FAILED` with a message shown in the UI, no retry (unit-tested).
- Model refusal, truncated or invalid output: engine raises, message retried, `FAILED` after 3 receives, message in the DLQ (unit-tested).
- API key missing or wrong: every parse fails with an authentication error and ends `FAILED` (check on AWS; `deploy.sh` warns).
- Throttling (429) or timeouts: SDK retries once, then the message is retried by SQS (check on AWS).
- Visibility timeout shorter than the function timeout would process messages twice: derived as 6x in Terraform.
- Overlapping notification destinations on one bucket: avoided by design (uploads bucket to Lambda, converted bucket to SQS); verify with `aws s3api get-bucket-notification-configuration`.
- DLQ and `convert-failures` contents: inspect with `aws sqs receive-message --queue-url $(terraform output -raw receipts_dlq_url)` (and `convert_failures_queue_url`).

## 6. Cost and cleanup
- Lambda: inside the free tier at personal scale. S3, SQS, CloudWatch Logs, ECR: cents.
- Claude API: per receipt, measured by the ADR-012 evaluation; `maximum_concurrency` caps bursts.
- Saved: the Fargate parser worker (about $9/month); no NAT gateway needed.
- Teardown: `terraform destroy` removes everything (buckets have `force_destroy` through `deploy.sh`'s `force_destroy_buckets=true`); delete ECR images.

## 7. Definition of done
Upload a HEIC and a JPEG in the deployed frontend; a PNG of each appears in the converted bucket; within a minute the draft appears in the review form with store, date, items and total; a deliberately broken image ends in the failures queue and creates no data; `terraform destroy` removes everything new.
