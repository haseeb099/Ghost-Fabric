module "us_east_1" {
  source = "./modules/region"

  providers = {
    aws = aws.us_east_1
  }

  name_prefix              = local.name_prefix
  region                   = "us-east-1"
  vpc_cidr                 = var.vpc_cidr_blocks["us-east-1"]
  enable_nat_gateway       = var.enable_nat_gateway
  api_image_tag            = var.api_image_tag
  web_image_tag            = var.web_image_tag
  api_cpu                  = var.api_cpu
  api_memory               = var.api_memory
  web_cpu                  = var.web_cpu
  web_memory               = var.web_memory
  db_instance_class        = var.db_instance_class
  db_allocated_storage     = var.db_allocated_storage
  db_backup_retention_days = var.db_backup_retention_days
  auth_mode                = var.auth_mode
  desired_count            = var.desired_count
  tags                     = local.common_tags
}

module "eu_west_1" {
  source = "./modules/region"

  providers = {
    aws = aws.eu_west_1
  }

  name_prefix              = local.name_prefix
  region                   = "eu-west-1"
  vpc_cidr                 = var.vpc_cidr_blocks["eu-west-1"]
  enable_nat_gateway       = var.enable_nat_gateway
  api_image_tag            = var.api_image_tag
  web_image_tag            = var.web_image_tag
  api_cpu                  = var.api_cpu
  api_memory               = var.api_memory
  web_cpu                  = var.web_cpu
  web_memory               = var.web_memory
  db_instance_class        = var.db_instance_class
  db_allocated_storage     = var.db_allocated_storage
  db_backup_retention_days = var.db_backup_retention_days
  auth_mode                = var.auth_mode
  desired_count            = var.desired_count
  tags                     = local.common_tags
}

module "ap_southeast_1" {
  source = "./modules/region"

  providers = {
    aws = aws.ap_southeast_1
  }

  name_prefix              = local.name_prefix
  region                   = "ap-southeast-1"
  vpc_cidr                 = var.vpc_cidr_blocks["ap-southeast-1"]
  enable_nat_gateway       = var.enable_nat_gateway
  api_image_tag            = var.api_image_tag
  web_image_tag            = var.web_image_tag
  api_cpu                  = var.api_cpu
  api_memory               = var.api_memory
  web_cpu                  = var.web_cpu
  web_memory               = var.web_memory
  db_instance_class        = var.db_instance_class
  db_allocated_storage     = var.db_allocated_storage
  db_backup_retention_days = var.db_backup_retention_days
  auth_mode                = var.auth_mode
  desired_count            = var.desired_count
  tags                     = local.common_tags
}
