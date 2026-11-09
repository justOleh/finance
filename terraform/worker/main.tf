# Receipt parser worker: an SQS consumer on ECS Fargate (ADR-010).
# Unlike the backend it has no port, no inbound rule and no health-check endpoint: it only
# makes outbound calls (SQS, S3, DynamoDB, ECR, CloudWatch). It uses a public IP for the same
# reason as the backend (no NAT gateway, see ADR-007).

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_security_group" "worker" {
  name        = "${var.name_prefix}-parser"
  description = "Parser worker: no inbound, all outbound"
  vpc_id      = data.aws_vpc.default.id
  tags        = var.tags
}

resource "aws_vpc_security_group_egress_rule" "all" {
  security_group_id = aws_security_group.worker.id
  description       = "All outbound"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${var.name_prefix}-parser"
  retention_in_days = 7
  tags              = var.tags
}

# --- Roles --------------------------------------------------------------------
data "aws_iam_policy_document" "ecs_tasks_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

# Execution role: used by ECS itself (pull image, write logs).
resource "aws_iam_role" "execution" {
  name               = "${var.name_prefix}-parser-exec"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
  tags               = var.tags
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Task role: what the worker code may do. Separate from the backend role on purpose: the
# worker can read receipts but not sign uploads, the backend can sign uploads but not read.
resource "aws_iam_role" "task" {
  name               = "${var.name_prefix}-parser"
  description        = "Assumed by the receipt parser worker."
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
  tags               = var.tags
}

data "aws_iam_policy_document" "task" {
  statement {
    sid = "ConsumeQueue"
    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:ChangeMessageVisibility",
      "sqs:GetQueueAttributes",
    ]
    resources = [var.queue_arn]
  }

  statement {
    sid       = "ReadReceiptImages"
    actions   = ["s3:GetObject"]
    resources = ["${var.receipts_bucket_arn}/receipts/*"]
  }

  # Updates the receipt record only (it never creates items or reads other data).
  statement {
    sid       = "UpdateReceiptRecords"
    actions   = ["dynamodb:UpdateItem"]
    resources = var.dynamodb_table_arns
  }
}

resource "aws_iam_role_policy" "task" {
  name   = "parser-access"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.task.json
}

# --- Task definition and service ---------------------------------------------
resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.name_prefix}-parser"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  tags                     = var.tags

  # Matches the arm64 image built on Apple Silicon.
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64"
  }

  container_definitions = jsonencode([{
    name      = "parser"
    image     = "${var.image_repository_url}:${var.image_tag}"
    essential = true

    environment = [for k, v in var.environment : { name = k, value = v }]

    # SQS long polling waits up to 20 s; give the loop time to finish the current message.
    stopTimeout = 60

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.worker.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "parser"
      }
    }
  }])
}

resource "aws_ecs_service" "worker" {
  name            = "${var.name_prefix}-parser"
  cluster         = var.cluster_arn
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"
  tags            = var.tags

  network_configuration {
    subnets          = data.aws_subnets.default.ids
    security_groups  = [aws_security_group.worker.id]
    assign_public_ip = true # needed to pull from ECR and reach AWS APIs without a NAT gateway
  }
}
