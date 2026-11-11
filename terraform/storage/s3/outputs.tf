output "bucket_ids" {
  description = "Map of logical name => bucket id."
  value       = { for k, b in aws_s3_bucket.this : k => b.id }
}

output "bucket_arns" {
  description = "Map of logical name => bucket ARN."
  value       = { for k, b in aws_s3_bucket.this : k => b.arn }
}

output "bucket_regional_domain_names" {
  description = "Map of logical name => regional domain name (the origin address for CloudFront)."
  value       = { for k, b in aws_s3_bucket.this : k => b.bucket_regional_domain_name }
}
