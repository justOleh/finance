# TODO

## Done
- [x] DynamoDB storage and least-privilege backend IAM role
- [x] Backend on ECS Fargate (ECR, ECS, security group limited to my IP)
- [x] Frontend on S3, built against the backend task IP

## Next: receipt upload pipeline
Target flow: frontend -> backend (presigned URL) -> S3 -> SQS -> parser (ECS) -> DynamoDB.

1. [ ] Terraform: S3 receipts bucket (private, block public access, CORS allowing `PUT` from the frontend origin, lifecycle rule for old objects)
2. [ ] Backend: `POST /receipts/upload-url` returns a presigned S3 URL (content type + size limit, short expiry, key like `receipts/<id>.<ext>`)
   - [ ] Add `s3:PutObject` on the receipts bucket to the backend IAM role
3. [ ] Frontend: upload page requests the URL, then `PUT`s the file directly to S3
4. [ ] Terraform: SQS queue + dead-letter queue (`maxReceiveCount` ~3), queue policy allowing S3 to send, S3 `ObjectCreated` notification -> queue (filter on the `receipts/` prefix)
5. [ ] Receipt parser: replace the FastAPI entry point with an SQS long-polling consumer
   - [ ] Download the image from S3, run the model, write the expense item to DynamoDB
   - [ ] Delete the message only after a successful write; make processing idempotent
   - [ ] Task role: `sqs:ReceiveMessage/DeleteMessage`, `s3:GetObject`, DynamoDB write
6. [ ] Terraform + `deploy.sh`: ECR repo, ECS service and image push for the parser (`deploy_parser`)
   - [ ] Check model size vs Fargate CPU/memory limits (no GPU on Fargate); cost can be much higher than the backend
7. [ ] Decide how the frontend learns the result (poll the expenses list, or a status field on the item)
8. [ ] End-to-end test: upload a receipt, see the expense appear
9. [ ] ADR for the upload pipeline (presigned URL, S3 -> SQS direct, DLQ, parser as a queue consumer)

## Then: auth and hardening
- [ ] Frontend: sign-in page
- [ ] Backend: authorization (and tag receipts/expenses with the user)
- [ ] Integrate auth and verify frontend <-> backend end to end
- [ ] Add a load balancer (stable DNS, TLS, health checks) and drop the IP allow-list
- [ ] ECS deployment circuit breaker with rollback; `/health` curl check after `services-stable`
- [ ] `.gitignore`: add `*.tfstate*`

## Cost reminders
- Fargate tasks, ALB and NAT bill while they exist; set `desired_count=0` or destroy when idle.
- SQS and S3 are near-free at this scale; the parser task will be the main new cost.
