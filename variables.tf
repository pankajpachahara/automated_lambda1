# variables.tf

variable "source_code_hash" {
  description = "SHA256 hash of the Lambda function's source code for integrity checks and deployments."
  type        = string
  # No default value needed, as it will be passed via CI/CD (GitHub Actions)
}

variable "project_name" {
  description = "The name of the project, used for naming resources."
  type        = string
  default     = "pankaj-devops-lambda" # You can change this default if you like
}

variable "environment" {
  description = "The deployment environment (e.g., dev, prod)."
  type        = string
  default     = "dev" # You can change this default if you like
}

variable "aws_region" {
  description = "The AWS region to deploy resources into."
  type        = string
  default     = "ap-south-1" # Ensure this matches your desired region
}