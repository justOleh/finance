output "frontend_bucket" {
  description = "Name of the S3 bucket that hosts the frontend."
  value       = module.frontend_bucket.bucket_ids["app"]
}

output "frontend_hosting_url" {
  description = "URL to access the frontend S3 bucket hosting the static website."
  value       = module.frontend_bucket.website_urls["app"]
}

output "app_table_name" {
  description = "Name of the DynamoDB table used by the backend."
  value       = module.dynamodb_table.table_names["app"]
}

output "app_table_arn" {
  description = "ARN of the DynamoDB table (use it to scope the backend IAM policy)."
  value       = module.dynamodb_table.table_arns["app"]
}

output "backend_ecr_repository_url" {
  description = "ECR repository the backend image is pushed to."
  value       = module.ecr.repository_urls["backend"]
}

output "ecs_cluster_name" {
  description = "ECS cluster running the backend."
  value       = module.backend_ecs.cluster_name
}

output "ecs_backend_service_name" {
  description = "ECS service running the backend."
  value       = module.backend_ecs.service_name
}

output "backend_port" {
  description = "Port the backend listens on."
  value       = module.backend_ecs.container_port
}

output "backend_role_arn" {
  description = "ARN of the IAM role the backend assumes to access DynamoDB."
  value       = module.backend_iam.backend_role_arn
}


output "cognito_user_pool_id" {
  description = "Cognito user pool id."
  value       = module.cognito.user_pool_id
}

output "cognito_client_id" {
  description = "Cognito app client id used by the frontend."
  value       = module.cognito.client_id
}

output "parser_ecr_repository_url" {
  description = "ECR repository the receipt parser worker image is pushed to."
  value       = module.ecr.repository_urls["parser"]
}

output "ecs_parser_service_name" {
  description = "ECS service running the receipt parser worker."
  value       = module.parser_worker.service_name
}

output "receipts_bucket" {
  description = "Private bucket receiving receipt uploads."
  value       = module.receipts_bucket.bucket_ids["receipts"]
}

output "receipts_queue_url" {
  description = "SQS queue the parser worker consumes."
  value       = module.receipts_queue.queue_url
}

output "receipts_dlq_url" {
  description = "Dead-letter queue: receipts that failed 3 times."
  value       = module.receipts_queue.dlq_url
}
