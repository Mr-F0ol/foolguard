output "app_url" {
  description = "URL pública da aplicação deployada"
  value       = "http://${aws_lb.app.dns_name}"
}

output "ecr_repository_url" {
  description = "URL do repositório ECR"
  value       = aws_ecr_repository.app.repository_url
}

output "ecs_cluster" {
  description = "Nome do cluster ECS"
  value       = aws_ecs_cluster.foolguard.name
}
