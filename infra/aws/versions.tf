terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Copy backend.hcl.example -> backend.hcl and pass -backend-config=backend.hcl
  # after the S3/DynamoDB bootstrap bucket exists. Apply stays manual.
  # backend "s3" {}
}
