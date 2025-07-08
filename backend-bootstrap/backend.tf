variable "region" {
  description = "AWS Region"
  type        = string
  default     = "us-east-1"
}

variable "lambda_function_name" {
  description = "Name of the Lambda function"
  type        = string
  default     = "nodejs-app"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "List of CIDR blocks for public subnets"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "alb_name" {
  default     = "nodejs-alb"
  description = "Name for our ALB"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"
}