mock_provider "cloudflare" {}

variables {
  account_id     = "00000000000000000000000000000000"
  zone_id        = "11111111111111111111111111111111"
  tunnel_id      = "11111111-2222-4333-8444-555555555555"
  hostname       = "ha.example.invalid"
  origin_service = "http://home-assistant:8123"
}

run "existing_tunnel_route" {
  command = plan
  assert {
    condition     = output.home_assistant_ingress.hostname == "ha.example.invalid" && output.home_assistant_ingress.service == "http://home-assistant:8123"
    error_message = "The shared-tunnel consumer must expose its selected route for the existing config owner."
  }
  assert {
    condition     = module.home_assistant.callback_application_id == null
    error_message = "The shared-tunnel example must not add an Access boundary implicitly."
  }
}
