terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

# ── Rede ─────────────────────────────────────────────────────────────────────

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# ── ECR (já criado pelo deploy worker) ───────────────────────────────────────

resource "aws_ecr_repository" "app" {
  name                 = "foolguard-app-${var.app_id}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# ── ECS Cluster ──────────────────────────────────────────────────────────────

resource "aws_ecs_cluster" "foolguard" {
  name = "foolguard-cluster"
}

# ── IAM para ECS Task ────────────────────────────────────────────────────────

resource "aws_iam_role" "ecs_task_execution" {
  name = "foolguard-ecs-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# ── Security Group ───────────────────────────────────────────────────────────

resource "aws_security_group" "app" {
  name        = "foolguard-app-${var.app_id}-sg"
  description = "FoolGuard app ${var.app_id}"
  vpc_id      = data.aws_vpc.default.id

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

# ── Load Balancer ────────────────────────────────────────────────────────────

resource "aws_lb" "app" {
  name               = "sf-app-${var.app_id}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.app.id]
  subnets            = data.aws_subnets.default.ids
}

resource "aws_lb_target_group" "app" {
  name        = "sf-app-${var.app_id}-tg"
  port        = 80
  protocol    = "HTTP"
  vpc_id      = data.aws_vpc.default.id
  target_type = "ip"

  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "app" {
  load_balancer_arn = aws_lb.app.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

# ── ECS Task Definition ──────────────────────────────────────────────────────

resource "aws_ecs_task_definition" "app" {
  family                   = "foolguard-app-${var.app_id}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn

  container_definitions = jsonencode([{
    name      = "app"
    image     = var.image_uri
    essential = true
    portMappings = [{
      containerPort = 80
      protocol      = "tcp"
    }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = "/foolguard/app-${var.app_id}"
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "app"
        "awslogs-create-group"  = "true"
      }
    }
  }])
}

# ── ECS Service ──────────────────────────────────────────────────────────────

resource "aws_ecs_service" "app" {
  name            = "foolguard-app-${var.app_id}"
  cluster         = aws_ecs_cluster.foolguard.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = data.aws_subnets.default.ids
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "app"
    container_port   = 80
  }

  depends_on = [aws_lb_listener.app]
}
