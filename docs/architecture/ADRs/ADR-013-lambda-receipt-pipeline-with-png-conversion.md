# ADR-013: Lambda receipt pipeline: PNG conversion bucket, SQS, Claude parse Lambda

**Status** Accepted: implemented, deployed to AWS and tested by the owner (2026-11-09). A real HEIC went through every stage (converted in 9 s including a 4 s cold start, parsed by Claude, about 34 s end to end). The ADR-012 evaluation on a proper golden set is still to do. Supersedes the Fargate worker part of [ADR-010](ADR-010-async-receipt-upload-pipeline.md) and refines [ADR-012](ADR-012-claude-sonnet-for-receipt-parsing.md). Steps in [plan 03](../../implementation/03-lambda-receipt-pipeline.md).
**Date** 2026-11-09

## Context
ADR-010 built the upload pipeline around an always-on Fargate worker polling SQS, and ADR-012 proposed Claude Sonnet 5.5 as the engine. Three things came out of that discussion:

- Receipts arrive in any format (HEIC from iPhones, JPEG, PNG, ...). ADR-010 left HEIC conversion open, and the model should only ever see one well-defined format.
- The worker costs about $9/month idle, and calling a hosted model from it raised outbound-internet questions (a NAT gateway is about $32/month; a public subnet is the cheap workaround).
- A hosted model call is seconds of network wait per receipt: a good fit for Lambda, a poor fit for a 24/7 container.

Constraint found in the Terraform: `aws_s3_bucket_notification` is authoritative, with **one notification configuration per bucket**, and S3 rejects two destinations that overlap on event type and prefix. The upload bucket's existing SQS notification therefore had to be *moved* to another trigger, not added to.

## Decision
```
Browser --presigned POST--> S3 uploads bucket   receipts/<sub>/<id>.<any ext>
S3 uploads --ObjectCreated--> Lambda convert-image   (any format -> PNG)
Lambda convert-image --PutObject--> S3 converted bucket   receipts/<sub>/<id>.png
S3 converted --ObjectCreated--> SQS queue (+ DLQ)
SQS --event source mapping--> Lambda parse-receipt --Anthropic API (Claude Sonnet 5.5)
Lambda parse-receipt --UpdateItem--> DynamoDB  RECEIPT#<id> = PARSED (draft) | FAILED
Browser --poll--> Backend GET /receipts/{id} --> editable draft --> POST /expenses   (unchanged)
```

- **Two buckets.** The existing receipts bucket stays the upload bucket. A second bucket (`<prefix>-receipts-converted`) holds the PNGs and expires objects after 30 days (the originals stay). Writing to a different bucket than the one that triggers the Lambda rules out the recursive-trigger loop.
- **Same key layout, new extension.** `receipts/<sub>/<id>.<ext>` becomes `receipts/<sub>/<id>.png`; owner and receipt id are still derived from the key (ADR-010 contract).
- **convert-image Lambda** (`lambdas/convert_image`, container image, arm64, 1024 MB, 60 s): **A PNG that is already usable is copied unchanged** (byte for byte, no re-encoding): it must be a complete valid PNG, at most 4 MB (under the model API's image size limit), with the longest side at most `MAX_IMAGE_EDGE`, and without an EXIF rotation. Everything else is converted: Pillow plus `pillow-heif` open the image, apply EXIF orientation, flatten transparency onto white, downscale the longest side to `MAX_IMAGE_EDGE` (default 2000 px, never upscaling) and write a PNG. Triggered directly by S3 (asynchronous invocation, 2 automatic retries); an `aws_lambda_function_event_invoke_config` sends events that still fail to an SQS "failures" queue (14 days) instead of dropping them. The output key is deterministic, so a retry overwrites the same object. The upload Lambda invoke permission is limited by `source_arn` and `source_account`.
- **SQS stays between the converted bucket and the parser** (decision of the owner, 2026-11-09). The existing queue and DLQ are reused; the queue policy and the `aws_s3_bucket_notification` point at the converted bucket. Reasons: retries and redrive to the DLQ, `maximum_concurrency` on the event source mapping as a spend and rate-limit cap for the model call, and a retry with delay on throttling for free. The queue's visibility timeout is derived in Terraform as 6 times the parse Lambda timeout (720 s for 120 s).
- **Review before save stays** (ADR-010; a background flow where the Lambda created the expense and the UI redirected right after the upload was built and tried, and the owner preferred to edit the data in the preview before it is written). The Lambda only stores a draft on the receipt record; the frontend waits, shows the editable form, and the user's Save calls `POST /expenses`.
- **Unreadable photo rule.** If the model finds neither items nor a total, the Lambda marks the receipt `FAILED` with a readable message (shown in the UI) and does **not** retry: the same photo gives the same answer, and each retry costs a model call.
- **parse-receipt Lambda** (`lambdas/parse_receipt`, container image, arm64, 512 MB, 120 s): SQS event source mapping with batch size 1, `ReportBatchItemFailures` and `maximum_concurrency = 2`. It reuses the idempotent `process_message` / `mark_failed` logic from the old worker (conditional `UpdateItem`, `FAILED` on the last attempt detected from `ApproximateReceiveCount`) and the `Engine` protocol; only the entry point changed from a polling loop to a Lambda handler. A failed message is reported back, so SQS redelivers it and finally moves it to the DLQ.
- **Engine: Claude Sonnet 5.5 through the Anthropic API** (decision of the owner, 2026-11-09; Bedrock was the first proposal and stays the alternative). `ClaudeEngine` uses the official `anthropic` SDK with a base64 image block, **structured outputs** (`output_config.format` with a JSON schema, so no fence stripping or regex fallback) and an explicit `output_config.effort` (default `medium`). It sends none of the parameters Sonnet 5.5 rejects (`temperature`, `top_p`, `top_k`, `thinking: disabled`, prefill, forced `tool_choice`), checks `stop_reason` for `refusal` and `max_tokens`, and raises on anything unusable, so SQS retries and the DLQ apply instead of an empty expense being stored. If the receipt shows no valid date the engine uses today's date and says so in `notes`, because the backend response model requires a date. Model id and effort are configuration (`CLAUDE_MODEL`, `CLAUDE_EFFORT`); `ENGINE=dummy` keeps the dummy available for pipeline tests.
- **API key as a Lambda environment variable, set in the console.** Terraform creates the function with the placeholder `set-me-in-the-lambda-console` and `lifecycle { ignore_changes = [environment[0].variables["ANTHROPIC_API_KEY"]] }`, so the real key is never in the repository, in Terraform variables or in the state, and later applies do not overwrite it. `deploy.sh` warns (without printing the key) while the placeholder is still there.
- **No VPC, no NAT.** A Lambda outside a VPC reaches the Anthropic API directly, which removes the outbound-internet problem of the Fargate worker.
- **Fargate worker retired.** Removed: `terraform/worker`, the parser ECS service and the `parser` ECR repository (replaced by `convert_image` and `parse_receipt`), `receipt_parser/Dockerfile.worker`, `receipt_parser/worker/main.py` and the worker steps of `deploy.sh`. `processor.py`, `engine.py` and their tests moved to `lambdas/parse_receipt`. The old synchronous `/receipts/parse` and `/receipts/upload` endpoints and the legacy `receipt_parser/app` service are untouched for now.
- **Both functions are container images, deployed with `deploy.sh`.** Pillow, `pillow-heif` and the Anthropic SDK (pydantic, jiter) have native parts, so a zip built on macOS would not run on Lambda; building the same arm64 images as the backend avoids that. Images are built with `--provenance=false` (Lambda rejects buildx attestation manifests). The tag is always `:latest`, so `deploy.sh` runs `aws lambda update-function-code` and waits for the update.
- **Least privilege, one role per function.** convert-image: `s3:GetObject` on `uploads/receipts/*`, `s3:PutObject` on `converted/receipts/*`, `sqs:SendMessage` to its failures queue, its own log group. parse-receipt: `sqs:ReceiveMessage/DeleteMessage/GetQueueAttributes` on the queue, `s3:GetObject` on `converted/receipts/*`, `dynamodb:UpdateItem` only, its own log group. Log groups keep 14 days.
- **Backend unchanged.** Its upload allow-list (JPEG, PNG, HEIC, HEIF) is enough for now; the converter itself reads anything Pillow reads (WebP, TIFF, ...).

## Consequences
- **+** No idle compute: the Fargate worker (about $9/month) is gone; Lambda, SQS and S3 are near-free at this volume, and the model call is the only real cost (ADR-012).
- **+** The model sees one format and a bounded image size, which lowers tokens and removes the HEIC gap from ADR-010. PNG uploads skip the conversion entirely (faster, and no quality loss or size growth from re-encoding).
- **+** SQS keeps retry, DLQ and a concurrency cap; no always-on process to patch or scale.
- **+** The PNG is persisted for 30 days, so a receipt can be re-parsed with another model or prompt without the original, and the original stays in the uploads bucket.
- **−** More moving parts than one worker (or one Lambda converting in memory): two functions, two buckets, two roles, two images. Chosen on purpose for the separation and for the learning value.
- **−** The API key in a Lambda environment variable is encrypted at rest but readable in the console and by anyone with `lambda:GetFunctionConfiguration`; it is also in the function configuration, not in a secret store. Acceptable for a one-person project; Secrets Manager (about $0.40/month) is the upgrade path.
- **−** Receipt images (personal financial data) are sent to the Anthropic API; check its data-retention terms. Bedrock would keep them inside the AWS relationship.
- **−** A conversion failure never reaches the parser: the receipt stays `UPLOADING` until the frontend's poll times out; the event is kept in the failures queue. Marking it `FAILED` from there is an open question.
- **−** Spend is unbounded except by `maximum_concurrency` and the 10 MB upload limit; set a spend limit in the Anthropic console.
- **−** Not verified against the real Claude API or on AWS yet: unit tests use a fake client, moto and local containers only.
- Cost and cleanup: Lambda free tier (1M requests, 400,000 GB-seconds per month) covers it; the extra bucket, the log groups and two ECR images cost cents. `./deploy.sh --env aws --down` leaves the Lambdas, queues and buckets in place (they cost nothing idle); a full `terraform destroy` removes everything (buckets use `force_destroy`).

## Open questions
- Is `claude-sonnet-5-5` at `medium` effort the right cost/accuracy point? Run the ADR-012 evaluation (golden set, Haiku 5.5 comparison) and change `claude_model` / `claude_effort`.
- Mark the receipt `FAILED` when conversion fails, or rely on the frontend's poll timeout (today it stays `UPLOADING`)?
- Move the key to Secrets Manager, or switch to Bedrock (IAM role instead of a key)?
- Item schema (only `name` and `price` today) and the accuracy bar.
- Remove the old synchronous endpoints, `RECEIPT_PARSER_URL` and the legacy parser service once the pipeline works on AWS.
