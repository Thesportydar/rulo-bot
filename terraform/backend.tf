terraform {
  backend "s3" {
    key = "rulo-bot/terraform.tfstate"
  }
}
