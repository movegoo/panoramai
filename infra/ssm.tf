# SSM Parameter Store entries
# Secrets are created as placeholders — actual values set via AWS Console or CLI.

locals {
  # Secrets (SecureString) — placeholder values, update via:
  #   aws ssm put-parameter --name "/panoramai/<env>/KEY" --value "xxx" --type SecureString --overwrite
  secrets = [
    "DATABASE_URL",
    "JWT_SECRET",
    "META_APP_ID",
    "META_APP_SECRET",
    "META_ACCESS_TOKEN",
    "META_AD_LIBRARY_TOKEN",
    "YOUTUBE_API_KEY",
    "SCRAPECREATORS_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "OPENAI_API_KEY",
    "MISTRAL_API_KEY",
    "SEARCHAPI_KEY",
    "APIFY_API_KEY",
  ]

  # Config (String)
  config = {
    SCHEDULER_ENABLED        = var.env == "prod" ? "true" : "false"
    CORS_ORIGINS             = "https://panoramai-eight.vercel.app,https://panoramai.mobsuccess.ai"
    DATAGOUV_CACHE_DIR       = "/app/cache/datagouv"
    MCP_ALLOWED_HOSTS        = "api.panoramai.mobsuccess.ai"
    MS_AUTH_ENABLED          = var.env == "prod" ? "true" : "false"
    MS_LAMBDA_AUTHORIZER_URL = var.env == "prod" ? "https://33adhwcu4tz4sg7dbxl4qjlovu0ojjin.lambda-url.eu-central-1.on.aws/" : ""
  }
}

resource "aws_ssm_parameter" "secrets" {
  for_each = toset(local.secrets)

  name  = "/${var.project}/${var.env}/${each.key}"
  type  = "SecureString"
  value = "CHANGE_ME"

  tags = { Name = each.key }

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "config" {
  for_each = local.config

  name  = "/${var.project}/${var.env}/${each.key}"
  type  = "String"
  value = each.value

  tags = { Name = each.key }

  lifecycle {
    ignore_changes = [value]
  }
}
