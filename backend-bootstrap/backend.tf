resource "aws_s3_bucket" "terraform_state_bucket" {
  bucket = "pankaj-devops-lambda-tfstate-ea8d4e33"
  force_destroy = true

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
}

resource "aws_s3_bucket_public_access_block" "terraform_state_bucket_block" {
  bucket                  = aws_s3_bucket.terraform_state_bucket.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}


resource "aws_dynamodb_table" "terraform_lock_table" {
  name           = "pankaj-devops-lambda-tf-lock-ea8d4e33"
  billing_mode = "PAY_PER_REQUEST"
  hash_key      = "LockID"

 attribute {
    name = "LockID"
    type = "S"
  }
}

output "terraform_state_bucket_name" {
  value       = aws_s3_bucket.terraform_state_bucket.bucket
  description = "Name of the S3 bucket for Terraform state"
}

output "terraform_lock_table_name" {
  value       = aws_dynamodb_table.terraform_lock_table.name
  description = "Name of the DynamoDB table for Terraform state locking"
}