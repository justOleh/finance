ADR-007: Run the backend on ECS Fargate with a public IP, no load balancer

**Status** Accepted (the IP allow-list was removed by [ADR-011](ADR-011-drop-backend-ip-allow-list.md))
**Date** 2026-11-08

## Context
The backend must run as a container on AWS (the project goal is to learn cloud-native architecture). The frontend is a static site on S3 and calls the API from the browser. Budget is personal, so idle cost matters. An ALB costs roughly $16-20/month even when idle, and a NAT gateway roughly $32/month plus data. The API has no authentication yet.

## Decision
- Run the backend as one ECS Fargate task (0.25 vCPU / 0.5 GB, ARM64 to match images built on Apple Silicon), defined in Terraform modules `ecr` and `ecs`.
- Use the default VPC and its public subnets. The task gets a public IP (`assign_public_ip = true`), which is how it pulls from ECR and reaches DynamoDB and CloudWatch without a NAT gateway.
- No ALB. The security group allows the API port only from one CIDR, the deployer's current public IP (`backend_allowed_cidr`), detected by `deploy.sh`. This stands in for authentication until it exists.
- Two IAM roles: an execution role (ECS pulls the image, writes logs) and the existing backend role from ADR-005 as the task role. Its trust policy gains an `ecs-tasks.amazonaws.com` statement.
- The image is always tagged `:latest`, so Terraform sees no change on redeploys. `deploy.sh` pushes the image, then runs `aws ecs update-service --force-new-deployment` and `aws ecs wait services-stable`. The wait ensures the old task is gone, so the next step reads the new task's IP.
- The task public IP is dynamic. After the backend is stable, `deploy.sh` looks it up (ECS task -> ENI -> EC2 public IP) and builds the frontend with `VITE_BACKEND_URL=http://<ip>:<port>`, then syncs it to S3.
- CORS is no longer `*`. `CORS_ORIGINS` (set by Terraform to the S3 website URL) lists the allowed browser origins. Empty means no cross-origin access, which is right for local docker-compose where nginx proxies same-origin.
- `desired_count` is a variable; `0` stops Fargate billing without destroying anything.
- ECR repositories use `force_delete` and `deploy.sh --down` removes only the frontend and ECS modules, so the registry and DynamoDB data outlive teardown.

## Consequences
- **+** Cheapest way to run a container on AWS: Fargate task cost only, no ALB or NAT.
- **+** Real ECS concepts are exercised: task and execution roles, security groups, container health checks, rolling deployments.
- **+** Restricting the port to one IP and removing wildcard CORS limit exposure of an unauthenticated API.
- **−** The public IP changes on every task restart (crash, deploy, scaling), so the frontend bundle goes stale and must be rebuilt. A restart outside `deploy.sh` breaks the app until the next deploy.
- **−** HTTP only, no TLS. Traffic, including any future tokens, is unencrypted.
- **−** If the deployer's IP changes, the API becomes unreachable until the next deploy updates the security group.
- **−** One task, no zero-downtime guarantee beyond ECS's rolling replace. `services-stable` can wait about 10 minutes and gives little detail on failure.
- **−** `:latest` makes deployments hard to trace and roll back.
- Follow-ups: enable the ECS deployment circuit breaker with rollback; add a `/health` curl check after the wait; replace this setup with an ALB (stable DNS name, health checks, TLS via ACM) once auth is in place. This is on `TODO.md` ("Add load balancer").
- Cost cleanup: `./deploy.sh --env aws --down` removes the ECS service and S3 bucket; ECR (small storage cost) and DynamoDB remain until `terraform destroy` of the full stack.
