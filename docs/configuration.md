# Configuration reference

[README](../README.md) · [Runbook](runbook.md) · [Adoption](adoption.md)

## Required installation values

- `account_id`: the lowercase 32-character hexadecimal Cloudflare account ID.
- `zone_id`: the lowercase 32-character hexadecimal ID of the active DNS zone.
- `hostname`: the exact lowercase fully qualified hostname, without scheme, port,
  path, trailing dot or wildcard. It must belong to the selected zone.

Terraform validates input shapes; only Cloudflare can confirm account membership,
permissions and zone ownership. The API token comes from `CLOUDFLARE_API_TOKEN`,
not from a Terraform variable. Account IDs are identifiers, not authentication
secrets, but remain private installation inventory in this project.

The root creates the dedicated tunnel and its complete configuration. Required
values are deliberately explicit: no personal account, zone or hostname is built in.

## Origin service

`origin_service` defaults to `http://127.0.0.1:8123`. It is an HTTP(S) authority
reachable by the connector, without credentials, path, query or fragment.

Examples for your **private** variable file:

```hcl
# Shared container network, with a service named home-assistant:
origin_service = "http://home-assistant:8123"
```

```hcl
# A different configured HA port on the connector's own host/network:
origin_service = "http://127.0.0.1:80"
```

```hcl
# An internal DNS name; replace this reserved example with your real origin:
origin_service = "https://ha.internal.example.invalid:8123"
```

Loopback is correct only when HA is reachable in the connector's network namespace.
For an HTTPS origin, its certificate must be valid and trusted, with a name matching
the configured host. The module does not disable TLS verification or offer origin
certificate overrides. Configure the origin appropriately before switching to HTTPS.

`dns_comment` defaults to `null`. If you add a comment, use a generic purpose
such as `Home Assistant publication`; metadata can appear in plans and logs.

## Optional notification callback Access

`callback_access` defaults to `null`: no Access application, no Access policy
change. Normal setup should keep this default.

For an existing notification setup that deliberately uses Cloudflare Access,
this object can attach **existing account policies** to the application path
`HOSTNAME/api/notify.html5/callback`. Policy decisions and membership remain with
the policy owner. The module does not create policies or infer their intent.

```hcl
# Synthetic policy ID. Supply your actual reviewed policy IDs privately.
callback_access = {
  policy_ids = ["00000000-0000-0000-0000-000000000001"]
}
```

Supported fields:

- `policy_ids`: required nonempty list of existing policy UUIDs, in precedence order.
- `name`: default `home-assistant-notification-callback`.
- `session_duration`: default `24h`.
- `auto_redirect_to_identity`: default `false`.
- `enable_binding_cookie`: default `false`.
- `options_preflight_bypass`: default `false`.
- `http_only_cookie_attribute`: default `false`.

Defaults are specific to this callback integration, not a recommended policy for
a whole application. No wildcard suffix is added, but Cloudflare's application
path matching and overlap precedence still apply. Review
[Cloudflare's path rules](https://developers.cloudflare.com/cloudflare-one/access-controls/policies/app-paths/)
and all overlapping applications. An Access policy can require a login, deny
traffic or bypass Access: the selected policy controls the result. An incorrect
choice can break background callbacks or create an unintended exception.

This option does not protect the HA dashboard and is not required for Companion
clients. Keep native HA authentication enabled. Test browser notification
registration and delivery after any callback policy change.

## Outputs

The dedicated root returns:

- `tunnel_id`: locate this tunnel in the dashboard and retrieve its token privately.
- `url`: the intended HTTPS URL; this is not a health check.
- `dns_record_id`: the managed DNS resource ID.

The publication submodule additionally takes an existing `tunnel_id`. Its
`origin_service` is mandatory. It returns `ingress_rule`, `dns_record_id`,
`callback_application_id` (`null` when disabled), and `callback_domain`.

Neither entry point retrieves or outputs a connector token. Outputs reveal
installation metadata, so treat logs containing them as private.
