# Security policy

## Report a vulnerability privately

Use this repository's **Security → Advisories → Report a vulnerability** feature
when available. Include the affected revision, impact and a synthetic reproduction.
Do not open a public issue containing a live credential, real installation
inventory or an exploit against an actual Home Assistant instance. If private
reporting is unavailable, ask in a public issue for a private contact channel
without disclosing the vulnerability or sensitive details.

We do not promise a response SLA. Coordinate disclosure after the issue can be
reproduced and a fix or mitigation is available.

## Installation trust boundaries

The default hostname is internet-facing and uses Home Assistant's own
authentication. Cloudflare Tunnel is a transport and reverse-proxy mechanism; this
module does not add a whole-site identity policy. Keep HA authentication and MFA,
maintain updates, and restrict unintended direct access to the origin. Cloudflare
terminates public TLS; the default final hop to HA is HTTP within your chosen
network. Use a verified HTTPS origin if that hop requires encryption.

Trust only the actual reverse-proxy peer in HA. An overly broad trusted-proxy
setting can allow a client to impersonate forwarded source addresses. The
optional callback Access application uses policies you explicitly supply and is
not a replacement for whole-site authorization.

## Keep these private

- API tokens, connector tokens, HA tokens, cookies and authentication headers.
- Actual account/zone/tunnel inventory, domain names and origin addresses.
- Terraform state, saved plans, backups, debug logs and deployment variable files.

Account IDs and hostnames are not passwords; they still reveal installation
metadata that does not belong in this public template. Ignore rules reduce
accidental commits but do not prevent `git add -f`, unsafe logging or artifact
uploads. Review new files and diffs before publishing them.

This repository's CI validates synthetic configurations without deployment
credentials. Do not give public PR workflows access to your production account.
Pin reviewed module revisions and keep the provider lock under version control.

## If something leaked

Revoke or rotate the actual credential first, restore service using the replacement,
and inspect the account's relevant access/audit records. Restrict access to leaked
artifacts and remove them using the hosting service's process. History cleanup
alone does not revoke a credential or guarantee every copy is gone. Keep recovery
records private. See the [operations runbook](docs/runbook.md#rollback-and-recovery).
