output "service_name" {
  description = "ECS service running the parser worker."
  value       = aws_ecs_service.worker.name
}

output "task_role_arn" {
  description = "IAM role the worker code runs as."
  value       = aws_iam_role.task.arn
}
