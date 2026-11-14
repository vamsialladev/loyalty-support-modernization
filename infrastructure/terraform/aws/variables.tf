variable "region" {
  description = "AWS region. Data residency: keep it in the customer's agreed region (docs/data-residency.md)."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "staging or production."
  type        = string
  default     = "staging"

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be staging or production."
  }
}

variable "owner_tag" {
  description = "Who answers for these resources (a team, not a person's email)."
  type        = string
  default     = "loyalty-support-platform"
}

variable "vpc_cidr" {
  description = "Address range for the VPC."
  type        = string
  default     = "10.40.0.0/16"
}

variable "domain_name" {
  description = "The public name for the console, whose ACM certificate is validated by DNS."
  type        = string
  default     = "loyalty.example.com"
}

variable "app_image" {
  description = "The app image, by digest (built and attested by CI)."
  type        = string
  default     = "public.ecr.aws/example/loyalty-app@sha256:0000000000000000000000000000000000000000000000000000000000000000"
}

variable "mock_api_image" {
  description = "The mock customer API image, by digest. A real deployment replaces it with the customer's system."
  type        = string
  default     = "public.ecr.aws/example/loyalty-mock-api@sha256:0000000000000000000000000000000000000000000000000000000000000000"
}

variable "monthly_budget_usd" {
  description = "Alarm when the month's spend is forecast past this (notifications only; AWS doesn't stop spending)."
  type        = number
  default     = 150
}

variable "budget_alert_email" {
  description = "Who gets the budget alarm. A team mailbox."
  type        = string
  default     = "platform-alerts@example.com"
}

variable "db_instance_class" {
  description = "RDS instance size."
  type        = string
  default     = "db.t4g.micro"
}
