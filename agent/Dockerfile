# Chat agent for Amazon Bedrock AgentCore Runtime (ADR-014). Build context: agent/
#   docker build --platform linux/arm64 --provenance=false -t <repo>:<tag> .
# AgentCore Runtime requires an arm64 image that serves POST /invocations and GET /ping on 8080;
# BedrockAgentCoreApp provides both.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY finance_agent/ ./finance_agent/

# Do not run as root.
RUN useradd --create-home --uid 1000 agent
USER agent

ENV PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["python", "-m", "finance_agent.main"]
