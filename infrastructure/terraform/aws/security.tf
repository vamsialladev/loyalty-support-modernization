# Restricted ingress and egress: the internet reaches only the load balancer on 443; the load balancer reaches only
# the app; the app and the worker reach the database, the mock API and HTTPS out (the model provider, the identity
# provider); nothing reaches the database except the tasks.

resource "aws_security_group" "alb" {
  name        = "${local.name}-alb"
  description = "HTTPS from the internet to the console"
  vpc_id      = aws_vpc.main.id
}

resource "aws_vpc_security_group_ingress_rule" "alb_https" {
  security_group_id = aws_security_group.alb.id
  description       = "HTTPS from anywhere (the console is a public sign-in page)"
  cidr_ipv4         = "0.0.0.0/0" #trivy:ignore:AVD-AWS-0107 the console's own sign-in page is meant to be reachable
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "alb_to_app" {
  security_group_id            = aws_security_group.alb.id
  description                  = "To the app tasks only"
  referenced_security_group_id = aws_security_group.app.id
  from_port                    = 8010
  to_port                      = 8010
  ip_protocol                  = "tcp"
}

resource "aws_security_group" "app" {
  name        = "${local.name}-app"
  description = "The app, worker and mock API tasks"
  vpc_id      = aws_vpc.main.id
}

resource "aws_vpc_security_group_ingress_rule" "app_from_alb" {
  security_group_id            = aws_security_group.app.id
  description                  = "From the load balancer"
  referenced_security_group_id = aws_security_group.alb.id
  from_port                    = 8010
  to_port                      = 8010
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "mock_from_tasks" {
  security_group_id            = aws_security_group.app.id
  description                  = "The app and worker call the mock customer API"
  referenced_security_group_id = aws_security_group.app.id
  from_port                    = 8020
  to_port                      = 8020
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "app_to_db" {
  security_group_id            = aws_security_group.app.id
  description                  = "To Postgres"
  referenced_security_group_id = aws_security_group.db.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "app_to_mock" {
  security_group_id            = aws_security_group.app.id
  description                  = "To the mock customer API"
  referenced_security_group_id = aws_security_group.app.id
  from_port                    = 8020
  to_port                      = 8020
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "app_https_out" {
  security_group_id = aws_security_group.app.id
  description       = "HTTPS out through the NAT: the model provider, the identity provider, AWS APIs"
  cidr_ipv4         = "0.0.0.0/0" #trivy:ignore:AVD-AWS-0104 egress is HTTPS only; a customer can narrow it with a proxy or VPC endpoints
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
}

resource "aws_security_group" "db" {
  name        = "${local.name}-db"
  description = "Postgres, reachable from the tasks only"
  vpc_id      = aws_vpc.main.id
}

resource "aws_vpc_security_group_ingress_rule" "db_from_app" {
  security_group_id            = aws_security_group.db.id
  description                  = "From the app, worker and mock API tasks"
  referenced_security_group_id = aws_security_group.app.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}
