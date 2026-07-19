output "bucket_ids" {
  description = "Map of logical name => bucket id."
  value       = { for k, b in aws_s3_bucket.this : k => b.id }
}

output "bucket_arns" {
  description = "Map of logical name => bucket ARN."
  value       = { for k, b in aws_s3_bucket.this : k => b.arn }
}

output "bucket_endpoints" {
  description = "Map of logical name => website endpoint."
  value       = { for k, v in aws_s3_bucket_website_configuration.this : k => v.website_endpoint }
}
