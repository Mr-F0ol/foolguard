variable "app_id" {
  description = "ID da aplicação no FoolGuard"
  type        = number
}

variable "image_uri" {
  description = "URI completa da imagem Docker no ECR (ex: 123456.dkr.ecr.us-east-1.amazonaws.com/foolguard-app-1:latest)"
  type        = string
}

variable "region" {
  description = "Região AWS onde os recursos serão criados"
  type        = string
  default     = "us-east-1"
}
