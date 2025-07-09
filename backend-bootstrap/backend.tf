terraform {
  required_version = ">= 1.3"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  default = "us-east-1"
}

# Create S3 bucket for Terraform state storage
resource "aws_s3_bucket" "tf_state" {
  bucket = "myapp-terraform-state-${random_string.suffix.result}"
  acl    = "private"

  versioning {
    enabled = true
  }

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "random_string" "suffix" {
  length  = 6
  upper   = false
  special = false
}

# Create DynamoDB table for state locking
resource "aws_dynamodb_table" "tf_lock" {
  name         = "terraform-lock-table"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }
}

output "s3_bucket" {
  value = aws_s3_bucket.tf_state.id
}

output "dynamodb_table" {
  value = aws_dynamodb_table.tf_lock.name
}