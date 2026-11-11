variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
}

variable "aws_region" {
  description = "AWS region of the runtime and of the Bedrock inference profile."
  type        = string
}

variable "image_repository_url" {
  description = "ECR repository URL (without tag) holding the agent image."
  type        = string
}

variable "image_repository_arn" {
  description = "ARN of that repository (the role may pull only from it)."
  type        = string
}

variable "image_tag" {
  description = "Tag of the agent image to run. deploy.sh passes a unique tag per build."
  type        = string
}

variable "model_id" {
  description = "Bedrock inference profile id of the chat model, for example eu.amazon.nova-pro-v1:0."
  type        = string

  validation {
    condition     = length(split(".", var.model_id)) >= 3
    error_message = "Use an inference profile id with a geography prefix, such as eu.amazon.nova-pro-v1:0."
  }
}

variable "api_base_url" {
  description = "HTTPS base URL of the REST API the agent's tools call."
  type        = string
}

variable "cognito_issuer" {
  description = "Issuer URL of the Cognito user pool."
  type        = string
}

variable "cognito_client_id" {
  description = "App client id whose access tokens may invoke the agent."
  type        = string
}

variable "max_tool_calls" {
  description = "Tool calls allowed per user message."
  type        = number
  default     = 8
}

variable "max_output_tokens" {
  description = "Output token cap per model call."
  type        = number
  default     = 2000
}

variable "max_turns_per_session" {
  description = "User messages allowed in one chat session."
  type        = number
  default     = 30
}

variable "tags" {
  description = "Tags applied to all resources."
  type        = map(string)
  default     = {}
}
