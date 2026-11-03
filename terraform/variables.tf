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

variable "force_destroy_buckets" {
  description = "If true, S3 buckets are deleted together with all objects and versions on destroy."
  type        = bool
  default     = false
}

variable "parser_cpu" {
  description = "Fargate CPU units for the receipt parser (model inference needs more than the default)."
  type        = number
  default     = 2048
}

variable "parser_memory" {
  description = "Fargate memory (MiB) for the receipt parser."
  type        = number
  default     = 8192
}
