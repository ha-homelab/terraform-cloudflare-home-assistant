# Documentation

Reusable Terraform that publishes an existing Home Assistant at a dedicated
HTTPS hostname through a Cloudflare Tunnel, with installation values kept
outside the public source.

## Understand the module

- [Architecture and ownership](architecture.md) — what Terraform creates, which parts stay under operator control and where the module's responsibility ends.
- [Configuration reference](configuration.md) — the input variables, defaults and the provider/state requirements.
- [Adopt an existing installation without replacing it](adoption.md) — importing an existing tunnel, DNS record and Access setup before the first apply.

## Install a connector

- [Run cloudflared as a native service](cloudflared-binaries.md) — installing cloudflared as a system service on the origin host.
- [Run cloudflared in Docker or k3s](cloudflared-containers.md) — container and k3s deployment of the connector with its configuration.

## Operate and verify

- [Install, verify, operate and recover](runbook.md) — the ordered setup, the acceptance checks that confirm the service works, and recovery steps.
- [Troubleshooting](troubleshooting.md) — symptoms seen at the edge, the connector and the HA origin, with the checks that separate them.

## Continuous integration

- [CI: validate the template, keep deployment under operator control](ci.md) — the workflow events, the required `CI gate` result and the mocked Terraform tests that need no Cloudflare account.
