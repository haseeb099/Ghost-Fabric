variable "name_prefix" {
  type = string
}

variable "region" {
  type = string
}

variable "vpc_cidr" {
  type = string
}

variable "enable_nat_gateway" {
  type = bool
}

variable "api_image_tag" {
  type = string
}

variable "web_image_tag" {
  type = string
}

variable "api_cpu" {
  type = number
}

variable "api_memory" {
  type = number
}

variable "web_cpu" {
  type = number
}

variable "web_memory" {
  type = number
}

variable "db_instance_class" {
  type = string
}

variable "db_allocated_storage" {
  type = number
}

variable "db_backup_retention_days" {
  type = number
}

variable "auth_mode" {
  type = string
}

variable "desired_count" {
  type = number
}

variable "tags" {
  type = map(string)
}

module "networking" {
  source = "../networking"

  name_prefix        = var.name_prefix
  region             = var.region
  vpc_cidr           = var.vpc_cidr
  enable_nat_gateway = var.enable_nat_gateway
  tags               = var.tags
}

module "ecr" {
  source = "../ecr"

  name_prefix = var.name_prefix
  region      = var.region
  tags        = var.tags
}

module "secrets" {
  source = "../secrets"

  name_prefix = var.name_prefix
  region      = var.region
  tags        = var.tags
}

data "aws_subnet" "private" {
  for_each = toset(module.networking.private_subnet_ids)
  id       = each.value
}

module "rds" {
  source = "../rds"

  name_prefix           = var.name_prefix
  region                = var.region
  vpc_id                = module.networking.vpc_id
  db_subnet_group_name  = module.networking.db_subnet_group_name
  private_subnet_cidrs  = [for subnet in data.aws_subnet.private : subnet.cidr_block]
  instance_class        = var.db_instance_class
  allocated_storage     = var.db_allocated_storage
  backup_retention_days = var.db_backup_retention_days
  db_username           = module.secrets.db_username
  db_password           = module.secrets.db_password
  tags                  = var.tags
}

resource "aws_secretsmanager_secret" "database_url" {
  name                    = "${var.name_prefix}/${var.region}/database-url"
  description             = "Fully formed Ghost Fabric DATABASE_URL for ECS tasks."
  recovery_window_in_days = 7
  tags                    = var.tags
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id = aws_secretsmanager_secret.database_url.id
  secret_string = jsonencode({
    DATABASE_URL = format(
      "postgresql+psycopg://%s:%s@%s:%s/%s",
      module.secrets.db_username,
      urlencode(module.secrets.db_password),
      module.rds.endpoint,
      module.rds.port,
      module.rds.db_name
    )
  })
}

module "ecs" {
  source = "../ecs"

  name_prefix             = var.name_prefix
  region                  = var.region
  vpc_id                  = module.networking.vpc_id
  public_subnet_ids       = module.networking.public_subnet_ids
  private_subnet_ids      = module.networking.private_subnet_ids
  api_image               = "${module.ecr.api_repository_url}:${var.api_image_tag}"
  web_image               = "${module.ecr.web_repository_url}:${var.web_image_tag}"
  api_cpu                 = var.api_cpu
  api_memory              = var.api_memory
  web_cpu                 = var.web_cpu
  web_memory              = var.web_memory
  desired_count           = var.desired_count
  database_url_secret_arn = aws_secretsmanager_secret.database_url.arn
  auth_tokens_secret_arn  = module.secrets.auth_tokens_secret_arn
  auth_mode               = var.auth_mode
  tags                    = var.tags
}

output "region" {
  value = var.region
}

output "vpc_id" {
  value = module.networking.vpc_id
}

output "alb_dns_name" {
  value = module.ecs.alb_dns_name
}

output "api_repository_url" {
  value = module.ecr.api_repository_url
}

output "web_repository_url" {
  value = module.ecr.web_repository_url
}

output "rds_endpoint" {
  value = module.rds.endpoint
}

output "cluster_name" {
  value = module.ecs.cluster_name
}

output "database_url_secret_arn" {
  value = aws_secretsmanager_secret.database_url.arn
}

output "auth_tokens_secret_arn" {
  value = module.secrets.auth_tokens_secret_arn
}
