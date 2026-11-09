# TODO

## Done
- [x] DynamoDB storage and least-privilege backend IAM role
- [x] Backend on ECS Fargate (ECR, ECS; the IP allow-list was dropped later, ADR-011)
- [x] Frontend on S3, built against the backend task IP

## Next: receipt upload pipeline
Target flow: frontend -> backend (presigned URL) -> S3 -> SQS -> parser (ECS) -> DynamoDB.
Status 2026-11-09: the whole pipeline is built with a **dummy engine** (ADR-010); items below marked done are in the code, not yet verified on AWS until the first deploy.

1. [x] Terraform: S3 receipts bucket (private, block public access, CORS allowing `POST` from the frontend origin)
   - [ ] Lifecycle rule for old objects
2. [x] Backend: `POST /receipts/upload-url` returns a presigned S3 POST (content type + size limit, 5 min expiry, key `receipts/<sub>/<id>.<ext>`) and `GET /receipts/{id}`
   - [x] `s3:PutObject` on `receipts/*` added to the backend IAM role
3. [x] Frontend: upload page requests the URL, `POST`s the file directly to S3, then polls
4. [x] Terraform: SQS queue + dead-letter queue (`maxReceiveCount` ~3), queue policy allowing S3 to send, S3 `ObjectCreated` notification -> queue (filter on the `receipts/` prefix)
5. [x] Receipt parser: SQS long-polling consumer (`receipt_parser/worker`), dummy engine
   - [x] Download the image from S3, run the engine, write the draft to the receipt record (the worker does not create the expense, ADR-010)
   - [x] Delete the message only after a successful write; idempotent; `FAILED` on the last attempt
   - [x] Task role: `sqs:ReceiveMessage/DeleteMessage`, `s3:GetObject`, `dynamodb:UpdateItem`
   - [ ] Real engine (self-hosted model, weights from S3) replacing `DummyEngine`; HEIC to JPEG conversion
6. [x] Terraform + `deploy.sh`: ECR repo, ECS service and image push for the parser
   - [ ] Check model size vs Fargate CPU/memory limits (no GPU on Fargate); cost can be much higher than the backend
7. [x] Frontend learns the result by polling `GET /receipts/{id}` (status on the receipt record)
8. [ ] End-to-end test: upload a receipt, see the expense appear
9. [x] ADR for the upload pipeline: ADR-010
10. [ ] Remove the old synchronous `/receipts/parse` and `/receipts/upload` endpoints and `RECEIPT_PARSER_URL` once the real engine works
11. [ ] DLQ alarm (or a documented redrive procedure)

## Then: auth and hardening
- [x] Frontend: sign-in page, Backend: JWT authorization, expenses scoped per user (ADR-009; code and tests done)
- [ ] Deploy auth: `terraform apply`, wipe old table items, create the Cognito user, verify end to end
- [x] Tag receipts with the user (receipt keys `receipts/<sub>/...`)
- [x] Drop the IP allow-list (ADR-011)
- [ ] Add a load balancer / CloudFront (stable DNS, **TLS**, health checks): the main missing protection now that the API is public over HTTP
- [ ] ECS deployment circuit breaker with rollback; `/health` curl check after `services-stable`
- [ ] `.gitignore`: add `*.tfstate*`

## Cost reminders
- Fargate tasks, ALB and NAT bill while they exist; set `desired_count=0` or destroy when idle.
- SQS and S3 are near-free at this scale; the parser task will be the main new cost.
