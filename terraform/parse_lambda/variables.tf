variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
}

variable "image_repository_url" {
  description = "ECR repository URL (without tag) holding the function image."
  type        = string
}

variable "image_tag" {
  description = "Tag of the function image. deploy.sh pushes :latest and updates the function code."
  type        = string
  default     = "latest"
}

variable "queue_arn" {
  description = "ARN of the SQS queue the function consumes."
  type        = string
}

variable "converted_bucket_arn" {
  description = "ARN of the converted bucket; the function may read objects under receipts/."
  type        = string
}

variable "dynamodb_table_arns" {
  description = "ARNs of the DynamoDB tables the function writes receipt results to."
  type        = list(string)
}

variable "environment" {
  description = "Environment variables for the function (everything except the API key)."
  type        = map(string)
  default     = {}
}

variable "anthropic_api_key_placeholder" {
  description = "Initial ANTHROPIC_API_KEY value. Set the real key in the Lambda console; Terraform ignores later changes."
  type        = string
  default     = "set-me-in-the-lambda-console"
}

variable "memory_size" {
  description = "Memory in MB. The function is network-bound (one API call per receipt)."
  type        = number
  default     = 512
}

variable "timeout_seconds" {
  description = "Function timeout. The queue visibility timeout must be at least 6 times this."
  type        = number
  default     = 120
}

variable "maximum_concurrency" {
  description = "Maximum parallel invocations from the queue (2 to 1000)."
  type        = number
  default     = 2
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention."
  type        = number
  default     = 14
}

variable "tags" {
  description = "Tags applied to all resources."
  type        = map(string)
  default     = {}
}
