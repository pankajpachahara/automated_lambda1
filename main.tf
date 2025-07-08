terraform {
  backend "s3" {
    bucket         = "my-tfstate-bucket-${var.aws_account_id}"
    key            = "state/terraform.tfstate"
    region         = var.aws_region
    dynamodb_table = "my-tfstate-lock-${var.aws_account_id}"
    encrypt        = true
  }
}