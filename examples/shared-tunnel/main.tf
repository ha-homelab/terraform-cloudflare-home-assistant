terraform {
  required_version = ">= 1.7.0"
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = ">= 5.13.0, < 6.0.0"
    }
  }
}

provider "cloudflare" {}
variable "account_id" { type = string }
variable "zone_id" { type = string }
variable "tunnel_id" { type = string }
variable "hostname" { type = string }
variable "origin_service" { type = string }

module "home_assistant" {
  source         = "../../modules/publication"
  account_id     = var.account_id
  zone_id        = var.zone_id
  tunnel_id      = var.tunnel_id
  hostname       = var.hostname
  origin_service = var.origin_service
}

# Insert this output into the existing owner's ordered ingress list.
# This example deliberately creates no competing tunnel-config resource.
output "home_assistant_ingress" {
  value = module.home_assistant.ingress_rule
}
