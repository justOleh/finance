variable "buckets" {
  description = "Map of logical name => bucket configuration."
  type = map(object({
    name            = string
    versioning      = optional(bool, false)
    force_destroy   = optional(bool, false)
    sse_algorithm   = optional(string, "AES256")
    website_hosting = optional(bool, false)
    index_document  = optional(string, "index.html")
    error_document  = optional(string, "index.html")
    block_public    = optional(bool, true)
    # Browser origins allowed to call the bucket directly (e.g. presigned-POST uploads).
    # Empty = no CORS configuration.
    cors_allowed_origins = optional(list(string), [])
    cors_allowed_methods = optional(list(string), ["GET"])
    # Delete objects (and old versions) this many days after creation. null = keep forever.
    expiration_days = optional(number, null)
  }))
}

variable "tags" {
  description = "Tags applied to every bucket in this module."
  type        = map(string)
  default     = {}
}
