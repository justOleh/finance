# AI engineering showcase for the chat agent

**Status** Proposal. Nothing here is implemented yet. Items marked *verify* depend on AWS facts that have not been checked against current docs.
**Date** 2026-11-11
**Context** The chat agent is described in [ADR-014](../architecture/ADRs/ADR-014-chat-agent-facade-on-agentcore.md) and [plan 04](../implementation/04-chat-agent-facade.md). This document covers what to add so the talk shows AI engineering practice, not only how to wire a model to an API.

## Goal

Show that the agent is **measured, constrained and improved with evidence**. Each addition should produce a number before and after, so the talk can show a result rather than a claim.

## What already exists

- Hard limits per request and per session: prompt length, tool calls, output tokens, turns, and a row cap on `list_expenses`.
- One usage log line per turn: tokens, tool calls, latency, estimated cost and the prompt version.
- A 20-case eval set with prompt-injection cases (`agent/evals/cases.json`), run by `agent/evals/run_evals.py`.
- A human confirm step before any write. The agent has no write tools.

The gaps are that these checks are local and manual, nothing blocks unsafe content before the model sees it, and nothing is visualised over time.

## Guardrails

Ranked by value for the talk.

1. **Bedrock Guardrails on the model call.** Content filters, denied topics (for example, no tax or investment advice), and PII masking on input and output. Strands can attach a guardrail to its Bedrock model configuration. *Verify:* Nova Pro support in eu-west-1, the Strands parameter name, and the price per text unit.
2. **Output grounding check.** Every amount in an answer must come from a tool result in the same turn. Extract the amounts from the reply and compare them with the tool outputs in code. This is cheap and deterministic, and it targets the worst failure for a finance app: a wrong total. Bedrock's contextual grounding check is an alternative. *Verify* before relying on it.
3. **Tool-argument validation.** Check date ranges, store-name length and allowed fields in code before a call is made. Reject bad calls with a clear message. Deterministic and easy to test, but less impressive on stage.
4. **Structured injection defence.** Put receipt text and notes in a labelled data block and test that with the existing injection cases. Part of this is already in the prompt.

## Metrics

Ranked by value for the talk.

1. **Quality from evals in CI.** Task success, correct tool chosen, correct arguments and grounded numbers. Run the eval set on every pull request and track the trend. An LLM-as-judge for free-text answers is an optional extra.
2. **Per-turn telemetry as CloudWatch metrics.** Turn the usage log line into embedded metric format. Track p50 and p95 latency, input and output tokens, tool calls per turn, limit hits and guardrail blocks. Build one dashboard.
3. **Cost per successful task**, not cost per call. Divide spend by the number of eval tasks that pass. This is the figure that stays with an audience.
4. **Model comparison.** Run the same evals on Nova Pro and Nova 2 Lite, and later on a Claude model once access is granted. Plot quality against cost and latency. Earlier results: Nova Pro 20/20 after the thinking-text fix; Nova 2 Lite 14/20 on the stricter checks at the time.
5. **Tracing.** AgentCore Observability with OpenTelemetry spans, to show one turn from request through tool calls to the model. Useful, but adds moving parts.

## Recommended set for the talk

Keep it small so each item has a before-and-after number.

- **Guardrail with an injection before-and-after.** Run the injection cases with and without the guardrail and report the block rate.
- **Grounding check with a before-and-after count.** Count the answers that fail the check before and after it is added.
- **Eval in CI with a quality trend.** One chart, with a bar for each pull request.
- **Cost per successful task on one dashboard,** with the Nova Pro and Nova 2 Lite comparison.

Leave out tracing and LLM-as-judge unless time allows.

## Costs and cleanup

- Bedrock Guardrails are billed per text unit. A demo is cheap, but the charge applies to every turn once enabled. Add it to the cost section of ADR-014.
- CloudWatch custom metrics are billed per metric. Keep the set to about 6 to 8 metrics.
- Each eval run makes real model calls, at a few cents per run.
- Cleanup: `terraform destroy -target` for the guardrail and dashboard resources. The existing teardown commands in the README cover the rest.

## Open questions

- Which guardrail features does Nova Pro support in eu-west-1? (verify)
- Is the grounding check better as code or as a managed check? Measure both on the injection and answer sets.
- How many eval cases are enough for the trend chart to be meaningful? Start at 20 and grow the set with each real failure.
- Is the talk live or recorded? A recorded run makes the metrics slide safer.

## Next steps

1. Confirm which items from the recommended set to build.
2. Add a plan entry (plan 05) with one phase per item and its success measure.
3. Build the guardrail and the injection before-and-after first. It is the most visible result and the cheapest to test.