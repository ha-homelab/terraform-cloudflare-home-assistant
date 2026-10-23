# Credentials come from CLOUDFLARE_API_TOKEN; never commit a credential file.
provider "cloudflare" {}

resource "cloudflare_zero_trust_tunnel_cloudflared" "home_assistant" {
  account_id = var.account_id
  name       = "home-assistant-${var.hostname}"
  config_src = "cloudflare"
}

module "publication" {
  source          = "./modules/publication"
  account_id      = var.account_id
  zone_id         = var.zone_id
  tunnel_id       = cloudflare_zero_trust_tunnel_cloudflared.home_assistant.id
  hostname        = var.hostname
  origin_service  = var.origin_service
  dns_comment     = var.dns_comment
  callback_access = var.callback_access
}

resource "cloudflare_zero_trust_tunnel_cloudflared_config" "home_assistant" {
  account_id = var.account_id
  tunnel_id  = cloudflare_zero_trust_tunnel_cloudflared.home_assistant.id
  config = {
    # Keep the nested shape explicit: provider validation needs to see the
    # required service attribute even while module outputs are still unknown.
    ingress = [{
      hostname       = module.publication.ingress_rule.hostname
      service        = module.publication.ingress_rule.service
      origin_request = module.publication.ingress_rule.origin_request
    }, { service = "http_status:404" }]
    warp_routing = { enabled = false }
  }
}
