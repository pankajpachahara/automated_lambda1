module "backend_bootstrap" {
  source = "./backend-bootstrap"
  providers = {
    aws = aws
  }
}

provider "aws" {
  region = var.region
}

resource "aws_dynamodb_table" "tfstate_lock" {
  name           = module.backend_bootstrap.dynamodb_table_name
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "LockID"
  attribute {
    name = "LockID"
    type = "S"
  }
}

resource "aws_s3_bucket" "tfstate_bucket" {
  bucket = module.backend_bootstrap.s3_bucket_name
  acl    = "private"

 # Enable server-side encryption
  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }

  versioning {
    enabled = true
  }

 lifecycle {
    prevent_destroy = true
  }
}

# ... rest of your infrastructure (VPC, subnets, lambda, ALB etc.)
# will be added to this file.