variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
}

variable "aws_region" {
  description = "AWS region (used by the log driver and passed to the container)."
  type        = string
}

variable "task_role_arn" {
  description = "IAM role the backend code runs as (DynamoDB access). Must trust ecs-tasks.amazonaws.com."
  type        = string
}

variable "container_port" {
  description = "Port the backend listens on inside the container."
  type        = number
  default     = 8000
}

variable "image_repository_url" {
  description = "ECR repository URL (without tag) holding the backend image. Created by the ecr module."
  type        = string
}

variable "image_tag" {
  description = "Tag of the backend image in ECR that the task definition runs."
  type        = string
  default     = "latest"
}

variable "desired_count" {
  description = "Number of backend tasks. Set to 0 to stop paying for Fargate without destroying anything."
  type        = number
  default     = 1
}

variable "environment" {
  description = "Environment variables injected into the backend container."
  type        = map(string)
  default     = {}
}

variable "tags" {
  description = "Tags applied to all resources."
  type        = map(string)
  default     = {}
}
