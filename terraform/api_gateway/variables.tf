variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
}

variable "vpc_id" {
  description = "VPC the backend runs in."
  type        = string
}

variable "subnet_ids" {
  description = "Subnets for the VPC link's network interfaces."
  type        = list(string)
}

variable "backend_security_group_id" {
  description = "Security group of the backend task; an ingress rule from the VPC link is added to it."
  type        = string
}

variable "backend_port" {
  description = "Port the backend listens on."
  type        = number
}

variable "discovery_service_arn" {
  description = "Cloud Map service the backend tasks are registered in."
  type        = string
}

variable "cognito_issuer" {
  description = "Issuer URL of the Cognito user pool (https://cognito-idp.<region>.amazonaws.com/<pool id>)."
  type        = string
}

variable "cognito_client_id" {
  description = "App client id the access tokens are issued to."
  type        = string
}

variable "cors_allowed_origins" {
  description = "Browser origins allowed to call the API (the CloudFront URL of the frontend)."
  type        = list(string)
}

variable "throttling_rate_limit" {
  description = "Steady-state requests per second allowed across the API."
  type        = number
  default     = 10
}

variable "throttling_burst_limit" {
  description = "Burst of requests allowed across the API."
  type        = number
  default     = 20
}

variable "tags" {
  description = "Tags applied to all resources."
  type        = map(string)
  default     = {}
}
