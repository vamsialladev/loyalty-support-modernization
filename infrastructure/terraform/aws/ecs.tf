# ECS Fargate: the app, the worker and the mock customer API, as the Compose stack runs them (ADR-0074), plus a
# one-off migrate task that is the only place the owner role's credentials go (ADR-0058). Least privilege: the
# execution role pulls images and reads the named secrets; the task roles can do nothing in AWS but write their logs
# (the app needs no AWS API at all).

resource "aws_ecs_cluster" "main" {
  name = local.name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
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

resource "aws_iam_role" "execution" {
  name               = "${local.name}-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

data "aws_iam_policy_document" "execution" {
  statement {
    sid       = "PullAndLog"
    actions   = ["ecr:GetAuthorizationToken", "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["*"] #trivy:ignore:AVD-AWS-0057 ECR's token call has no resource; log streams are created under the groups below
  }

  statement {
    sid       = "ReadOnlyTheseSecrets"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [for s in aws_secretsmanager_secret.app : s.arn]
  }

  statement {
    sid       = "DecryptThem"
    actions   = ["kms:Decrypt"]
    resources = [aws_kms_key.data.arn]
  }
}

resource "aws_iam_role_policy" "execution" {
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.execution.json
}

# Task role: no AWS permissions. The app talks to Postgres, the mock API and HTTPS providers, never to AWS APIs.
resource "aws_iam_role" "task" {
  name               = "${local.name}-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

locals {
  common_env = [
    { name = "APP_PROFILE", value = var.environment == "production" ? "approved" : "staging" },
    { name = "AUTH_MODE", value = "oidc" },
    { name = "MOCK_API_URL", value = "http://mock-api.${local.name}.local:8020" },
    { name = "FEATURE_ADJUSTMENT_EXECUTION", value = "false" }, # off until the customer approves (production.env)
    { name = "FEATURE_LIVE_AI", value = "false" },
    { name = "LOG_FORMAT", value = "json" },
  ]
  secret_env = [for name in keys(aws_secretsmanager_secret.app) : { name = name, valueFrom = aws_secretsmanager_secret.app[name].arn }]

  containers = {
    app = {
      command = ["uvicorn", "--factory", "app.main:serve", "--host", "0.0.0.0", "--port", "8010"]
      port    = 8010
      image   = var.app_image
    }
    worker = {
      command = ["python", "-m", "app.worker"]
      port    = null
      image   = var.app_image
    }
    mock-api = {
      command = null
      port    = 8020
      image   = var.mock_api_image
    }
  }
}

resource "aws_ecs_task_definition" "service" {
  for_each                 = local.containers
  family                   = "${local.name}-${each.key}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([{
    name                   = each.key
    image                  = each.value.image
    command                = each.value.command
    essential              = true
    readonlyRootFilesystem = true
    user                   = "10001"
    portMappings           = each.value.port == null ? [] : [{ containerPort = each.value.port, protocol = "tcp" }]
    environment            = local.common_env
    secrets                = local.secret_env
    linuxParameters        = { capabilities = { drop = ["ALL"] } }
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.service[each.key].name
        awslogs-region        = var.region
        awslogs-stream-prefix = each.key
      }
    }
  }])
}

resource "aws_service_discovery_private_dns_namespace" "main" {
  name = "${local.name}.local"
  vpc  = aws_vpc.main.id
}

resource "aws_service_discovery_service" "mock_api" {
  name = "mock-api"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.main.id
    dns_records {
      type = "A"
      ttl  = 10
    }
  }
}

resource "aws_ecs_service" "service" {
  for_each        = local.containers
  name            = each.key
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.service[each.key].arn
  desired_count   = 1
  launch_type     = "FARGATE"

  deployment_circuit_breaker {
    enable   = true # a release that doesn't become healthy is rolled back to the last working task definition
    rollback = true
  }

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = false
  }

  dynamic "load_balancer" {
    for_each = each.key == "app" ? [1] : []
    content {
      target_group_arn = aws_lb_target_group.app.arn
      container_name   = "app"
      container_port   = 8010
    }
  }

  dynamic "service_registries" {
    for_each = each.key == "mock-api" ? [1] : []
    content {
      registry_arn = aws_service_discovery_service.mock_api.arn
    }
  }
}
