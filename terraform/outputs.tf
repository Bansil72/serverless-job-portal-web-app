output "dynamodb_table_name" {
  description = "DynamoDB Table Name"
  value       = aws_dynamodb_table.applications.name
}

output "resume_bucket_name" {
  description = "Private S3 Bucket for Resume PDFs"
  value       = aws_s3_bucket.resumes.id
}

output "frontend_bucket_name" {
  description = "S3 Bucket for Frontend Hosting"
  value       = aws_s3_bucket.frontend.id
}

output "lambda_role_arn" {
  description = "IAM Role ARN for Lambda Execution"
  value       = aws_iam_role.lambda_role.arn
}
