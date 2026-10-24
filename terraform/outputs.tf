output "function_name" {
  value = aws_lambda_function.monitor.function_name
}

output "state_table" {
  value = aws_dynamodb_table.state.name
}

output "telegram_token_param" {
  value = aws_ssm_parameter.telegram_token.name
}
