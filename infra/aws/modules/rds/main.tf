variable "name_prefix" {
  type = string
}

variable "region" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "db_subnet_group_name" {
  type = string
}

variable "private_subnet_cidrs" {
  type        = list(string)
  description = "CIDR blocks allowed to reach Postgres (ECS private subnets)."
}

variable "instance_class" {
  type    = string
  default = "db.t4g.medium"
}

variable "allocated_storage" {
  type    = number
  default = 50
}

variable "backup_retention_days" {
  type    = number
  default = 7
}

variable "db_username" {
  type = string
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "tags" {
  type    = map(string)
  default = {}
}

resource "aws_security_group" "rds" {
  name        = "${var.name_prefix}-${var.region}-rds"
  description = "Allow Postgres from Ghost Fabric ECS tasks only."
  vpc_id      = var.vpc_id

  ingress {
    description = "Postgres from private application subnets"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = var.private_subnet_cidrs
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-${var.region}-rds-sg"
  })
}

resource "aws_db_parameter_group" "postgres16" {
  name   = "${var.name_prefix}-${var.region}-pg16"
  family = "postgres16"

  parameter {
    name  = "log_min_duration_statement"
    value = "1000"
  }

  tags = var.tags
}

resource "aws_db_instance" "audit" {
  identifier     = "${var.name_prefix}-${var.region}-audit"
  engine         = "postgres"
  engine_version = "16"

  instance_class        = var.instance_class
  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.allocated_storage * 2
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = "ghost_fabric"
  username = var.db_username
  password = var.db_password

  db_subnet_group_name   = var.db_subnet_group_name
  vpc_security_group_ids = [aws_security_group.rds.id]
  parameter_group_name   = aws_db_parameter_group.postgres16.name
  publicly_accessible    = false
  multi_az               = false

  backup_retention_period   = var.backup_retention_days
  backup_window             = "03:00-04:00"
  maintenance_window        = "sun:04:00-sun:05:00"
  deletion_protection       = true
  skip_final_snapshot       = false
  final_snapshot_identifier = "${var.name_prefix}-${var.region}-audit-final"

  copy_tags_to_snapshot = true
  apply_immediately     = false

  tags = merge(var.tags, {
    Name    = "${var.name_prefix}-${var.region}-audit-db"
    Purpose = "durable-append-only-audit"
  })
}

output "endpoint" {
  value = aws_db_instance.audit.address
}

output "port" {
  value = aws_db_instance.audit.port
}

output "db_name" {
  value = aws_db_instance.audit.db_name
}

output "security_group_id" {
  value = aws_security_group.rds.id
}

output "arn" {
  value = aws_db_instance.audit.arn
}
