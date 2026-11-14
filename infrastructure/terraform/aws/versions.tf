# The AWS reference path (spec F.2; DEL-06; ADR-0085). **Validate only: never applied, no AWS account used.**
# `terraform fmt -check`, `init -backend=false` and `validate` run in CI and in scripts\terraform_check.ps1.
terraform {
  required_version = ">= 1.17.1, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "6.71.0"
    }
  }

  # A real deployment keeps state remotely, encrypted and locked; the bucket is the customer's (docs/teardown.md).
  # backend "s3" {}
}

provider "aws" {
  region = var.region

  default_tags {
    tags = local.tags
  }
}

locals {
  name = "loyalty-${var.environment}"
  tags = {
    project     = "loyalty-support-modernization"
    environment = var.environment
    data        = "synthetic"
    owner       = var.owner_tag
    managed_by  = "terraform"
  }
}
