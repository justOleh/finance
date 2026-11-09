output "queue_url" {
  description = "URL of the work queue."
  value       = aws_sqs_queue.this.id
}

output "queue_arn" {
  description = "ARN of the work queue."
  value       = aws_sqs_queue.this.arn
}

output "dlq_url" {
  description = "URL of the dead-letter queue."
  value       = aws_sqs_queue.dlq.id
}

output "dlq_arn" {
  description = "ARN of the dead-letter queue."
  value       = aws_sqs_queue.dlq.arn
}

output "queue_policy_id" {
  description = "Id of the queue policy; depend on it so S3 notifications are created after S3 may send."
  value       = aws_sqs_queue_policy.s3_send.id
}
