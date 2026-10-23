# Troubleshooting

[README](../README.md) · [Runbook](runbook.md) · [Configuration](configuration.md)

Work from infrastructure to runtime: **plan → DNS → connector → origin → HA →
client**. Change one layer at a time. Keep diagnostic output private until account
IDs, hostnames, addresses, cookies and credentials are removed.

For installation and process failures, use the platform-specific guides:
[Linux / Windows / macOS](cloudflared-binaries.md) and
[Docker / k3s diagnostics](cloudflared-containers.md#container-and-cluster-troubleshooting).
For failed repository checks, see [CI](ci.md); CI does not deploy the connector
or authenticate to a live Cloudflare account.

## Terraform rejects the credentials or account

For 401/403 responses, check that the process running Terraform receives
`CLOUDFLARE_API_TOKEN`, that the token is valid, and that its account/zone scopes
match the three inputs. The tunnel and DNS permissions are separate. Callback
Access management adds an Access permission; basic setup does not need it.

An authentication error does not mean you should grant access to every account.
Confirm the intended resource scope before changing permissions. Never paste the
token into a public issue. A local credential-free test passing is unrelated to
whether your live token is authorized.

## A record already exists, or a plan wants to replace resources

Stop before applying. Confirm the DNS record, tunnel and optional Access
application each have one Terraform owner. Follow [adoption](adoption.md) to move
or import existing resources. Replacing a hostname or deleting a record merely to
clear the error can interrupt working access.

Unexpected route changes on a shared tunnel usually indicate a second owner or an
incomplete ingress list. Compare the full configuration, including route order,
origin options and the final catch-all, with the prior protected snapshot.

## The hostname does not resolve or HTTPS fails

Confirm the zone is active, the hostname belongs to it, and the managed DNS record
exists and is proxied. A proxied CNAME can resolve publicly as Cloudflare addresses;
not seeing the tunnel UUID in a DNS answer is not itself a failure.

Check certificate readiness for the exact hostname. Avoid adding hostname levels
that are not covered by your available certificate. DNS and public TLS failures
happen before HA login; changing HA passwords or proxy trust will not fix them.

## Cloudflare reports an unavailable tunnel

Confirm the expected connector is running and using the token for this tunnel.
Check its private service logs, local DNS and outbound network reachability.
If no connector is connected, diagnose that path before changing the HA origin.
Follow [Cloudflare's tunnel troubleshooting guide](https://developers.cloudflare.com/tunnel/troubleshooting/)
for transport-specific checks and required connectivity.

A healthy connector establishes the edge-to-connector path. It does not prove the
connector can reach HA.

## The tunnel is healthy, but the response is 502

From the **connector's network namespace**, verify the exact `origin_service`
host, port and protocol. Common mistakes are loopback in a separate container,
using a host-only service name, the wrong HA port, or sending HTTP to an HTTPS
listener. Check the origin certificate if HTTPS is configured. Do not disable
certificate verification to hide a name or trust error; fix the origin setup.

An HTTP response from HA confirms reachability even if it is not an authenticated
success. Use a read-only request; diagnostic testing need not call automations,
change entities or send an HA access token to unrelated tools.

## HA returns 400 or rejects the proxy

Inspect the source address HA sees and configure narrow proxy trust. Do not add
all internet addresses, all Cloudflare edge ranges, or an unrelated container
subnet by guesswork. Keep local access while changing the HTTP settings. The
[official HTTP reference](https://www.home-assistant.io/integrations/http/)
describes forwarded headers and trusted proxies.

## Login loops, stale dashboards or disconnected live updates

Check whether an existing Cloudflare Access application or redirect rule overlaps
the hostname. This module does not add a whole-site Access gate by default. Test a
fresh browser session and inspect failed WebSocket requests without sharing their
cookies or headers.

Custom caching rules must not cache HA HTML, service workers, `/api/`, `/auth/`, or
404 responses. Remove the conflicting cache rule and clear affected cached
responses. See [HA's reverse-proxy cache guidance](https://www.home-assistant.io/integrations/http/#caching-behind-a-reverse-proxy-or-cdn).

## A Companion client or notification callback fails

First confirm normal HA login and live updates. Check the client's external URL.
Browser HTML5 notifications and Companion push are different integrations; the
optional callback Access application is not a general push-notification fix.

If `callback_access` is enabled, inspect the selected policy decisions and
[overlapping application paths](https://developers.cloudflare.com/cloudflare-one/access-controls/policies/app-paths/).
An interactive Access login can block a background request. Do not add a whole-site
bypass to repair a single endpoint. Preserve HA's native authentication, service
worker assets and callback routes, then repeat registration and delivery tests.

## Get help with a safe reproduction

Include the Terraform and provider versions, the failing stage, a synthetic
configuration, and redacted error text. State whether you use the dedicated root
or the shared-tunnel module. For origin errors, describe the topology generically
(same host, separate container, or remote origin), not your real addresses.

Never attach state, saved plans, real variable files, connector commands containing
tokens, browser network archives or provider debug logs without a careful private
review. Report security issues using [the private process](../SECURITY.md).
