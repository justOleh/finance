variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
}

variable "account_id" {
  description = "AWS account id; S3 may only invoke the function for a bucket of this account."
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

variable "uploads_bucket_arn" {
  description = "ARN of the bucket the browser uploads to (the function reads receipts/*)."
  type        = string
}

variable "converted_bucket_arn" {
  description = "ARN of the bucket the PNGs are written to (the function writes receipts/*)."
  type        = string
}

variable "converted_bucket_name" {
  description = "Name of the bucket the PNGs are written to."
  type        = string
}

variable "max_image_edge" {
  description = "Longest side, in pixels, of the converted PNG (larger images are downscaled)."
  type        = number
  default     = 2000
}

variable "memory_size" {
  description = "Memory in MB. A 12 MP phone photo needs about 1 GB to decode (CPU scales with it)."
  type        = number
  default     = 1024
}

variable "timeout_seconds" {
  description = "Function timeout."
  type        = number
  default     = 60
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
