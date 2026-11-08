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
    global_secondary_indexes = optional(list(object({
      name            = string
      hash_key        = string
      range_key       = optional(string)
      projection_type = optional(string, "ALL")
    })), [])
  }))
}

variable "tags" {
  description = "Tags applied to every table in this module."
  type        = map(string)
  default     = {}
}
