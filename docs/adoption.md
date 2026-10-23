# Adopt an existing installation without replacing it

[README](../README.md) · [Configuration](configuration.md) · [Architecture](architecture.md)

Use the repository root for a **new dedicated tunnel**. For an existing shared
tunnel, use `modules/publication`; keep the tunnel and its complete configuration
under their current owner. Publishing reusable code does not require moving
private state or credentials to a new public repository.

## Establish the existing owner

Before changing code, identify privately which workspace owns each DNS record,
Access application, tunnel and tunnel configuration. Save a protected state backup
and a snapshot of the complete ingress order. Confirm local HA access for recovery.

Match the existing `hostname`, `origin_service`, DNS comment and optional callback
settings exactly. The submodule requires the origin explicitly so it cannot
silently adopt a localhost default that differs from your working installation.
The objective of extraction is **no infrastructure change**; improvements to
behavior belong in a separate reviewed plan.

## One owner per tunnel configuration

Cloudflare keeps one ordered configuration per tunnel. Two Terraform resources
with the same tunnel ID do not combine their lists: they compete to replace the
configuration. The publication submodule creates neither the tunnel nor its config.

Add its returned rule in the existing configuration owner, preserving other routes:

```hcl
ingress = concat(
  local.existing_more_specific_routes,
  [module.home_assistant.ingress_rule],
  local.remaining_routes,
  [{ service = "http_status:404" }],
)
```

This is a composition pattern, not a complete replacement configuration. Neither
input list should already contain the final catch-all or the HA rule. Preserve
all existing route order, origin options and WARP settings. In particular, a
broad path regex before the HA rule can capture service-worker assets or callbacks.

[`examples/shared-tunnel`](../examples/shared-tunnel) shows module inputs and its
output. The example deliberately creates no second tunnel-config resource. When
referencing the module remotely, pin a reviewed full commit SHA rather than a
moving branch.

## Move addresses within the same state

Use reviewed `moved` blocks when resources are already owned by the same workspace.
For example, when the new module block is named `home_assistant`:

```hcl
moved {
  from = cloudflare_dns_record.old_home_assistant
  to   = module.home_assistant.cloudflare_dns_record.home_assistant
}

moved {
  from = cloudflare_zero_trust_access_application.old_callback
  to   = module.home_assistant.cloudflare_zero_trust_access_application.notification_callback[0]
}
```

Use your actual old addresses privately. Include the Access move only if that
resource already exists and `callback_access` is enabled with equivalent settings.
The dedicated root names its child module `publication`; resource destinations
must always match the module address in your configuration.

Retain move declarations for existing deployments. A moved block changes state
addresses inside one workspace; it does not transfer state between workspaces.
See [Terraform's refactoring guide](https://developer.hashicorp.com/terraform/language/modules/develop/refactoring).

## Existing resources outside this state

If a resource exists in Cloudflare but is not in your intended state, first verify
that another workspace does not own it. Use the import syntax documented for your
locked Cloudflare provider and the exact destination resource address. Provide
all matching configuration before planning the import. DNS and Access resources
have different import identifiers; do not guess them from a display name.

If another workspace owns it, coordinate a backed-up state transfer with that
owner. Do not independently import it and leave two active owners. Cross-workspace
migration needs its own reviewed sequence and rollback plan. No live import or
state transfer is performed by this repository's tests.

## Review the adoption plan

Expected for a pure same-state extraction: address moves only, **zero creates,
updates, replacements or deletes**. Verify outputs used by downstream consumers
still have equivalent values. A new DNS record, different Access policy order or
a changed ingress list is a behavior change, not a harmless module refactor.

If the plan changes infrastructure, stop and reconcile configuration, defaults or
state ownership. After an expected plan, apply and complete the
[acceptance checks](runbook.md#acceptance-checks), including every other service on
a shared tunnel. Keep the state backup until acceptance is complete.
