# Implementation plan 2: login with Amazon Cognito

**Status** Draft, open decisions marked **[DECIDE]**
**Date** 2026-11-08
**Goal** Only signed-in users can use the app, and each user sees only their own expenses and receipts.

```
Frontend --1--> Cognito (sign in) --2--> tokens (JWT)
Frontend --3--> Backend  Authorization: Bearer <token>
Backend  --4--> verify JWT against the user pool's public keys (JWKS)
Backend  --5--> DynamoDB, scoped by the user's id (the token's "sub")
```

## 1. Current state
- The backend has no auth. The ECS security group only allows the deployer's IP (ADR-007) as a stand-in.
- CORS allows only the S3 website origin (`CORS_ORIGINS`).
- Frontend: React + React Router + axios (`frontend/src/api.js`), pages: Dashboard, MonthlyView, AddExpense, UploadReceipt.
- DynamoDB items are global: `pk=EXPENSE#<id>`, GSI `gsi1pk` is the constant `EXPENSES` (ADR-003).

## 2. Constraints that shape the design
1. **Cognito's hosted login (OAuth redirect) requires HTTPS callback URLs**, except `http://localhost`. The frontend is on the S3 website endpoint, which is **HTTP only**, and the backend is plain HTTP on a task IP. Sending tokens over plain HTTP exposes them to anyone on the path.
2. Tokens are JWTs; the backend must verify signature, issuer, expiry, `token_use` and client id itself.
3. Multi-user data needs a new key design and a decision about the existing data.

## 3. Decisions

### [DECIDE] D1. Login flow
| Option | Needs HTTPS | Notes |
|---|---|---|
| A. Hosted UI + authorization code with PKCE | Yes (callback URL) | Least frontend code and the standard OAuth flow. Requires CloudFront in front of S3 (and ideally a TLS endpoint for the API). |
| B. Custom login form + SRP (`amazon-cognito-identity-js` or Amplify Auth) | Works over HTTP, but tokens still travel in the clear | Fits the current setup; more UI code; no redirect. |

Proposed: **B first** to match the current infra, then move to **A** when CloudFront and the load balancer (`TODO.md`) provide HTTPS. Keep the token handling isolated in one module so the switch is small.

### [DECIDE] D2. HTTPS timing
Real security needs TLS on both the site and the API. That means CloudFront for the frontend (free ACM cert for `*.cloudfront.net` works without a domain) and an ALB or CloudFront in front of the API (an ALB needs a domain for a custom cert). Until then the app is a learning setup only; note it in the ADR.

### [DECIDE] D3. Multi-user data model
- Add `user_id` (the Cognito `sub`) to every expense and receipt.
- Change the GSI partition key from the constant `EXPENSES` to `USER#<sub>`. This also removes the hot-partition downside from ADR-003.
- Existing items have the old key: **[DECIDE]** wipe them (simplest, personal data volume) or write a one-off migration that assigns them to your user.
- Every get/update/delete must check the owner; a missing or foreign item returns 404.

### Fixed choices
- User pool with **self-sign-up disabled** (personal app); create users with the CLI or console.
- App client: **no client secret** (a browser app cannot keep one). Access-token validity short (about 1 hour), refresh token longer.
- Backend validates the **access token** (`token_use=access`), reads `sub` from it.
- Email as username, email verification on.

## 4. Work breakdown

### Phase A: Terraform (new `terraform/cognito` module)
- `aws_cognito_user_pool` (email sign-in, password policy, `admin_create_user_config.allow_admin_create_user_only = true`).
- `aws_cognito_user_pool_client` (no secret; flows depend on D1: `ALLOW_USER_SRP_AUTH` + `ALLOW_REFRESH_TOKEN_AUTH`, or code grant with callback/logout URLs).
- If using hosted UI: `aws_cognito_user_pool_domain`.
- Outputs: user pool id, client id, region, JWKS URL (`https://cognito-idp.<region>.amazonaws.com/<pool-id>/.well-known/jwks.json`).
- Pass pool id and client id to the backend as env vars and to the frontend build (`VITE_*`) from `deploy.sh`.

### Phase B: backend
1. FastAPI dependency `get_current_user`: read the `Authorization: Bearer` header, fetch and cache the JWKS, verify signature (RS256), `iss`, `exp`, `token_use == "access"`, `client_id`. Return the `sub`.
2. Apply the dependency to all routers except `/health`.
3. Thread `user_id` through `expense_service` and `receipt_service`; update key construction (D3) and ownership checks.
4. Presigned upload keys become `receipts/<sub>/<receipt_id>.<ext>` ([plan 1](01-receipt-upload-pipeline.md)); the parser reads the owner from the key and writes the same `user_id`.
5. Local dev: either an `AUTH_DISABLED=true` setting that injects a fixed user (never set in AWS), or a dev user pool.
6. Tests: generate an RSA key pair in the test, serve a fake JWKS, sign tokens; cover expired, wrong issuer, wrong audience/client, wrong `token_use`, missing header, and cross-user access (user A cannot read or delete user B's expense).
7. CORS already allows the `Authorization` header (`allow_headers=["*"]`); verify the preflight in the browser.

### Phase C: frontend
1. Auth module: sign in, sign out, current session, refresh; keeps tokens in one place. Memory plus refresh token is safer than `localStorage` against XSS; `localStorage` survives reloads more easily. **[DECIDE]**.
2. Login page and a `ProtectedRoute` wrapper in `App.jsx`; redirect to login when no session.
3. axios request interceptor in `api.js` adds the bearer token; response interceptor handles 401 (refresh once, then sign out).
4. The direct S3 upload must **not** carry the app token (presigned URL only).
5. Sign-out and a visible current user.

### Phase D: security group and rollout
- Once auth works, the backend no longer needs to be limited to one IP, but do not open it before TLS (D2). Keep the allow-list until HTTPS is in place.
- Order: deploy Cognito and backend with auth enforced, create your user, deploy the frontend, test, then wipe or migrate old data (D3).

### Phase E: documentation
- ADR-009 (Cognito, flow choice, token validation, HTTP caveat) and update README and `TODO.md`.

## 5. Test checklist
- No token: 401. Garbage token: 401. Expired token: 401.
- Token from another user pool or client: 401.
- Valid token: 200 and only own data returned.
- User A requests user B's expense id: 404.
- Refresh works; sign-out clears state.
- `/health` stays public (ECS health check and the container check need it).

## 6. Cost and cleanup
- Cognito has a free tier that comfortably covers a personal app; check the current pricing page for the plan you pick, because tiers and limits have changed over time.
- CloudFront/ALB (if added for HTTPS): the ALB is the main recurring cost (about $16-20/month idle); destroy it when not in use.
- Teardown: `terraform destroy` removes the pool and its users (user data is lost).

## 7. Definition of done
Unauthenticated calls are rejected; a created user can sign in on the deployed site, upload a receipt, and sees only their own expenses; a second test user sees none of them; the tests above pass.
