mock_provider "cloudflare" {
  mock_resource "cloudflare_zero_trust_tunnel_cloudflared" {
    defaults = { id = "11111111-2222-4333-8444-555555555555" }
  }
}

variables {
  account_id = "00000000000000000000000000000000"
  zone_id    = "11111111111111111111111111111111"
  hostname   = "ha.example.invalid"
}

run "complete_installation_from_three_inputs" {
  command = apply
  assert {
    condition     = cloudflare_zero_trust_tunnel_cloudflared.home_assistant.config_src == "cloudflare"
    error_message = "The installation must create a remotely managed tunnel."
  }
  assert {
    condition     = length(cloudflare_zero_trust_tunnel_cloudflared_config.home_assistant.config.ingress) == 2 && cloudflare_zero_trust_tunnel_cloudflared_config.home_assistant.config.ingress[0].service == "http://127.0.0.1:8123" && cloudflare_zero_trust_tunnel_cloudflared_config.home_assistant.config.ingress[1].service == "http_status:404"
    error_message = "Default installation must reach HA, then deny every other hostname."
  }
  assert {
    condition     = output.url == "https://ha.example.invalid" && cloudflare_zero_trust_tunnel_cloudflared_config.home_assistant.tunnel_id == output.tunnel_id
    error_message = "Tunnel identity must be connected consistently."
  }
  assert {
    condition     = cloudflare_zero_trust_tunnel_cloudflared_config.home_assistant.config.ingress[0].hostname == "ha.example.invalid" && cloudflare_zero_trust_tunnel_cloudflared_config.home_assistant.config.ingress[1].hostname == null && module.publication.callback_application_id == null
    error_message = "Only the requested hostname may reach HA; callback Access must remain opt-in."
  }
}

run "different_origin" {
  command = plan
  variables { origin_service = "http://home-assistant:8123" }
  assert {
    condition     = cloudflare_zero_trust_tunnel_cloudflared_config.home_assistant.config.ingress[0].service == "http://home-assistant:8123"
    error_message = "Container-network origins must be configurable."
  }
}

run "ipv6_origin" {
  command = plan
  variables { origin_service = "http://[::1]:8123" }
  assert {
    condition     = cloudflare_zero_trust_tunnel_cloudflared_config.home_assistant.config.ingress[0].service == "http://[::1]:8123"
    error_message = "A valid IPv6 origin must be retained."
  }
}

run "root_rejects_port_out_of_range" {
  command = plan
  variables { origin_service = "http://localhost:65536" }
  expect_failures = [var.origin_service]
}

run "root_rejects_origin_credentials" {
  command = plan
  variables { origin_service = "https://user:password@origin.example.invalid" }
  expect_failures = [var.origin_service]
}
