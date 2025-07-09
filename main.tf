variable "aws_region" {
  default = "us-east-1"
}

variable "state_bucket_name" {
  type        = string
  description = "The name of the S3 bucket for Terraform state"
}

variable "locktable_name" {
  type        = string
  description = "The name of the DynamoDB table for Terraform state lock"
}