terraform {
  backend "s3" {
    bucket = "tfstate-bucket-unique-name" # Replace with a globally unique name
    key    = "terraform.tfstate"
    region = "us-west-2" # Replace with your desired region
    dynamodb_table = "tfstate-lock-table-unique-name" # Replace with a globally unique name
    encrypt        = true
  }
}