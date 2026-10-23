# Architecture and ownership

[README](../README.md) · [Configuration](configuration.md) · [Adoption](adoption.md)

![Terraform control path and application traffic, with explicit public/private boundaries.](publication.svg)

## Two separate paths

**Provisioning:** public Terraform code plus private installation inputs calls
the Cloudflare API. The dedicated root creates a remotely managed tunnel, its
ordered ingress configuration and a proxied CNAME. The API credential is needed
only by the Terraform operator. Configuration and resource identifiers are
recorded in private Terraform state.

**Runtime:** a client opens the public HTTPS hostname. Cloudflare forwards the
request over a tunnel connection established outbound by `cloudflared`. The
connector reaches the configured HA origin. It uses its own tunnel token, not the
Terraform API token. HA authenticates users and serves its UI, APIs and WebSockets.
Cloudflare terminates public TLS and is part of the trust boundary. The default
connector-to-HA hop is HTTP; keep it on an appropriate trusted network or configure
a correctly verified HTTPS origin.

The Terraform process does not need to run while users access HA. The connector,
HA and their network paths do. A tunnel removes the need for an inbound router
port forward for this route; it does not secure other existing paths to HA.

## What is owned where

- **Public Git:** reusable HCL, synthetic tests, example values, documentation and
  workflow definitions. No installation inventory or deployment credentials.
- **Private deployment:** actual inputs, state, saved plans and backups. One
  operator/workspace owns each resource. Limit access even if no secret appears
  in the console output.
- **Cloudflare:** DNS, tunnel configuration and any explicitly enabled callback
  Access application. Identity policies and the account itself remain outside
  this module.
- **Your runtime:** connector lifecycle, token storage, HA configuration,
  availability, logs and upgrades. This repository provisions no VM or container.

## One configuration per tunnel

A tunnel configuration is a complete ordered list, not independently merged route
objects. The dedicated root owns that list and ends it with a 404 catch-all. Do
not point another tunnel-config resource at the same tunnel.

For shared tunnels, use only the publication submodule. It returns the HA rule to
the current owner, which places it among existing routes. Preserve more-specific
rules, existing origin options, WARP settings and the final catch-all. Publication
can then evolve without silently replacing unrelated routes.

## Authentication choices

The default has no Cloudflare Access login layer. The public hostname reaches the
HA login page. Protect HA accounts, keep HA updated, and restrict unintended
direct origin access. The optional notification callback application is a narrow
integration surface with existing policies; it is not a whole-site security layer.

Whole-site Access, service-token support for clients, high availability, device
posture controls and custom origin TLS settings require deliberate additional
design. They are not silently enabled here.

## What testing establishes

Mock-provider tests validate Terraform behavior and resource contracts without an
account. Real provider schema validation catches unsupported resource arguments.
They cannot establish runtime connectivity, Cloudflare account entitlements,
real-policy decisions, successful notification delivery or recoverability of your
private state. The [runbook](runbook.md) supplies the live acceptance and recovery
checks for your installation.
