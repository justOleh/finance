variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
}

variable "aws_region" {
  description = "AWS region (log driver and passed to the container)."
  type        = string
}

variable "cluster_arn" {
  description = "ECS cluster to run in (shared with the backend)."
  type        = string
}

variable "image_repository_url" {
  description = "ECR repository URL (without tag) holding the worker image."
  type        = string
}

variable "image_tag" {
  description = "Tag of the worker image the task definition runs."
  type        = string
  default     = "latest"
}

variable "desired_count" {
  description = "Number of worker tasks. 0 stops Fargate billing; uploads then wait in the queue."
  type        = number
  default     = 1
}

variable "queue_arn" {
  description = "ARN of the SQS queue the worker consumes."
  type        = string
}

variable "receipts_bucket_arn" {
  description = "ARN of the receipts bucket; the worker may read objects under receipts/."
  type        = string
}

variable "dynamodb_table_arns" {
  description = "ARNs of the DynamoDB tables the worker writes receipt results to."
  type        = list(string)
}

variable "environment" {
  description = "Environment variables injected into the worker container."
  type        = map(string)
  default     = {}
}

variable "tags" {
  description = "Tags applied to all resources."
  type        = map(string)
  default     = {}
}
