output "function_arn" {
  description = "ARN of the convert-image function (the S3 notification target)."
  value       = aws_lambda_function.this.arn
}

output "function_name" {
  description = "Name of the convert-image function."
  value       = aws_lambda_function.this.function_name
}

output "failures_queue_url" {
  description = "Queue holding the events of uploads that could not be converted."
  value       = aws_sqs_queue.failures.id
}

output "s3_permission_id" {
  description = "Id of the S3 invoke permission; depend on it so the notification is created after S3 may invoke."
  value       = aws_lambda_permission.s3.id
}
