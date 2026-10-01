variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "eu-north-1"
}

variable "project_name" {
  description = "Project prefix for resource naming"
  type        = string
  default     = "serverless-job-portal"
}

variable "admin_email" {
  description = "Email address to receive recruiter alerts"
  type        = string
  default     = "recruiter@example.com"
}
