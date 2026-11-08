variable "name_prefix" {
  description = "Prefix for IAM resource names."
  type        = string
}

variable "dynamodb_table_arns" {
  description = "ARNs of the DynamoDB tables the backend may read and write."
  type        = list(string)
}

variable "local_dev_principal_arns" {
  description = "IAM user/role ARNs allowed to assume the backend role from a developer machine."
  type        = list(string)

  validation {
    condition     = length(var.local_dev_principal_arns) > 0
    error_message = "At least one principal ARN is required, otherwise nobody can assume the role."
  }
}

variable "tags" {
  description = "Tags applied to IAM resources that support tags."
  type        = map(string)
  default     = {}
}