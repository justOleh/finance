variable "buckets" {
  description = "Map of logical name => bucket configuration."
  type = map(object({
    name          = string
    versioning    = optional(bool, false)
    force_destroy = optional(bool, false)
    sse_algorithm = optional(string, "AES256")
  }))
}

variable "tags" {
  description = "Tags applied to every bucket in this module."
  type        = map(string)
  default     = {}
}
