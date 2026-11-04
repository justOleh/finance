output "frontend_bucket" {
  description = "Name of the S3 bucket that hosts the frontend."
  value       = module.frontend_bucket.bucket_ids["app"]
}

output "frontend_hosting_url" {
  description = "URL to access the frontend S3 bucket hosting the static website."
  value       = module.frontend_bucket.website_urls["app"]
}
