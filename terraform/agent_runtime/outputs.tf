output "runtime_arn" {
  description = "ARN of the agent runtime."
  value       = aws_bedrockagentcore_agent_runtime.this.agent_runtime_arn
}

output "runtime_id" {
  description = "Id of the agent runtime (its logs are in /aws/bedrock-agentcore/runtimes/<id>-DEFAULT)."
  value       = aws_bedrockagentcore_agent_runtime.this.agent_runtime_id
}

# The browser POSTs here with `Authorization: Bearer <token>` and a session id header.
# The ARN is part of the path, so it must be URL-encoded.
output "invoke_url" {
  description = "HTTPS URL the chat page calls."
  value       = "https://bedrock-agentcore.${var.aws_region}.amazonaws.com/runtimes/${urlencode(aws_bedrockagentcore_agent_runtime.this.agent_runtime_arn)}/invocations?qualifier=DEFAULT"
}
