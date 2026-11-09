# ADR-012: Use Claude Sonnet 5.5 as the receipt parsing engine

**Status** Proposed (the owner tested the model manually with the app prompt; evaluation and integration below are not done yet). **Amended by [ADR-013](ADR-013-lambda-receipt-pipeline-with-png-conversion.md) (implemented):** the engine (`lambdas/parse_receipt/parse_receipt/claude_engine.py`) runs in the parse-receipt Lambda and calls the Anthropic API directly. Points 7 to 9 below are replaced: HEIC to PNG conversion is a separate convert-image Lambda, the API key is the `ANTHROPIC_API_KEY` environment variable set in the Lambda console (not in Secrets Manager, not in Terraform), and a Lambda outside a VPC needs no NAT gateway. The model choice, structured output, evaluation plan and cost reasoning still apply; the evaluation itself is not done yet.
**Date** 2026-11-09

## Context
ADR-010 deployed the whole upload pipeline with a `DummyEngine` and left "the real model" open. The TODO assumed a self-hosted model (Qwen, weights from S3). The old synchronous parser also used OpenAI `gpt-4o-mini`. The owner tried `claude-sonnet-5-5` with the existing prompt (`receipt_parser/app/services/parser.py`, `RECEIPT_PROMPT`) and the first results look good, so a hosted Claude model is now a candidate.

What the engine must do: image in, `ParsedReceipt` out (`store`, `date`, `items`, `total`, `raw_text`; see `worker/engine.py`), inside the worker's 0.25 vCPU / 0.5 GB Fargate task. That task cannot run a vision model (no GPU, ADR-010 TODO), so a self-hosted model means a separate, much more expensive compute decision. A hosted API keeps the worker as it is: it only makes an HTTPS call.

## Options
| Option | Pro | Con |
|---|---|---|
| **A. Claude Sonnet 5.5** (`claude-sonnet-5-5`, $2 / $10 per MTok in/out) | Strong on messy photos and mixed languages; native image input; structured output; no infra | Per-receipt cost; receipt images leave AWS; needs a secret and outbound internet |
| **B. Claude Haiku 5.5** (`claude-haiku-5-5`, $0.10 / $0.50) | About 20x cheaper than A | Probably less accurate on crumpled or low-quality receipts; must be measured |
| **C. Same models through Amazon Bedrock** | IAM role instead of an API key; stays in the AWS account and billing; fits the least-privilege model of ADR-005/010 | Different client (`AnthropicBedrockMantle`, model id `anthropic.claude-sonnet-5-5`), partner pricing and feature availability to verify |
| **D. Self-hosted Qwen** | No per-call cost, data stays with us | Needs GPU or a large CPU task, model weights, ops; cost far above the API at personal-use volume |
| **E. Keep OpenAI `gpt-4o-mini`** | Already written | Second vendor, older model |

Rough cost per receipt (**estimate, to be replaced by measured `usage` numbers**): about 1.5-2k input tokens (image plus prompt) and 0.5-1k output tokens. That is on the order of $0.01 for A and under $0.001 for B. At a few hundred receipts a month, the API is cents to a few dollars, below the worker's own fixed cost (about $9/month, ADR-010).

## Decision (proposed)
1. Add a `ClaudeEngine` that implements the existing `Engine` protocol. Nothing else in the worker changes (this is what ADR-010 prepared). Select the engine with an env var (`ENGINE=dummy|claude`) so the dummy stays available for pipeline tests.
2. **Start with Sonnet 5.5, evaluate Haiku 5.5 on the same set** and pick the cheapest model that meets the accuracy bar below. The model id is configuration, not code.
3. Call the API with the official `anthropic` Python SDK, with the image as a base64 `image` content block and the prompt as text.
4. Get JSON through **structured outputs** (`output_config.format` with a JSON schema) instead of "return ONLY valid JSON" plus the regex/fence stripping in `parser.py`. A schema also fixes the current mismatch: the prompt asks for `{name, amount, unit, unit_price, item_price}` but the worker stores `{name, price}`. Decide the item shape once, in the schema, and map it in the engine.
5. Parameters specific to the 5.5 generation: do not send `temperature`, `top_p`, `top_k`, `budget_tokens`, prefill or a forced `tool_choice` (all rejected with 400); thinking is on by default, so set `output_config.effort` explicitly (`low` or `medium` for extraction; measure) and keep `max_tokens` bounded.
6. Handle failures explicitly: check `stop_reason` (`refusal`, `max_tokens`) and raise, so SQS retries and then the DLQ plus `FAILED` status from ADR-010 apply. Do not return an empty receipt.
7. **HEIC to JPEG** moves into the engine (or a helper in the worker), reusing `convert_heic_to_jpeg` logic (`pillow-heif`). Resize large photos before sending: it cuts tokens and cost, and the API has image size limits.
8. **Credentials**: the API key lives in Secrets Manager or SSM Parameter Store (SecureString) and is injected as an ECS task `secret`, never in the image, `.env` or Terraform state in plain text. The worker's task role gets read access to that one secret only. If Bedrock (option C) turns out to be equivalent, prefer it: `bedrock:InvokeModel` on one model replaces the secret entirely.
9. **Network**: the worker now needs outbound HTTPS. Check how its subnet is set up; a NAT gateway (about $32/month) would cost more than everything else, so keep the worker in a public subnet with a public IP (as the backend) or use Bedrock with a VPC endpoint only if the cost is justified.

## How to test it before integrating
1. **Golden set**: 20-30 real receipts (several stores, languages, crumpled/dark photos, one HEIC) with hand-written expected JSON. Keep them out of git if they contain personal data (`receipt_parser/tests/` already holds samples; `.gitignore` the private ones).
2. **Eval script** (outside the service, run locally): for each receipt call the candidate model and score `total` (exact), `date` (exact), `store` (normalized match), item count, and per-item price match. Also record `usage.input_tokens/output_tokens` and latency, so cost per receipt is measured instead of estimated.
3. **Compare** on the same set: Sonnet 5.5 at `low`/`medium`/`high` effort, Haiku 5.5, and the current `gpt-4o-mini` as baseline. Pick the cheapest configuration that reaches the accuracy bar. Proposed bar (to be confirmed by the owner): total and date correct on at least 95% of receipts, and every wrong parse is visible in the review form anyway because the worker only stores a draft (ADR-010).
4. **Unit tests**: `ClaudeEngine` with a fake client (no network, no cost), in the style of `tests/worker/test_processor.py`: valid response, `refusal`, `max_tokens`, malformed JSON, HEIC input.
5. **End to end**: deploy with `ENGINE=claude`, upload one receipt from the frontend, and watch the worker logs and the `PARSED` record. Rollback is `ENGINE=dummy`.

## Consequences
- **+** No model hosting, no GPU, no weights in S3; the worker stays tiny; quality on real photos is likely higher than the self-hosted candidate.
- **+** Only `engine.py`, the worker env/secret wiring and the Terraform for the secret change.
- **−** Variable cost per receipt and a spend risk if someone loops uploads: keep the presigned-POST size limit (10 MB), consider a per-user daily cap, and set a spend limit in the Anthropic console.
- **−** Receipt images (personal financial data) are sent to a third party. Bedrock keeps them inside the AWS relationship; check the provider's data-retention terms before making this permanent.
- **−** Outbound internet and a secret add Terraform and IAM work (and the NAT cost trap above).
- **−** The model may be deprecated later; keeping the model id in configuration and keeping the golden set makes switching a measured decision.
- Cleanup: nothing new is created by the API itself; the secret has a small monthly cost (Secrets Manager about $0.40/secret, SSM SecureString standard is free). `parser_desired_count = 0` still stops the worker (ADR-010).

## Open questions
- Anthropic API directly or Bedrock? (Decide after checking Bedrock pricing and availability for `claude-sonnet-5-5`; the engine is the same apart from client construction.)
- Accuracy bar and the item schema (keep unit/amount/unit_price, or only name/price as in the review form).
- Remove the old synchronous `/receipts/parse` endpoint and `app/services/parser.py` (TODO item 10) once this engine works.
