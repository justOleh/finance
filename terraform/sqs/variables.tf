variable "name" {
  description = "Queue name. The dead-letter queue is called <name>-dlq."
  type        = string
}

variable "source_bucket_arn" {
  description = "S3 bucket allowed to send event notifications to the queue."
  type        = string
}

variable "account_id" {
  description = "AWS account id; the queue policy only trusts the bucket if it belongs to this account."
  type        = string
}

variable "visibility_timeout_seconds" {
  description = "How long a received message is hidden. Must be longer than the worker's processing time."
  type        = number
  default     = 60
}

variable "max_receive_count" {
  description = "Deliveries before a message is moved to the dead-letter queue."
  type        = number
  default     = 3
}

variable "tags" {
  description = "Tags applied to all queues."
  type        = map(string)
  default     = {}
}
