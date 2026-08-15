locals {
  regions = [
    "us-east-1",
    "eu-west-1",
    "ap-southeast-1",
  ]

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    Owner       = var.owner
    ManagedBy   = "terraform"
    Safety      = "simulation-pilot-only"
    Purpose     = "bounded-resilience-pilot"
  }

  name_prefix = "${var.project_name}-${var.environment}"
}
