# ADR-011: Drop the backend IP allow-list; Cognito is the only access control

**Status** Accepted (supersedes the allow-list part of [ADR-007](ADR-007-backend-on-ecs-fargate-no-alb.md) and the last bullet of [ADR-009](ADR-009-cognito-authentication.md))
**Date** 2026-11-09

## Context
ADR-007 restricted the backend port to one CIDR (the deployer's public IP, detected by `deploy.sh`) and described it as a stand-in for authentication until that existed. ADR-009 added Cognito and kept the allow-list as a second layer. ADR-007 already listed its cost: if the deployer's IP changes the API becomes unreachable until the next deploy, and `deploy.sh` needed an extra `curl` and a Terraform variable (`backend_allowed_cidr`) on every run. The allow-list only existed to compensate for the missing authentication; with authentication and authorization in place it was removed (decision by the owner, 2026-11-09).

## Decision
- Remove `backend_allowed_cidr` (Terraform root and `ecs` module) and the IP detection in `deploy.sh`.
- The security group allows the API port from `0.0.0.0/0`. Access control is the Cognito JWT check on every route except `/` and `/health` (ADR-009).
- The ingress rule keeps its address through a `moved` block (`api[0]` to `api`); the security group itself is replaced because its description changed.

## Consequences
- **+** No dependency on the deployer's IP; the app works from any network and a deploy no longer needs a lookup.
- **+** Simpler Terraform and `deploy.sh`.
- **−** The IP filter was also masking the missing TLS: it limited who could capture traffic. Without it, anyone on the network path (public Wi-Fi, for example) can capture a token and replay it until it expires.
- **−** The API is reachable by anyone on the internet over plain HTTP. Tokens and expense data travel unencrypted (no TLS, see ADR-009), so a network observer can read them and replay an access token until it expires (60 minutes).
- **−** `/docs`, `/` and `/health` are public, and unauthenticated requests still reach the app and cost CPU. There is no rate limiting or WAF.
- **−** Defence in depth is lost: a Cognito or JWT-verification bug is now directly exposed.
- Deploy note: Terraform replaces the backend security group (its description changed) and re-creates its rules, so the first deploy after this change briefly drops connections; the new ingress rule address is kept by a `moved` block.
- Follow-up: TLS (CloudFront or ALB with ACM, TODO "Add load balancer") is now the main missing protection; until then do not store sensitive data.
