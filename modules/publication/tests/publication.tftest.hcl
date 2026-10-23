mock_provider "cloudflare" {}

variables {
  account_id     = "00000000000000000000000000000000"
  zone_id        = "11111111111111111111111111111111"
  tunnel_id      = "11111111-2222-4333-8444-555555555555"
  hostname       = "ha.example.invalid"
  origin_service = "http://127.0.0.1:8123"
}

run "native_auth_and_route" {
  command = plan
  assert {
    condition     = cloudflare_dns_record.home_assistant.proxied && cloudflare_dns_record.home_assistant.ttl == 1 && cloudflare_dns_record.home_assistant.content == "11111111-2222-4333-8444-555555555555.cfargotunnel.com"
    error_message = "DNS must use the supplied tunnel with Cloudflare proxy enabled."
  }
  assert {
    condition     = output.ingress_rule.hostname == "ha.example.invalid" && output.ingress_rule.service == "http://127.0.0.1:8123" && length(output.ingress_rule.origin_request) == 0
    error_message = "The HA route must preserve the explicitly supplied origin and TLS defaults."
  }
  assert {
    condition     = length(cloudflare_zero_trust_access_application.notification_callback) == 0 && output.callback_application_id == null
    error_message = "Access policies must never be created implicitly."
  }
}

run "callback_is_path_scoped_and_keeps_policy_order" {
  command = plan
  variables {
    hostname       = "automation.example.invalid"
    origin_service = "https://origin.example.invalid:8443"
    callback_access = {
      name       = "notification-callback"
      policy_ids = ["22222222-2222-4222-8222-222222222222", "33333333-3333-4333-8333-333333333333"]
    }
  }
  assert {
    condition     = cloudflare_zero_trust_access_application.notification_callback[0].domain == "automation.example.invalid/api/notify.html5/callback" && cloudflare_zero_trust_access_application.notification_callback[0].destinations[0].uri == output.callback_domain
    error_message = "Notification rules must stay on the callback path rather than the entire HA site."
  }
  assert {
    condition     = cloudflare_zero_trust_access_application.notification_callback[0].policies[0].id == "22222222-2222-4222-8222-222222222222" && cloudflare_zero_trust_access_application.notification_callback[0].policies[1].precedence == 2
    error_message = "Policy identity and precedence must be retained."
  }
}

run "reject_wildcard" {
  command = plan
  variables { hostname = "*.example.invalid" }
  expect_failures = [var.hostname]
}

run "reject_origin_credentials" {
  command = plan
  variables { origin_service = "https://user:password@origin.example.invalid" }
  expect_failures = [var.origin_service]
}

run "reject_origin_path" {
  command = plan
  variables { origin_service = "https://origin.example.invalid/admin" }
  expect_failures = [var.origin_service]
}

run "reject_empty_callback_policy" {
  command = plan
  variables { callback_access = { policy_ids = [] } }
  expect_failures = [var.callback_access]
}

run "reject_duplicate_callback_policies" {
  command = plan
  variables { callback_access = { policy_ids = ["22222222-2222-4222-8222-222222222222", "22222222-2222-4222-8222-222222222222"] } }
  expect_failures = [var.callback_access]
}

run "reject_port_zero" {
  command = plan
  variables { origin_service = "http://localhost:0" }
  expect_failures = [var.origin_service]
}

run "reject_port_above_65535" {
  command = plan
  variables { origin_service = "http://localhost:65536" }
  expect_failures = [var.origin_service]
}

run "allow_highest_port_and_valid_ipv6" {
  command = plan
  variables { origin_service = "https://[2001:db8::1]:65535" }
  assert {
    condition     = output.ingress_rule.service == "https://[2001:db8::1]:65535"
    error_message = "Valid IPv6 and the maximum TCP port must be accepted."
  }
}

run "reject_invalid_ipv6" {
  command = plan
  variables { origin_service = "http://[::::]:8123" }
  expect_failures = [var.origin_service]
}

run "reject_empty_dns_label" {
  command = plan
  variables { origin_service = "http://home..assistant:8123" }
  expect_failures = [var.origin_service]
}

run "reject_label_with_edge_hyphen" {
  command = plan
  variables { origin_service = "http://home.-assistant:8123" }
  expect_failures = [var.origin_service]
}

run "reject_query" {
  command = plan
  variables { origin_service = "http://home-assistant:8123?token=example" }
  expect_failures = [var.origin_service]
}

run "reject_fragment" {
  command = plan
  variables { origin_service = "http://home-assistant:8123#example" }
  expect_failures = [var.origin_service]
}
