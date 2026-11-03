variable "repositories" {
  description = "Map of logical name => ECR repository name."
  type        = map(string)
}

variable "keep_last_images" {
  type    = number
  default = 10
}

variable "tags" {
  type    = map(string)
  default = {}
}
