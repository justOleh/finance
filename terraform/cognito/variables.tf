variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
}

variable "access_token_minutes" {
  description = "Lifetime of access/id tokens. Short, because a stolen JWT is valid until it expires."
  type        = number
  default     = 60
}

variable "refresh_token_days" {
  description = "Lifetime of the refresh token (how long you stay signed in without typing the password)."
  type        = number
  default     = 30
}

variable "tags" {
  description = "Tags applied to all resources."
  type        = map(string)
  default     = {}
}
