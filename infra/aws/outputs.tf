output "pilot_endpoints" {
  description = "ALB DNS names for each pilot region. HTTPS termination is a follow-up."
  value = {
    "us-east-1"      = module.us_east_1.alb_dns_name
    "eu-west-1"      = module.eu_west_1.alb_dns_name
    "ap-southeast-1" = module.ap_southeast_1.alb_dns_name
  }
}

output "ecr_repositories" {
  description = "Per-region ECR repositories for API and web images."
  value = {
    "us-east-1" = {
      api = module.us_east_1.api_repository_url
      web = module.us_east_1.web_repository_url
    }
    "eu-west-1" = {
      api = module.eu_west_1.api_repository_url
      web = module.eu_west_1.web_repository_url
    }
    "ap-southeast-1" = {
      api = module.ap_southeast_1.api_repository_url
      web = module.ap_southeast_1.web_repository_url
    }
  }
}

output "rds_endpoints" {
  description = "Private RDS endpoints for durable audit storage."
  value = {
    "us-east-1"      = module.us_east_1.rds_endpoint
    "eu-west-1"      = module.eu_west_1.rds_endpoint
    "ap-southeast-1" = module.ap_southeast_1.rds_endpoint
  }
}

output "secret_arns" {
  description = "Secrets Manager ARNs (no secret values)."
  value = {
    "us-east-1" = {
      database_url = module.us_east_1.database_url_secret_arn
      auth_tokens  = module.us_east_1.auth_tokens_secret_arn
    }
    "eu-west-1" = {
      database_url = module.eu_west_1.database_url_secret_arn
      auth_tokens  = module.eu_west_1.auth_tokens_secret_arn
    }
    "ap-southeast-1" = {
      database_url = module.ap_southeast_1.database_url_secret_arn
      auth_tokens  = module.ap_southeast_1.auth_tokens_secret_arn
    }
  }
}

output "safety_notice" {
  value = "Simulation pilot only. Human approval required. Not a multi-region failover mesh — regions are independent pilot footprints."
}
