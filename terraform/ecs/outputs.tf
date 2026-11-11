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

output "vpc_id" {
  description = "VPC the backend runs in (the default VPC)."
  value       = data.aws_vpc.default.id
}

output "subnet_ids" {
  description = "Subnets of that VPC (the API Gateway VPC link is placed in them)."
  value       = data.aws_subnets.default.ids
}

output "security_group_id" {
  description = "Security group of the backend task. It has no inbound rule of its own."
  value       = aws_security_group.backend.id
}

output "discovery_service_arn" {
  description = "Cloud Map service the backend tasks are registered in."
  value       = aws_service_discovery_service.backend.arn
}

output "container_port" {
  description = "Port the backend listens on."
  value       = var.container_port
}
