variable "aws_account_id" {
  description = "AWS account ID (used as an assertion guard)."
  type        = string
  default     = "675129110096"
}

variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "eu-west-1"
}

variable "project" {
  description = "Project name, used as a prefix for resources."
  type        = string
  default     = "finance"
}

variable "env" {
  description = "Environment name, used as a prefix for resources."
  type        = string
  default     = "prod"
}

variable "local_dev_principal_arns" {
  description = "IAM user/role ARNs allowed to assume the backend role when running the backend locally."
  type        = list(string)
  default     = ["arn:aws:iam::675129110096:user/me"]
}

variable "backend_desired_count" {
  description = "Number of backend tasks. 0 stops Fargate billing without destroying anything."
  type        = number
  default     = 1
}

variable "parse_max_concurrency" {
  description = "Maximum parallel parse-receipt invocations (spend and API rate-limit cap, minimum 2)."
  type        = number
  default     = 2
}

variable "claude_model" {
  description = "Claude model id used to parse receipts."
  type        = string
  default     = "claude-sonnet-5-5"
}

variable "claude_effort" {
  description = "Claude effort level (low, medium, high, xhigh, max). Lower is cheaper and faster."
  type        = string
  default     = "medium"
}

variable "force_destroy_buckets" {
  description = "If true, S3 buckets are deleted together with all objects and versions on destroy."
  type        = bool
  default     = false
}

variable "extra_cors_origins" {
  description = "Extra browser origins allowed to call the API and upload receipts, for example [\"http://localhost:5173\"] to run the frontend locally against AWS."
  type        = list(string)
  default     = []
}

variable "chat_model_id" {
  description = "Bedrock inference profile id of the chat agent's model. List them with: aws bedrock list-inference-profiles. Claude models (for example eu.anthropic.claude-sonnet-5-5) need the Anthropic use-case form submitted for the account first."
  type        = string
  default     = "eu.amazon.nova-pro-v1:0"
}

variable "agent_image_tag" {
  description = "Tag of the agent image the runtime runs. deploy.sh passes a unique tag per build; a new tag creates a new runtime version."
  type        = string
  default     = "latest"
}

variable "budget_alert_email" {
  description = "Email for an AWS Budgets alert at 80% of monthly_budget_usd. Empty = no budget is created."
  type        = string
  default     = ""
}

variable "monthly_budget_usd" {
  description = "Monthly cost budget for the account, in USD."
  type        = number
  default     = 10
}
