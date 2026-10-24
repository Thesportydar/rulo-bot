terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.50.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.7"
    }
  }

  required_version = ">= 1.14"
}
