locals {
  name = "${var.project}-${var.env}"
}

data "archive_file" "lambda" {
  type        = "zip"
  output_path = "${path.module}/.build/lambda.zip"

  source {
    content  = file("${path.module}/../config.toml")
    filename = "config.toml"
  }

  dynamic "source" {
    for_each = fileset("${path.module}/../rulo", "**/*.py")
    content {
      content  = file("${path.module}/../rulo/${source.value}")
      filename = "rulo/${source.value}"
    }
  }
}

# --- estado ---

resource "aws_dynamodb_table" "state" {
  name         = "${local.name}-state"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"

  attribute {
    name = "pk"
    type = "S"
  }
}

# --- secreto: el valor real se carga a mano para que no quede en el tfstate ---
#   aws ssm put-parameter --overwrite --type SecureString --name <nombre> --value <token>

resource "aws_ssm_parameter" "telegram_token" {
  name  = "/${var.project}/${var.env}/telegram-bot-token"
  type  = "SecureString"
  value = "placeholder"

  lifecycle {
    ignore_changes = [value]
  }
}

# --- lambda ---

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.name}"
  retention_in_days = var.log_retention_days
}

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${local.name}-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "lambda" {
  statement {
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.lambda.arn}:*"]
  }
  statement {
    actions   = ["dynamodb:GetItem", "dynamodb:PutItem"]
    resources = [aws_dynamodb_table.state.arn]
  }
  statement {
    actions   = ["ssm:GetParameter"]
    resources = [aws_ssm_parameter.telegram_token.arn]
  }
}

resource "aws_iam_role_policy" "lambda" {
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda.json
}

resource "aws_lambda_function" "monitor" {
  function_name    = local.name
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.13"
  architectures    = ["arm64"]
  handler          = "rulo.lambda_handler.handler"
  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256
  memory_size      = 128
  timeout          = 60

  environment {
    variables = {
      RULO_STATE_TABLE         = aws_dynamodb_table.state.name
      TELEGRAM_BOT_TOKEN_PARAM = aws_ssm_parameter.telegram_token.name
      TELEGRAM_CHAT_ID         = var.telegram_chat_id
    }
  }

  depends_on = [aws_cloudwatch_log_group.lambda, aws_iam_role_policy.lambda]
}

# --- schedule ---

data "aws_iam_policy_document" "scheduler_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "${local.name}-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume.json
}

resource "aws_iam_role_policy" "scheduler" {
  role = aws_iam_role.scheduler.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = aws_lambda_function.monitor.arn
    }]
  })
}

resource "aws_scheduler_schedule" "monitor" {
  name                         = local.name
  schedule_expression          = var.schedule_expression
  schedule_expression_timezone = "America/Argentina/Buenos_Aires"
  state                        = var.schedule_enabled ? "ENABLED" : "DISABLED"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.monitor.arn
    role_arn = aws_iam_role.scheduler.arn

    retry_policy {
      # la próxima corrida llega en 2 minutos, no tiene sentido reintentar
      maximum_retry_attempts       = 0
      maximum_event_age_in_seconds = 60
    }
  }
}

resource "aws_scheduler_schedule" "summary" {
  name                         = "${local.name}-summary"
  schedule_expression          = var.summary_schedule_expression
  schedule_expression_timezone = "America/Argentina/Buenos_Aires"
  state                        = var.schedule_enabled ? "ENABLED" : "DISABLED"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.monitor.arn
    role_arn = aws_iam_role.scheduler.arn
    input    = jsonencode({ args = ["--summary"] })

    retry_policy {
      maximum_retry_attempts       = 2
      maximum_event_age_in_seconds = 600
    }
  }
}
