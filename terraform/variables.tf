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
