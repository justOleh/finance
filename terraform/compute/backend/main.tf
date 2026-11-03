data "aws_region" "current" {}

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_cloudwatch_log_group" "this" {
  name              = "/ecs/${var.name_prefix}-${var.service_name}"
  retention_in_days = 14
  tags              = var.tags
}

resource "aws_ecs_cluster" "this" {
  name = "${var.name_prefix}-${var.cluster_suffix}"
  tags = var.tags
}

data "aws_iam_policy_document" "ecs_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

# Pulls the image from ECR and writes logs.
resource "aws_iam_role" "execution" {
  name               = "${var.name_prefix}-${var.service_name}-exec"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
  tags               = var.tags
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Runtime role of the app itself (least privilege; add policies as needed).
resource "aws_iam_role" "task" {
  name               = "${var.name_prefix}-${var.service_name}-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
  tags               = var.tags
}

resource "aws_iam_role_policy" "task_dynamodb" {
  count = length(var.dynamodb_table_arns) > 0 ? 1 : 0

  name = "dynamodb-access"
  role = aws_iam_role.task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:DeleteItem",
        "dynamodb:Scan",
        "dynamodb:Query",
      ]
      Resource = var.dynamodb_table_arns
    }]
  })
}

resource "aws_security_group" "alb" {
  name        = "${var.name_prefix}-${var.service_name}-alb"
  description = "Backend ALB"
  vpc_id      = data.aws_vpc.default.id
  tags        = var.tags

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_lb" "this" {
  name               = "${substr(var.name_prefix, 0, 24)}-${var.alb_suffix}"
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = data.aws_subnets.default.ids
  tags               = var.tags
}

resource "aws_lb_target_group" "this" {
  name        = "${substr(var.name_prefix, 0, 24)}-${var.alb_suffix}"
  port        = var.container_port
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = data.aws_vpc.default.id
  tags        = var.tags

  # Default is 300s, which makes deploys and destroys wait 5 minutes per drain.
  deregistration_delay = 10

  health_check {
    path    = "/health"
    matcher = "200"
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.this.arn
  }
}

resource "aws_security_group" "this" {
  name        = "${var.name_prefix}-${var.service_name}"
  description = "Backend ECS service"
  vpc_id      = data.aws_vpc.default.id
  tags        = var.tags

  ingress {
    from_port       = var.container_port
    to_port         = var.container_port
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_ecs_task_definition" "this" {
  family                   = "${var.name_prefix}-${var.service_name}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  tags                     = var.tags

  container_definitions = jsonencode([{
    name         = var.service_name
    image        = "${var.image_repository_url}:latest"
    essential    = true
    portMappings = [{ containerPort = var.container_port, protocol = "tcp" }]
    environment  = [for k, v in var.environment : { name = k, value = v }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.this.name
        awslogs-region        = data.aws_region.current.name
        awslogs-stream-prefix = var.service_name
      }
    }
  }])
}

resource "aws_ecs_service" "this" {
  name            = "${var.name_prefix}-${var.service_name}"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.this.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"
  tags            = var.tags

  load_balancer {
    target_group_arn = aws_lb_target_group.this.arn
    container_name   = var.service_name
    container_port   = var.container_port
  }

  depends_on = [aws_lb_listener.http]

  network_configuration {
    subnets          = data.aws_subnets.default.ids
    security_groups  = [aws_security_group.this.id]
    assign_public_ip = true
  }
}
