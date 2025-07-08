provider "aws" {
  region = var.aws_region
}

terraform {
  required_version = ">= 1.0"
  backend "s3" {
    bucket         = "tfstate-bucket-nodejs-lambda" # Name will be created below
    key            = "terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "tfstate-lock-nodejs-lambda"
    encrypt        = true
  }
}