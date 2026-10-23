# The parent owns the complete ordered tunnel config. A tunnel config is not a
# per-route resource: two configs for one tunnel would overwrite each other.
locals {
  ingress_rule = {
    hostname       = var.hostname
    service        = var.origin_service
    origin_request = {}
  }
  callback_domain = "${var.hostname}/api/notify.html5/callback"
}

resource "cloudflare_dns_record" "home_assistant" {
  zone_id = var.zone_id
  name    = var.hostname
  type    = "CNAME"
  content = "${var.tunnel_id}.cfargotunnel.com"
  ttl     = 1
  proxied = true
  comment = var.dns_comment
}

resource "cloudflare_zero_trust_access_application" "notification_callback" {
  count = var.callback_access == null ? 0 : 1

  account_id       = var.account_id
  name             = var.callback_access.name
  type             = "self_hosted"
  domain           = local.callback_domain
  session_duration = var.callback_access.session_duration
  destinations     = [{ type = "public", uri = local.callback_domain }]

  auto_redirect_to_identity  = var.callback_access.auto_redirect_to_identity
  enable_binding_cookie      = var.callback_access.enable_binding_cookie
  options_preflight_bypass   = var.callback_access.options_preflight_bypass
  http_only_cookie_attribute = var.callback_access.http_only_cookie_attribute

  policies = [for index, id in var.callback_access.policy_ids : {
    id         = id
    precedence = index + 1
  }]

  lifecycle {
    # Cloudflare derives this field from destinations. Do not fight that value.
    ignore_changes = [self_hosted_domains]
  }
}
