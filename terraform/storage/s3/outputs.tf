output "bucket_ids" {
  description = "Map of logical name => bucket id."
  value       = { for k, b in aws_s3_bucket.this : k => b.id }
}

output "bucket_arns" {
  description = "Map of logical name => bucket ARN."
  value       = { for k, b in aws_s3_bucket.this : k => b.arn }
}

output "website_urls" {
  description = "Map of logical name => website URL, only for buckets with website_hosting enabled."
  value = {
    for k, w in aws_s3_bucket_website_configuration.this :
    k => "http://${w.website_endpoint}"
  }
}
