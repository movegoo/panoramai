bucket         = "panoramai-prod-terraform-state"
key            = "panoramai/prod/terraform.tfstate"
region         = "eu-central-1"
dynamodb_table = "panoramai-prod-terraform-lock"
encrypt        = true
