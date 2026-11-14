# Secrets Manager entries the tasks read by reference. Terraform creates the empty entries; **a person puts the
# values in** (`aws secretsmanager put-secret-value`), so no secret value is ever in code, a plan or the state file.
# The database owner's password is RDS-managed (rds.tf) and goes only to the migrate task.

locals {
  secret_names = toset([
    "APP_SECRET_KEY",
    "DATABASE_URL", # the app role's connection string (loyalty_app), not the owner's
    "MOCK_API_TOKEN",
    "MOCK_API_DATABASE_URL",
    "OIDC_CLIENT_SECRET",
    "ANTHROPIC_API_KEY", # stays empty until live AI is approved (FEATURE_LIVE_AI=false)
  ])
}

resource "aws_secretsmanager_secret" "app" {
  for_each                = local.secret_names
  name                    = "${local.name}/${each.key}"
  kms_key_id              = aws_kms_key.data.arn
  recovery_window_in_days = var.environment == "production" ? 30 : 7
}
