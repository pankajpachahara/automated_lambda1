variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "lambda_function_name" {
  description = "Name for Lambda function"
  type        = string
  default     = "nodejs-lambda-alb"
}

variable "vpc_cidr" {
  description = "VPC CIDR"
  default     = "10.0.0.0/16"
}

variable "private_subnets" {
  description = "Private subnet CIDRs"
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "public_subnets" {
  description = "Public subnet CIDRs"
  default     = ["10.0.101.0/24", "10.0.102.0/24"]
}

variable "allowed_ip" {
  description = "ALB access CIDR"
  default     = "0.0.0.0/0"
}