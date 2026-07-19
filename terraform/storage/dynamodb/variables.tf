variable "tables" {
  description = "Map of logical name => DynamoDB table configuration."
  type = map(object({
    name         = string
    hash_key     = string
    range_key    = optional(string)
    billing_mode = optional(string, "PAY_PER_REQUEST")
    attributes = list(object({
      name = string
      type = string
    }))
  }))
}

variable "tags" {
  description = "Tags applied to every table in this module."
  type        = map(string)
  default     = {}
}
