output "cluster_name" {
  description = "ECS cluster name."
  value       = aws_ecs_cluster.this.name
}

output "cluster_arn" {
  description = "ECS cluster ARN (other services, such as the parser worker, run in it)."
  value       = aws_ecs_cluster.this.arn
}

output "service_name" {
  description = "ECS service name."
  value       = aws_ecs_service.backend.name
}

output "container_port" {
  description = "Port the backend listens on."
  value       = var.container_port
}
