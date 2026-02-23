variable "env" {
  description = "Environment name (dev or prod)"
  type        = string
  validation {
    condition     = contains(["dev", "prod"], var.env)
    error_message = "env must be 'dev' or 'prod'"
  }
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "eu-central-1"
}

variable "project" {
  description = "Project name"
  type        = string
  default     = "panoramai"
}

variable "db_username" {
  description = "RDS master username"
  type        = string
  default     = "panoramai"
}

variable "db_password" {
  description = "RDS master password"
  type        = string
  sensitive   = true
}

variable "container_port" {
  description = "Port the container listens on"
  type        = number
  default     = 8000
}

variable "acm_certificate_arn" {
  description = "ACM certificate ARN for HTTPS on ALB"
  type        = string
  default     = ""
}

# ECS sizing per env
variable "ecs_cpu" {
  description = "ECS task CPU (in CPU units)"
  type        = number
  default     = 512 # 0.5 vCPU
}

variable "ecs_memory" {
  description = "ECS task memory (in MiB)"
  type        = number
  default     = 1024 # 1 GB
}

variable "ecs_desired_count" {
  description = "Number of ECS tasks"
  type        = number
  default     = 1
}
