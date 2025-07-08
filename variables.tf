# S3 backend bucket
resource "aws_s3_bucket" "tfstate" {
  bucket = "tfstate-bucket-nodejs-lambda"

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

  block_public_access {
    block_public_acls       = true
    block_public_policy     = true
    ignore_public_acls      = true
    restrict_public_buckets = true
  }

  force_destroy = true
}

# DynamoDB Table for locking
resource "aws_dynamodb_table" "tfstate_lock" {
  name         = "tfstate-lock-nodejs-lambda"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }
}