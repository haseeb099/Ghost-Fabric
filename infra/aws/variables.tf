variable "project_name" {
  type        = string
  description = "Short project name used in resource naming."
  default     = "ghost-fabric"
}

variable "environment" {
  type        = string
  description = "Deployment environment label."
  default     = "pilot"
}

variable "owner" {
  type        = string
  description = "Owner tag for cost and contact tracking."
  default     = "ghost-fabric-ops"
}

variable "vpc_cidr_blocks" {
  type        = map(string)
  description = "Per-region VPC CIDR blocks. Must not overlap if peering is added later."
  default = {
    "us-east-1"      = "10.10.0.0/16"
    "eu-west-1"      = "10.20.0.0/16"
    "ap-southeast-1" = "10.30.0.0/16"
  }
}

variable "api_image_tag" {
  type        = string
  description = "Container image tag for the API service."
  default     = "latest"
}

variable "web_image_tag" {
  type        = string
  description = "Container image tag for the web console."
  default     = "latest"
}

variable "api_cpu" {
  type        = number
  description = "Fargate CPU units for the API task."
  default     = 512
}

variable "api_memory" {
  type        = number
  description = "Fargate memory (MiB) for the API task."
  default     = 1024
}

variable "web_cpu" {
  type        = number
  description = "Fargate CPU units for the web task."
  default     = 256
}

variable "web_memory" {
  type        = number
  description = "Fargate memory (MiB) for the web task."
  default     = 512
}

variable "db_instance_class" {
  type        = string
  description = "RDS instance class for the durable audit database."
  default     = "db.t4g.medium"
}

variable "db_allocated_storage" {
  type        = number
  description = "Allocated storage (GiB) for RDS."
  default     = 50
}

variable "db_backup_retention_days" {
  type        = number
  description = "Automated backup retention for RDS."
  default     = 7
}

variable "auth_mode" {
  type        = string
  description = "Ghost Fabric AUTH_MODE for the pilot API."
  default     = "required"
}

variable "desired_count" {
  type        = number
  description = "Desired ECS service task count per region."
  default     = 1
}

variable "enable_nat_gateway" {
  type        = bool
  description = "Create a NAT gateway for private subnet egress (required for Fargate pulls without VPC endpoints)."
  default     = true
}
