terraform {
  backend "s3" {
    bucket         = "my-unique-tfstate-bucket"
    key            = "global/s3/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "my-tfstate-lock"
    encrypt        = true
  }
}