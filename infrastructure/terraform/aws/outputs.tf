output "console_url" {
  description = "Where the console answers once DNS points at the load balancer and the certificate is validated."
  value       = "https://${var.domain_name}"
}

output "load_balancer_dns" {
  description = "The CNAME target for var.domain_name."
  value       = aws_lb.main.dns_name
}

output "certificate_validation" {
  description = "DNS records that validate the ACM certificate."
  value       = aws_acm_certificate.console.domain_validation_options
}

output "secrets_to_fill" {
  description = "Secrets Manager entries a person must fill before the services can start."
  value       = sort([for s in aws_secretsmanager_secret.app : s.name])
}

output "db_master_secret_arn" {
  description = "The RDS-managed owner credentials, for the migrate task only."
  value       = aws_db_instance.main.master_user_secret[0].secret_arn
  sensitive   = true
}
