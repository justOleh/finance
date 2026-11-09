# Backend on ECS Fargate, "cheapest possible" variant:
#  - default VPC, public subnets, task gets a public IP (no NAT gateway, no ALB)
#  - inbound port is open to the internet; access control is Cognito JWT checks in the API

# --- Networking (default VPC) -------------------------------------------------
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_security_group" "backend" {
  name        = "${var.name_prefix}-backend"
  description = "Backend task: inbound API port, auth enforced by the API (Cognito)"
  vpc_id      = data.aws_vpc.default.id
  tags        = var.tags
}

resource "aws_vpc_security_group_ingress_rule" "api" {
  security_group_id = aws_security_group.backend.id
  description       = "Backend API (public, Cognito-authenticated)"
  ip_protocol       = "tcp"
  from_port         = var.container_port
  to_port           = var.container_port
  cidr_ipv4         = "0.0.0.0/0"
}

# The task must reach ECR (pull image), CloudWatch (logs) and DynamoDB.
resource "aws_vpc_security_group_egress_rule" "all" {
  security_group_id = aws_security_group.backend.id
  description       = "All outbound"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

# --- Logs ---------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/${var.name_prefix}-backend"
  retention_in_days = 7
  tags              = var.tags
}

# --- Task execution role: used by ECS itself (pull image, write logs) ---------
# Different from the TASK role (var.task_role_arn), which is what your code uses.
data "aws_iam_policy_document" "ecs_tasks_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execution" {
  name               = "${var.name_prefix}-backend-exec"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
  tags               = var.tags
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# --- Cluster, task definition, service ----------------------------------------
resource "aws_ecs_cluster" "this" {
  name = "${var.name_prefix}-cluster"
  tags = var.tags
}

resource "aws_ecs_task_definition" "backend" {
  family                   = "${var.name_prefix}-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = var.task_role_arn
  tags                     = var.tags

  # Matches the arm64 Docker image built on Apple Silicon (and ~20% cheaper).
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64"
  }

  container_definitions = jsonencode([{
    name      = "backend"
    image     = "${var.image_repository_url}:${var.image_tag}"
    essential = true

    portMappings = [{ containerPort = var.container_port, protocol = "tcp" }]

    environment = [for k, v in var.environment : { name = k, value = v }]

    # python:slim has no curl, so use the stdlib.
    healthCheck = {
      command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:${var.container_port}/health')\""]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 15
    }

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.backend.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "backend"
      }
    }
  }])
}

resource "aws_ecs_service" "backend" {
  name            = "${var.name_prefix}-backend"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"
  tags            = var.tags

  network_configuration {
    subnets          = data.aws_subnets.default.ids
    security_groups  = [aws_security_group.backend.id]
    assign_public_ip = true # needed to pull from ECR without a NAT gateway
  }
}
