ADR-009: Authenticate with Amazon Cognito (custom login form, JWT verified in the backend)

**Status** Accepted
**Date** 2026-11-09

## Context
The API was open to anyone on the allow-listed IP (ADR-007) and all expenses were global. The app needs sign-in, and each user must see only their own data. The frontend is on the S3 website endpoint (HTTP only) and the backend is plain HTTP on a task IP. Cognito's Hosted UI uses an OAuth redirect that requires HTTPS callback URLs, so it is not usable yet.

## Decision
- **Cognito user pool** (`terraform/cognito`): email as username, self-sign-up disabled (users are created by the admin), password minimum 12 characters. **App client** without a secret, flows `USER_SRP_AUTH` and `REFRESH_TOKEN_AUTH`, access token 60 minutes, refresh token 30 days.
- **Login flow:** a custom login page using `amazon-cognito-identity-js` (SRP). All Cognito code lives in `frontend/src/auth.js`, so a later move to the Hosted UI (once CloudFront/ALB give HTTPS) only changes that file. Tokens are kept in `localStorage` (the SDK default): they survive reloads, at the price of being readable by any XSS.
- **Backend:** FastAPI dependency `get_current_user` (`backend/app/core/auth.py`) verifies the `Authorization: Bearer` access token with PyJWT: RS256 signature against the pool's JWKS (cached), `iss`, `exp`, `token_use == "access"`, `client_id`. It returns the `sub`. All routes except `/` and `/health` require it. Missing Cognito config fails closed (500), never open.
- **Local development:** `AUTH_DISABLED=true` (only in `envs/local.env`) makes the backend act as the fixed user `local`; the frontend skips the login when `VITE_COGNITO_*` are empty.
- **Data model:** the owner is part of every key. Item `pk = USER#<sub>`, `sk = EXPENSE#<id>`; GSI `gsi1pk = USER#<sub>`, `gsi1sk = <date>#<id>`. Another user's id is simply "not found" (404), and there is no per-item owner check to forget. This replaces the key layout of ADR-003 and removes its constant-partition downside.
- **Existing data was wiped**, not migrated (personal data, old keys are incompatible).
- The IP allow-list on the security group stays.

## Consequences
- **+** No auth code to run or patch ourselves; passwords never reach our backend; per-request verification needs no call to Cognito.
- **+** Tenant isolation comes from the key design, covered by tests (user A cannot read, update or delete user B's expense).
- **−** There is no TLS yet, so tokens and requests cross the network in clear text. This is a learning setup until CloudFront and a load balancer (TODO) provide HTTPS; do not put real sensitive data in it before then.
- **−** `localStorage` tokens are exposed to XSS; the 60-minute access token limits the damage, and sign-out revokes the refresh token.
- **−** The backend task must reach `cognito-idp.<region>.amazonaws.com` for the JWKS (it has a public IP, so it can).
- **−** Users created by the admin start in `FORCE_CHANGE_PASSWORD`; the login page does not handle that challenge, so set a permanent password when creating the user (see README).
- Cost: Cognito's free tier covers a personal app; no recurring cost added.
