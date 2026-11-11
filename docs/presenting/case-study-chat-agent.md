# Case study: adding a chat agent to a small production-style AWS app

**Purpose** A worked example for the talk. It shows the options at each decision point, how each one fits this problem and its constraints, what was chosen, and what would change at production scale.
**Status** Written from the decisions in [ADR-014](../architecture/ADRs/ADR-014-chat-agent-facade-on-agentcore.md) and [plan 04](../implementation/04-chat-agent-facade.md). Nothing is deployed to production. Items marked *verify* depend on AWS facts not yet checked against current docs.
**Date** 2026-11-11

## 1. The starting point

The app is a personal expense tracker on AWS, built in earlier steps:

- A React SPA on S3 behind CloudFront.
- A FastAPI backend on ECS Fargate, storing data in DynamoDB (single table, ADR-003).
- Cognito for sign-in, with tenant isolation by `USER#<sub>` keys (ADR-009).
- A receipt pipeline on Lambda: convert the image, then parse it with Claude into a draft (ADR-012, ADR-013). The draft is reviewed by the user before it is saved (ADR-010).

The question: **how should a chat interface be added so that it works with the same data and the same rules as the existing UI, and so that the model cannot harm data?**

## 2. The constraints

These drive every decision below. A design that ignores them is not "better", only wrong for this case.

| Constraint | Why it matters |
|---|---|
| Personal budget | Idle cost must be near zero. Nothing hourly that is not already there. |
| One owner, many users possible | Tenant isolation is a security property, not a feature. |
| Financial data | A wrong write is worse than a slow answer. Every write needs a human decision. |
| Learning and talk value | The design should show production patterns, but stay small enough to build and explain. |
| Demo risk | The demo may be live. A flaky model answer must not corrupt data on stage. |

## 3. Decision points

Each decision lists the options that were considered, how they fit the constraints, and the choice. The rejected options are as useful as the chosen one in a talk.

### D1. Where does the chat logic run?

| Option | Fit |
|---|---|
| A. `/chat` route inside the existing Fargate backend | Almost no new infrastructure, but the chat becomes a feature of the app, not a separate facade. Little to show. |
| B. Container Lambda with a Function URL and a hand-built tool loop | Fits the existing Lambda patterns. Streaming, JWT checks and sessions are all hand-built. Python response streaming on Lambda needs the Lambda Web Adapter. |
| C. AgentCore Runtime with a Strands agent | Managed sessions, streaming, JWT validation before the code runs, and tracing. New service to learn, and the Terraform provider needs the v6 major version. |

**Choice: C.** The managed runtime removes plumbing that would otherwise be built by hand (ADR-014). The provider upgrade is a separate, known cost.

### D2. Does the agent read the database directly or call the API?

| Option | Fit |
|---|---|
| Agent reads and writes DynamoDB | Duplicates the key layout, tenant isolation and validation. Any table change must be made in two places. |
| Agent reads DynamoDB, writes via the API | Less risk, but the agent must still build keys and know the schema. Needs `Query` permissions that the least-privilege role (ADR-005) does not grant. |
| Agent calls the existing REST API with the user's token | One set of rules. The backend already scopes data by the token's `sub`. |

**Choice: the REST API.** The business rules and the tenant boundary stay in one place. The compare-the-interfaces claim only holds if both interfaces follow the same rules (ADR-014).

### D3. Who may write data?

| Option | Fit |
|---|---|
| Agent has write tools (`create`, `update`, `delete`) | Fastest demo. Every model mistake or injected instruction becomes a data change. No human in the loop. |
| Agent drafts, the user confirms in the UI | The browser makes the write after a click. The model never writes. Matches the existing draft-review flow. |
| Agent writes only low-risk changes, with undo | A sensible later step. Needs an undo design first. |

**Choice: draft and confirm.** The agent has five read or draft tools. The user clicks Save, which calls `POST /expenses` with an idempotency key. This is the human-approval practice in the Agentic AI Lens (AGENTSEC04-BP02).

### D4. How does the agent get the user's identity?

| Option | Fit |
|---|---|
| Agent uses its own IAM role to read data | The agent could read any user's data. Breaks tenant isolation. |
| Pass the user's Cognito access token through to the tools | Simple, and the backend already checks it. The token is visible to the agent process. |
| Token exchange or signed user claims (the Lens's stricter form, AGENTSEC03) | Stronger: the agent never holds the user's credentials. More moving parts, and AgentCore Gateway cannot forward the user token to an OpenAPI target without a token exchange. |

**Choice: forward the token.** It is the simple version. The case study says so openly and names the stronger form as the next step.

### D5. Which model, and from which provider?

| Option | Fit |
|---|---|
| Claude on Bedrock | Best fit for the eval set. Needed the Anthropic use-case form, which was not submitted, so every call was denied. |
| Claude on the Anthropic API | Already used by the receipt Lambda. A separate key and a separate spend to watch. |
| Amazon Nova Pro on Bedrock (EU profile) | No third-party agreement. Passed 20 of 20 evals after a fix for `<thinking>` text leaking into replies. Price estimate unverified (*verify*). |
| Amazon Nova 2 Lite | Cheaper. Passed 14 of 20 on the stricter checks, mangling a receipt id and answering in the wrong language. |

**Choice: Nova Pro for now.** It works today on this account, and the evals decided it, not a preference. The model is one config value, so switching is cheap once the Anthropic form is approved. *Verify* the Nova Pro lifecycle status in eu-west-1 before the talk.

### D6. Where do the tools live?

| Option | Fit |
|---|---|
| Plain Python functions inside the agent that call the REST API | Least moving parts. The docstring is the tool prompt. The backend stays unchanged. |
| Generated tools from the FastAPI OpenAPI spec | Less code, but also exposes write and delete routes, with weak auto-generated descriptions. |
| A separate MCP server | Reusable by other clients. Adds a service and the token problem before there is a working chat. |
| A purpose-built `/agent-tools` router in the backend | Model-friendly responses without touching UI routes. Only worth it if response shaping grows. |

**Choice: plain functions in the agent,** with an aggregation endpoint so the model never does arithmetic. MCP is a "what's next" slide.

### D7. How does the browser reach the chat?

| Option | Fit |
|---|---|
| Chat through the HTTP API | One front door for throttling and logs. Streaming through the HTTP API is *unverified*. |
| Direct to the AgentCore Runtime endpoint, with the runtime's own JWT check | One hop, streamed reply. The endpoint is public, so the token check is the only gate. |
| Separate chat app with its own login | Second login, hosting and CORS setup. Not side by side with the UI. |

**Choice: direct to the runtime.** The browser needs CORS on the runtime endpoint. A preflight check against the managed endpoint worked during testing.

### D8. Where do the cost and safety limits live?

| Option | Fit |
|---|---|
| Only the platform's limits | Not enough. The platform does not know what a turn is worth. |
| Limits in the agent code: prompt length, tool calls, output tokens, turns per session | Deterministic, testable, and visible in the usage log. |
| A daily per-user cap in durable storage | Needed to stop a valid user from running up the bill. Not built yet. |

**Choice: code limits now, daily cap next.** This is a known gap, named in the case study. See section 6.

## 4. What went wrong, and what it taught

These are the real incidents from the build. They make the talk credible, because production is mostly this.

1. **CORS preflight returned 401.** The `$default` route required a token, and browsers send preflight requests without one. Fix: an unauthenticated `OPTIONS /{proxy+}` route. Lesson: test the browser path, not only curl with a token.
2. **Terraform `moved` block conflicted with `-target`.** The deploy script targets one module first. Fix: a `removed` block with `destroy = false`. Lesson: read the plan with the same flags the deploy uses.
3. **Cloud Map resource replacement.** An empty `health_check_custom_config {}` was not stored by the provider, so every apply would have replaced the service. Lesson: a plan that shows an unexpected replacement is a bug, not noise.
4. **Bedrock denied every Claude call.** The account had not submitted the Anthropic use-case form. Lesson: check model access before writing the code that depends on it. The error was clear; the cause was an account step.
5. **Model output leaked `<thinking>` text into the chat.** Fix: the agent strips the tag from the stream, and the evals fail if it leaks. Lesson: evals must check the output the user sees, not just the tool calls.

## 5. Production-grade layer

What makes this more than a demo, and what each piece costs:

| Layer | What it does | Cost or effort |
|---|---|---|
| Limits | Caps prompt length, tool calls, output tokens and turns | Code only |
| Usage log | One line per turn: tokens, tool calls, latency, estimated cost, prompt version | Code only; price constants need checking |
| Eval set | 20 cases, including prompt-injection cases, run against the real model | A few cents per run |
| Injection handling | Tool results are data, not instructions. Tested with a receipt that contains instructions | Prompt and tests |
| Deploy | Image with a unique tag, runtime updated by Terraform, frontend built against the URLs | Part of `deploy.sh` |
| Teardown | Documented commands in the README to stop spend, and to destroy everything | Documentation |

## 6. What is not production yet

Stating these openly is part of the case study:

- **No daily per-user cap.** A valid user can open many sessions and drive up model spend. Planned next.
- **No throttling on the runtime.** The REST API has throttling; the runtime endpoint has none in Terraform.
- **Tokens in the browser.** Stored in `localStorage` by the Cognito SDK. Any XSS bug could steal them. The next step is the Hosted UI with PKCE.
- **Token forwarding, not token exchange.** The agent process sees the user's token. Acceptable for a demo; the Lens recommends the stronger form.
- **Observability.** The usage log is local. CloudWatch metrics and a dashboard are planned. AgentCore tracing is not set up.
- **Cost estimate.** The per-turn price uses a US list price that is not confirmed for the EU (*verify*).
- **Single environment.** No staging. Deploys go straight to the one AWS account.

## 7. What changes at production scale

If this served many users, the decisions that would change:

| Area | Change |
|---|---|
| Throughput | Per-user and global rate limits at the edge, plus a daily spend cap per user |
| Cost | Route simple turns to a cheaper model; cache the system prompt and tool definitions (Claude supports cache points; Nova logs a warning per call) |
| Reliability | Retries with backoff on model errors; a clear degraded mode when the chat is down, while the UI keeps working (AGENTREL06-BP02) |
| Security | Token exchange so the agent never holds the user's token; a second review of tool scopes; guardrails on the model call (see the AI engineering showcase) |
| Data | Idempotency keys on every write path; an audit trail of who confirmed each change |
| Operations | Staging environment; deploys from CI with a pinned image tag; alarms on error rate and daily spend |
| Evals | Run on every pull request, with a quality trend, not only before a deploy |

## 8. How this maps to the talk

| Talk section | Case-study section | Slide |
|---|---|---|
| Why an agent, and where it fits | 1, 2 | Agentic AI overview |
| Options at each decision | 3 | Integration options (middle column) |
| What AWS offers | Section 3, D1 and D5 | AWS offerings |
| What went wrong | 4 | Live demo backup and "lessons" slide |
| What is production-grade | 5 and 6 | Production gaps slide |
| What changes at scale | 7 | Next steps slide |

## 9. Open questions for the talk

- Live demo or recorded? A recorded run is safer if the Anthropic form is still pending.
- Which incident to show live? CORS (quick to explain) or the Bedrock access denial (shows the error path).
- How much of the option tables to show? One table per decision is too many for one talk; pick D2, D3 and D5.
