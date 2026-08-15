variable "name_prefix" {
  type = string
}

variable "region" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

resource "random_password" "db" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "aws_secretsmanager_secret" "db_credentials" {
  name                    = "${var.name_prefix}/${var.region}/db-credentials"
  description             = "Ghost Fabric pilot RDS credentials (simulation audit store)."
  recovery_window_in_days = 7

  tags = merge(var.tags, {
    Name   = "${var.name_prefix}-db-credentials"
    Region = var.region
  })
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = "ghost"
    password = random_password.db.result
    dbname   = "ghost_fabric"
    engine   = "postgres"
    port     = 5432
  })
}

resource "aws_secretsmanager_secret" "auth_tokens" {
  name                    = "${var.name_prefix}/${var.region}/auth-tokens"
  description             = "Ghost Fabric pilot bearer tokens. Rotate before any external pilot."
  recovery_window_in_days = 7

  tags = merge(var.tags, {
    Name   = "${var.name_prefix}-auth-tokens"
    Region = var.region
  })
}

resource "random_password" "viewer_token" {
  length  = 32
  special = false
}

resource "random_password" "operator_token" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret_version" "auth_tokens" {
  secret_id = aws_secretsmanager_secret.auth_tokens.id
  secret_string = jsonencode({
    AUTH_TOKENS = "${random_password.viewer_token.result}=viewer:PILOT-VIEWER,${random_password.operator_token.result}=operator:PILOT-OPERATOR"
  })
}

output "db_secret_arn" {
  value = aws_secretsmanager_secret.db_credentials.arn
}

output "db_secret_name" {
  value = aws_secretsmanager_secret.db_credentials.name
}

output "db_password" {
  value     = random_password.db.result
  sensitive = true
}

output "db_username" {
  value = "ghost"
}

output "auth_tokens_secret_arn" {
  value = aws_secretsmanager_secret.auth_tokens.arn
}

output "auth_tokens_secret_name" {
  value = aws_secretsmanager_secret.auth_tokens.name
}
