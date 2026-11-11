variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
}

variable "bucket_id" {
  description = "Name of the private bucket holding the built frontend."
  type        = string
}

variable "bucket_arn" {
  description = "ARN of that bucket."
  type        = string
}

variable "bucket_regional_domain_name" {
  description = "Regional domain name of that bucket (the CloudFront origin)."
  type        = string
}

variable "tags" {
  description = "Tags applied to all resources."
  type        = map(string)
  default     = {}
}
