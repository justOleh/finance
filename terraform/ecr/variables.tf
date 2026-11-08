variable "repositories" {
  description = "Map of logical name => ECR repository settings."
  type = map(object({
    name             = string
    force_delete     = optional(bool, false) # true: allow destroy even if images exist
    keep_last_images = optional(number, 5)
  }))
}

variable "tags" {
  description = "Tags applied to all repositories."
  type        = map(string)
  default     = {}
}
