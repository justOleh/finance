# ADR-014: Chat agent as a facade over the existing API (AgentCore Runtime, Bedrock, direct HTTP tools)

**Status** Accepted: implemented in code on the `experimental` branch (2026-11-11), **not deployed yet**. Unit tests pass, the agent image builds and runs, `terraform validate` and a read-only `terraform plan` pass. Never run so far: a deploy, a real model call (the eval set), the comparison. See "Implementation notes" at the end for what was verified and what differs from the decisions below. Steps in [plan 04](../../implementation/04-chat-agent-facade.md).
**Date** 2026-11-11

## Context
The app has a React UI that calls a FastAPI backend (ADR-007, ADR-009). The owner wants a second interface, a chat agent, and to compare the two. It is also the demo for a tech talk, "Adding a Chat facade to an existing AWS app", so it must look like a production design without being expensive to build.

What the existing system dictates:
- **The API owns the business rules and the tenant isolation** (`USER#<sub>` keys, ADR-009). An agent that bypasses it would duplicate both.
- **The backend is plain HTTP on a task IP that changes on restart** (ADR-007, ADR-011). An agent running elsewhere needs a stable, TLS address.
- **Writes already go through draft, review, save** (ADR-010, ADR-013). That maps directly onto chat.

Reference: the AWS Well-Architected **Agentic AI Lens** (41 questions, 150 best practices). Practices cited below use its IDs, for example AGENTSEC03-BP02.

## Decision
```
Browser (React, CloudFront + private S3)
  |-- existing pages --> HTTP API (TLS, Cognito JWT authorizer, throttling)
  |                         `- VPC link -> Cloud Map -> Fargate backend (code unchanged)
  `-- Chat page --> AgentCore Runtime (validates the Cognito JWT, streams)
                      |- Strands agent --> Claude on Bedrock
                      `- tools --> the same HTTP API, with the caller's token
```

1. **Facade, not a second backend.** The agent calls the existing REST API. The backend sees an ordinary authenticated request and keeps deciding whose data it is.
2. **Runtime: Amazon Bedrock AgentCore Runtime with a Strands agent**, one container image (arm64, like the Lambdas). Chosen over a `/chat` route in the Fargate backend (no facade to show) and over a Lambda with a Function URL (Python has no native response streaming on managed runtimes, it needs the Lambda Web Adapter).
3. **Model: Claude on Amazon Bedrock**, through the runtime's IAM role. No API key (this also answers the Bedrock question left open in ADR-013 for the chat only; the receipt Lambda stays on the Anthropic API until decided separately). *Unverified:* model availability and pricing in the chosen region.
4. **Identity: forward the caller's token.** AgentCore validates the Cognito JWT before agent code runs; the `Authorization` header is passed to the agent through the runtime's header allowlist. Tools send it on to the API. The model never sees the token and never supplies a user id. This is the simple form of identity propagation. The Lens prefers signed claims without the agent holding the user's credentials (AGENTSEC03); the gap is accepted for the demo and called out in the talk.
5. **Tools are hand-written Python functions inside the agent that call the REST API.** No MCP server, no AgentCore Gateway, no generated-from-OpenAPI tools. Reasons: the agent gets only the surface it needs (least privilege applied to tools, AGENTSEC02-BP01), tools are shaped for a model rather than mirroring routes, responses can be trimmed to save tokens, and token forwarding stays trivial. Gateway cannot forward the user's token to an OpenAPI target (only AgentCore Runtime HTTP targets support passthrough; OpenAPI targets need an OAuth token exchange), which is more than this scope warrants.
6. **The agent has no write tools.** It can read, summarise, and *propose* an expense as a draft. The chat page shows a confirm card, and the user's click makes the `POST /expenses` call from the browser. This keeps a human in the loop for every write (AGENTSEC04-BP02, AGENTREL02-BP05) and means a wrong model answer cannot change data. Receipt upload in chat reuses the presigned POST from the browser; the agent only reads the resulting draft.
7. **Initial tool set** (all read-only or draft-only):

   | Tool | Backed by |
   |---|---|
   | `list_expenses(start_date, end_date, store?)` | `GET /expenses/` |
   | `get_expense(expense_id)` | `GET /expenses/{id}` |
   | `spending_summary(start_date, end_date, group_by)` | new aggregation endpoint, plus `GET /expenses/monthly-summary` |
   | `get_receipt_draft(receipt_id)` | `GET /receipts/{id}` |
   | `propose_expense(date, store, items, total)` | nothing; returns a draft for the UI |

8. **Backend changes the agent needs** (they also improve the UI):
   - An aggregation endpoint (spend by store or by period for a date range), so the model never does arithmetic.
   - Typed expense items instead of `items: list[dict]`, so the tool schema tells the model what an item is.
   - An idempotency key on `POST /expenses`, because clients retry (AGENTREL06-BP04).
9. **Foundation fixes first** (they are prerequisites, and they close the top gaps found in the Well-Architected review):
   - **HTTP API in front of the backend** with the Cognito JWT authorizer, throttling and TLS. A VPC link to a Cloud Map service replaces the changing task IP, with no load balancer. *Unverified:* whether the HTTP API VPC link or Cloud Map add a recurring charge.
   - **CloudFront in front of the frontend bucket**, bucket made private.
   - **Terraform AWS provider upgrade from `~> 5.0` to v6**, done as its own change, because the AgentCore resources need it.
10. **Production-grade layer**, each item a talking point:
    - turn and token caps per request, and a daily cap per user (AGENTCOST07-BP01);
    - token usage and cost logged per turn, with one CloudWatch alarm on daily spend (AGENTCOST05);
    - tool results and receipt text treated as untrusted data in the prompt, with a test that a receipt containing instructions cannot produce a draft (AGENTSEC08-BP01);
    - an eval set of about 20 questions with expected tool calls, run locally before each deploy (AGENTOPS06);
    - if the chat is down the UI still works (AGENTREL06-BP02), which is the point of a facade.
11. **Comparison:** six fixed tasks run through the UI and the chat, recording time, clicks or turns, cost and errors. Expected result: chat wins on ad-hoc questions and quick entry, the UI wins on browsing and bulk edits.

### Left out on purpose
MCP and AgentCore Gateway, long-term memory, multi-agent setups, knowledge bases and vector stores, Bedrock Guardrails beyond a mention, and any agent-side write. Each is a "what's next" slide.

## Consequences
- **+** One source of truth for rules and tenant isolation; the backend code does not change for the agent.
- **+** No API key for chat, no idle compute for the agent; cost is per use.
- **+** Writes cannot happen without a click, so a live demo cannot corrupt data.
- **+** The foundation work (TLS, stable address, private bucket, idempotent writes, typed schemas) fixes real gaps listed in ADR-007, ADR-009 and ADR-011, not just demo needs.
- **−** More moving parts: HTTP API, VPC link, Cloud Map, CloudFront, AgentCore Runtime, a container image, and a provider major-version upgrade.
- **−** Forwarding the user's token means the agent process holds a bearer token for the length of a request (see Decision 4).
- **−** Each chat turn costs several model calls, well above one receipt parse. Measure it in phase 3 and set the caps from the measurement.
- **−** The browser-side streaming path (consuming the runtime's streamed response, CORS from CloudFront) is *unverified* and is the first thing to spike.
- **−** AgentCore and the Agentic AI Lens are new and change quickly; names of Terraform arguments and CLI flags must be taken from current docs, not from this ADR.
- Cost and cleanup: HTTP API, CloudFront, AgentCore Runtime and Bedrock bill per use, so idle cost is near zero; Fargate stays the only hourly cost. Set an AWS Budgets alert before phase 3. Everything is in Terraform, so `terraform destroy` removes it; delete the agent's ECR images too.

## Alternatives considered
| Option | Why not |
|---|---|
| `/chat` route inside the Fargate backend, tools call the service layer in-process | Almost no new infrastructure, but it is a feature, not a facade, and gives the talk nothing to show |
| Container Lambda with a Function URL and a hand-written tool loop | Fits the existing Lambda pattern, but streaming, JWT checks and sessions would be hand-built; Python streaming needs the Lambda Web Adapter |
| MCP server in front of the API | Worth it only if other clients should reuse the tools; adds a service to deploy and secure |
| AgentCore Gateway with an OpenAPI target | Cannot pass the user's token through; needs an OAuth token exchange |
| Tools generated from `/openapi.json` | Exposes write and delete routes, and auto-generated names and descriptions are poor tool prompts |
| Bedrock Agents (the older managed service) | Less control over the tool surface and streaming; AgentCore is the current direction |
| **Separate chat app with its own tools that read and write DynamoDB directly** | Bypasses the API, so business rules and tenant isolation are duplicated or lost; see the detailed section below |
| Same, but the agent only *reads* DynamoDB directly | Removes the write risk, not the duplication: key layout, `Decimal` handling, `store_lower` and the GSI sort key still leak into the agent; an LLM building queries needs `Query` shapes the least-privilege role does not allow (no `Scan`, ADR-005) |
| Separate chat UI (own SPA, or Streamlit or Chainlit) calling the same REST API | Sound for the data, but it needs a second login, hosting and CORS setup, and the two interfaces are no longer side by side in one app; the talk is about adding a facade *to* the existing app. Reasonable if the chat must ship independently of the main UI |
| Agent runs in the browser, calling Bedrock with temporary credentials from a Cognito identity pool | No agent server to run, but model access is exposed to the browser, spend caps, logging and prompt-injection controls cannot be enforced server-side, and the system prompt and tool logic are visible to the user |
| Agent with write tools that call `POST`, `PUT` and `DELETE` on its own | Faster in a demo, but every model mistake or injected instruction becomes a data change; no human in the loop (AGENTSEC04-BP02, AGENTREL02-BP05). Revisit later for low-risk writes only, with undo |
| Text-to-query: the model writes DynamoDB queries or SQL (for example over an Athena export) | Non-deterministic, hard to authorise per user, and arithmetic or filters go wrong silently; typed tools with an aggregation endpoint are testable |
| API Gateway WebSocket API plus a Lambda for streaming | Works, but connection handling, auth on connect and session state are hand-built; AgentCore Runtime provides streaming and sessions |
| MCP-first: expose the API as MCP tools and let any client connect | Good second step for reuse; as the first step it adds a service and the token-forwarding problem before there is a working chat |

### Why not a separate chat app that writes to DynamoDB directly
This is the most tempting shortcut: a new service, its own tools (`add_expense`, `list_expenses` as DynamoDB calls), fewer hops and no dependency on the backend. It is a legitimate pattern for a greenfield app. For this one it trades a small convenience for several problems:

- **Business rules are duplicated.** The backend owns the key layout (`USER#<sub>` / `EXPENSE#<id>`, ADR-009), the GSI sort key `<date>#<id>` and its read-modify-write update (ADR-003), `Decimal` conversion, the lowercase `store_lower` attribute, string ids (ADR-004) and validation. A second writer must copy all of it, and any change to the table design has to be made in two places. ADR-010 already accepted this cost once, for the receipt record, as a conscious exception for two small functions. A full agent toolset is not small.
- **Tenant isolation moves into the agent.** Today a wrong `user_id` is impossible to ask for: the key contains the owner and the token decides it. With direct access the agent must build the key itself, so a prompt-injected or hallucinated owner id becomes a cross-user read or write. Containing it needs IAM conditions on the leading key (`dynamodb:LeadingKeys`) with per-user credentials, which is real work, easy to get wrong, and not what the current role (ADR-005) is built for.
- **Least privilege gets worse.** The backend role is limited to six item-level actions and no `Scan`. An agent role that can write the table can write *any* item, including other users' expenses, so a single model mistake has a bigger blast radius than a bug in one API route.
- **No human in the loop.** Direct writes make the model the decision maker for data changes, against the Lens guidance to keep critical actions behind human approval (AGENTSEC04-BP02). Every injected instruction in a receipt or note becomes a potential write.
- **Behaviour diverges between the two interfaces.** The comparison in this ADR is only fair if both interfaces go through the same rules. A chat that can store things the UI would reject, or skip the idempotency key and typed items added in plan 04, invalidates it.
- **Testing and audit are split.** The backend tests (ADR-006) and the API logs describe one writer. A second writer needs its own moto tests, its own audit trail and its own migration whenever the schema changes.
- **It defeats the point of the talk.** The message is "a chat facade over an existing app, reusing what already exists". A parallel write path is the anti-pattern the facade avoids.

When it *would* be right: a new product with no existing API, an analytics or reporting agent that only reads a purpose-built, pre-aggregated table or export, or a bulk-import job that the user starts deliberately and that is reviewed afterwards. Even then, prefer read-only access and a separate, scoped role.

## Open questions
- Bedrock or the Anthropic API for the chat model? (Bedrock assumed; confirm region and model availability.)
- Is the talk demo live? (A recorded backup is assumed.)
- Does the HTTP API VPC link have an hourly charge?
- How does the browser consume the runtime's streamed response, and what does CORS need?
- Is MCP a must-have for the talk, or only a closing slide?

## Implementation notes (2026-11-11)
Verified while building:
- **Browser to AgentCore Runtime works with a plain `fetch`.** A CORS preflight against `https://bedrock-agentcore.eu-west-1.amazonaws.com/runtimes/<arn>/invocations` returns `access-control-allow-origin: *` and allows the `authorization`, `content-type` and session id headers. No proxy is needed. The authenticated call itself is only testable after a deploy.
- **Model:** the inference profile `eu.anthropic.claude-sonnet-5-5` exists in `eu-west-1` (`aws bedrock list-inference-profiles`). It is the default of `chat_model_id`. Whether the account may invoke it is not tested.
- **Terraform:** provider `~> 6.0` has `aws_bedrockagentcore_agent_runtime` with `authorizer_configuration.custom_jwt_authorizer` (`discovery_url`, `allowed_clients`) and `request_header_configuration.request_header_allowlist`. The plan after the upgrade shows no unexpected change to existing resources; the provider only warns that `hash_key` / `range_key` on the DynamoDB table are deprecated in favour of `key_schema`.
- **Streaming format:** the AgentCore SDK turns each yielded object into one `data: {json}` SSE line. The agent yields its own small event vocabulary (`text`, `tool`, `draft`, `done`, `error`), not raw framework events.

Differences from the decisions above:
- **Idempotency** uses an expense id derived from user and key with a conditional write, not a separate key item: one item, no transaction. A repeated request returns the first expense with status 200.
- **Cloud Map** needs a private DNS namespace (SRV records), which is a Route 53 private hosted zone: about $0.50 per month. That is the only new fixed cost.
- **The backend has no public inbound rule any more.** Its security group accepts the API port only from the API Gateway VPC link, and `/docs` is behind the token check.
- **Agent image tags:** a unique tag per build (commit, plus a timestamp for uncommitted changes), passed to Terraform, because the runtime only starts a new version when the image reference changes.
- **Sessions:** history is kept in memory per session id (AgentCore runs one microVM per session) and is bound to the user who started it.

Not built yet:
- The daily cap per user and the CloudWatch alarm on daily spend. Per-request and per-session caps exist; an optional AWS Budgets alert (`budget_alert_email`) covers the account. A per-user counter needs storage the agent deliberately does not have, so it belongs in the backend.
- AgentCore Observability (OpenTelemetry) is not wired; the usage log line is the data source for now.
- The comparison run and ADR-015 with measured numbers.

## After the first deploy (2026-11-11)
- **Deployed and reachable:** CloudFront site, HTTP API, AgentCore runtime. The token is accepted by both the API and the runtime, and the agent's log line shows the caller's user id.
- **Model changed to Amazon Nova Pro** (`eu.amazon.nova-pro-v1:0`, decision of the owner). The account has no access to Anthropic models on Bedrock: the Anthropic use-case form was never submitted, so every Claude call failed with `AccessDeniedException`. Amazon models need no agreement. The eval set passes 20/20 on Nova Pro; Nova 2 Lite did worse (14/20 on the first, stricter version of the checks). "Claude on Bedrock" in decision 3 becomes "a model on Bedrock, chosen by `chat_model_id` and checked with the eval set"; Claude stays an option once the form is submitted.
- **Nova writes its planning inline** as `<thinking>...</thinking>`. The agent strips it from the stream (`ThinkingFilter`), and prompt caching is only requested for Anthropic models.
- **Two mistakes found by deploying, both fixed:** (1) CORS preflight was rejected with 401, because the `$default` route sends OPTIONS through the JWT authorizer; an `OPTIONS /{proxy+}` route without an authorizer fixes it. (2) An empty `health_check_custom_config {}` on the Cloud Map service would have replaced the service on every apply; the block was removed.
- **Still open:** the measured cost per chat turn with real prices (the log estimate uses an unverified list price), the comparison run, and the items under "Not built yet".
