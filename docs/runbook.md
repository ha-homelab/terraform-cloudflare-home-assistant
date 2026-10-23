# Install, verify, operate and recover

[README](../README.md) · [Troubleshooting](troubleshooting.md) · [Security](../SECURITY.md)

![Provision, connect, verify and operate: Terraform success and runtime acceptance are distinct steps.](setup-flow.svg)

## State and backups

Keep installation inputs outside Git and credentials in a secret manager. Protect
Terraform state, saved plans and backups with restricted access and encryption
appropriate to your backend. State and plans expose topology and resource IDs;
marking an output `sensitive` does not encrypt them. Never upload live state,
plans, provider debug logs or actual variable files to public Actions artifacts.
See [Terraform's sensitive-data guidance](https://developer.hashicorp.com/terraform/language/manage-sensitive-data).

No account-specific backend is embedded here. For production, configure a private
backend with locking/versioning as appropriate. An external CLI config or private
wrapper can provide backend credentials. If using local state, protect the entire
working directory and back it up independently; `.gitignore` is not a backup.
Keep a protected record of the reviewed code revision, provider lock and input
version so an operator can reproduce the configuration later.

## Before applying

1. Confirm a working local HA login and a recovery path independent of this tunnel.
2. Check the account, active zone and unused hostname. Determine the origin address
   from the connector's network namespace, including its actual HA port.
3. Provide the scoped API token and review `terraform plan`. For default new
   installation expect 3 additions; investigate replacements or unrelated changes.
4. Review the fresh plan shown by `terraform apply` and confirm only intended changes.
5. Record outputs privately. Apply success does not start the connector.

Existing resources require [adoption](adoption.md) first. Do not run this new-tunnel
procedure over an existing hostname simply to make Terraform accept it.

## Start the connector

Install a supported `cloudflared` build using
[Cloudflare's downloads](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/).
Locate the tunnel using `terraform output -raw tunnel_id`, then retrieve its
connector token in the dashboard. Store the token outside the checkout in a file
readable only by the connector service account. On Unix, restrict the parent
directory and file permissions; in a container, mount it as a runtime secret.

For a foreground check, replace this placeholder path:

```sh
cloudflared tunnel --no-autoupdate run --token-file /private/path/tunnel.token
```

`--token-file` requires cloudflared 2025.4.0 or newer. The credential grants the
ability to connect to that tunnel: keep it out of command arguments, screenshots
and logs. The [official run-parameter reference](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/configure-tunnels/run-parameters/)
describes this option. Terraform does not fetch the token.

Once verified, run the connector persistently with your service manager or
orchestrator, using the same restricted token file. Pin and maintain the installed
version; this command disables the process's own updater. Confirm restart policy,
network readiness and service-account access to the secret. Installing the
connector does not require giving it the Terraform API token.

## Configure Home Assistant

Set HA's external URL to `terraform output -raw url`. In current HA releases,
configure HTTP settings under **Settings → System → Network**: enable forwarded
header trust and add the connector's actual source address to trusted proxies.
Use the narrowest correct address/subnet, never `0.0.0.0/0` or `::/0`.

For HA before 2026.8, consult the matching version's YAML configuration; current
releases migrate those settings to the UI. HA OS defaults to port 80 from 2026.8;
HA Container remains 8123. Check your installation rather than assuming either.
Saving current HTTP settings restarts HA and requires confirmation, so keep local
access available. See the [official HTTP integration reference](https://www.home-assistant.io/integrations/http/).

Proxy trust concerns the peer connecting **to HA**, often a container address,
not the public user's IP or Cloudflare's edge addresses. A custom reverse proxy
between cloudflared and HA changes which peer HA must trust.

## Acceptance checks

Record results privately, with time and code revision. Test from a network outside
your home LAN to avoid mistaking local DNS or a local route for working publication.

- [ ] The expected tunnel reports a healthy connector.
- [ ] The hostname resolves and presents a valid public TLS certificate.
- [ ] The HA login page appears; native authentication and MFA work.
- [ ] Authenticated dashboard values update and WebSockets stay connected.
- [ ] Logout ends the session; a fresh private browser cannot bypass login.
- [ ] Companion clients connect using their configured external URL.
- [ ] If used, browser notification registration and delivery work.
- [ ] The connector restarts successfully without an interactive login.
- [ ] For a shared tunnel, all pre-existing services still pass their checks.

A green CI badge covers source contracts, not these live checks. Do not call a
migration complete until the relevant runtime checks pass.

## Routine operation

Before upgrading code or providers, review the diff and run the credential-free
checks. Plan against your private state and inspect any action other than the
intended change. Preserve the provider lock. Apply in a window with local HA
access, then repeat the relevant acceptance checks. Maintain connector and HA
updates independently of Terraform.

Do not edit Terraform-owned tunnel routes in the dashboard as the normal change
process: the next apply reconciles drift. For emergency changes, record them
privately and reconcile the intended configuration before the next apply.

## Rollback and recovery

**A configuration change:** restore the last reviewed inputs and code revision,
then create a fresh plan against current state. Review and apply the reversal.
If resource addresses moved, retain or explicitly reverse the reviewed moves;
blindly reverting HCL can propose replacement infrastructure.

**A connector failure:** restore the last working service definition and origin
settings. Verify the token file and local reachability before changing Terraform.
A DNS change will not repair an unreachable origin.

**Lost local state:** restore a protected state backup, or use a deliberate
[import procedure](adoption.md#existing-resources-outside-this-state). Do not apply
an empty state against an existing installation. Never restore a stale state
blindly over newer live infrastructure.

**Remove a new dedicated installation:** review a destroy plan for this root only,
then confirm removal during a maintenance window. Stop its connector and remove
its runtime secret afterward. This removes publication, not HA or its data.
Never destroy the shared tunnel's owning root as a shortcut for removing one route.

**Credential exposure:** revoke or rotate the affected credential in Cloudflare,
update the private secret store and verify the replacement. A leaked connector
token and a leaked API token need different rotations. Removing a file from Git
history alone does not revoke access. Follow [SECURITY.md](../SECURITY.md).
