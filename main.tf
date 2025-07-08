terraform {
  required_version = ">= 1.3.0"

  backend "s3" {
    bucket         = "REPLACE_THIS_ON_FIRST_DEPLOY"
    key            = "terraform/state/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "tfstate-lock"
    encrypt        = true
  }
}