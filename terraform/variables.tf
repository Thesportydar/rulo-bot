variable "project" {
  type = string
}

variable "env" {
  type = string
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "profile" {
  description = "Perfil SSO que puede asumir terraform_role_arn (TerraformAdmin)"
  type        = string
  default     = "terraform-admin"
}

variable "terraform_role_arn" {
  type = string
}

variable "telegram_chat_id" {
  type = string
}

variable "schedule_expression" {
  description = "Cron en hora de Argentina: cada 2 min, lunes a viernes de 11 a 17"
  type        = string
  default     = "cron(0/2 11-16 ? * MON-FRI *)"
}

variable "schedule_enabled" {
  type    = bool
  default = true
}

variable "log_retention_days" {
  type    = number
  default = 14
}
