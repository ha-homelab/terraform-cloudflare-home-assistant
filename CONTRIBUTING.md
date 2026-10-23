# Contributing

Contributions should keep ordinary new installations configurable through inputs,
preserve existing resource identities during adoption, and keep public source
separate from private deployment data.

## Before opening a pull request

1. Use only fictional data: `ha.example.invalid`, explicit synthetic IDs and generic
   origin names. Never reproduce a real deployment's inventory or token.
2. Run `python3 scripts/ci.py`. It validates disposable copies against the provider
   schema and runs mocked Terraform contracts. No Cloudflare account is required.
3. Add a meaningful regression test when changing resource shape, validation,
   default behavior, ingress ownership or optional Access configuration.
4. Explain any proposed resource replacement or migration. Keep the shared-tunnel
   module free of competing tunnel configuration resources.
5. Update the relevant configuration/runbook page and diagrams when behavior changes.

Do not treat mock apply results as live acceptance evidence. If you independently
test a deployment, report which behaviors you checked without posting its domain,
state, credentials or sensitive logs. CI runs source and security checks; deployment
stays with the private installation owner.

## Documentation and artwork

Write public documentation in English. SVG diagrams are source-controlled and
use embedded shapes/text with no scripts, external fonts or remote image assets.
Keep readable labels, title/description elements and an explanatory Markdown
caption or alt text. Check the rendered image after changing its geometry.

Use primary Cloudflare, Home Assistant and Terraform references for product
behavior. Describe limitations honestly, including connector setup, proxy trust,
private state and the difference between native HA auth and optional Access.

## Security issues

Use [SECURITY.md](SECURITY.md) for private reporting. Ordinary bug reports should
contain a minimal synthetic configuration and the exact Terraform/provider versions.
