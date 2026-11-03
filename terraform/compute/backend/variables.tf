variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
}

variable "image_repository_url" {
  description = "ECR repository URL (without tag) for the backend image."
  type        = string
}

variable "container_port" {
  type    = number
  default = 8000
}

variable "cpu" {
  type    = number
  default = 256
}

variable "memory" {
  type    = number
  default = 512
}

variable "desired_count" {
  type    = number
  default = 1
}

variable "environment" {
  description = "Plain environment variables for the container."
  type        = map(string)
  default     = {}
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "dynamodb_table_arns" {
  description = "DynamoDB table ARNs the backend task may read and write."
  type        = list(string)
  default     = []
}

variable "service_name" {
  description = "Service name used in resource names and as the container name."
  type        = string
  default     = "backend"
}

variable "cluster_suffix" {
  type    = string
  default = "cluster"
}

variable "alb_suffix" {
  description = "Suffix for ALB/target group names (they share a 32-char limit)."
  type        = string
  default     = "api"
}
