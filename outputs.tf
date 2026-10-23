output "tunnel_id" {
  description = "New tunnel ID. Retrieve its connector token privately from the Cloudflare dashboard."
  value       = cloudflare_zero_trust_tunnel_cloudflared.home_assistant.id
}

output "url" {
  description = "Home Assistant URL; available after the connector and HA reverse-proxy settings are configured."
  value       = "https://${var.hostname}"
}

output "dns_record_id" {
  value = module.publication.dns_record_id
}
