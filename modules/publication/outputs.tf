output "ingress_rule" {
  description = "Insert after any more-specific routes, before the final catch-all, in the single owner of the tunnel config."
  value       = local.ingress_rule
}

output "dns_record_id" {
  description = "Managed Home Assistant DNS record ID."
  value       = cloudflare_dns_record.home_assistant.id
}

output "callback_application_id" {
  description = "Managed notification callback application ID, or null when disabled."
  value       = one(cloudflare_zero_trust_access_application.notification_callback[*].id)
}

output "callback_domain" {
  description = "Exact notification callback path; it is not a whole-site Access boundary."
  value       = local.callback_domain
}
