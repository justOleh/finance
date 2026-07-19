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