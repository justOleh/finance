output "table_names" {
  description = "Map of logical name => DynamoDB table name."
  value       = { for k, t in aws_dynamodb_table.this : k => t.name }
}

output "table_arns" {
  description = "Map of logical name => DynamoDB table ARN."
  value       = { for k, t in aws_dynamodb_table.this : k => t.arn }
}
