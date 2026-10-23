# Run cloudflared in Docker or k3s

[README](../README.md) · [Native binaries](cloudflared-binaries.md) ·
[Runbook](runbook.md) · [Troubleshooting](troubleshooting.md)

These examples connect the **remotely managed tunnel already created by
Terraform**. They do not create another tunnel, install Home Assistant (HA), or
configure its trusted proxies. Use the connector token for `terraform output -raw
tunnel_id`; the connector does not need your Cloudflare API token, `cert.pem`, or
Terraform state. Keep the token outside Git.

The examples pin cloudflared **2026.10.3** and its multi-platform image digest
(verified for Linux AMD64 and ARM64). Review and update that pin deliberately;
process auto-updates are disabled. Docker Desktop must use **Linux containers**.
For native Windows/macOS processes, use the [binary guide](cloudflared-binaries.md).

## Choose an origin the connector can reach

Set `origin_service` in your **private Terraform inputs**, then review/apply that
configuration yourself. CI never performs this deployment.

- **HA on the same Docker network:** use its service name or network alias, such
  as `http://home-assistant:8123`. Both containers must join that network.
- **HA on the Docker Desktop host:** use `http://host.docker.internal:8123` if
  HA actually listens there. The host firewall must permit this path.
- **HA on a Linux Docker host:** an explicit `host-gateway` mapping can provide
  `host.docker.internal`; HA must listen on an address reachable from the bridge.
  A listener bound only to the host's `127.0.0.1` is not reachable this way.
- **HA in Kubernetes:** use the existing Service DNS name and **Service port**,
  for example `http://home-assistant.home-assistant.svc.cluster.local:8123`.
  The example assumes that Service and namespace exist; it does not create them.
- **HA elsewhere on your LAN:** use a private DNS name/IP reachable from every
  connector node. Store the real address in private inputs only.

`127.0.0.1` in a container/pod means that container/pod, not your laptop, Docker
host or Kubernetes node. HA OS and HA Container can use different ports; verify
the actual listener. Configure [HA proxy trust](runbook.md#configure-home-assistant)
for the source address HA observes, including any NAT or intermediate proxy.

## Prepare a token file

Export only the file's **absolute path**, not its contents. On Linux/macOS, use a
private file owned by your account, mode `0600`, in a mode `0700` directory.
Copy only the token value from the existing tunnel's dashboard, not its entire
installation command. Save it using this Bash block; it refuses to overwrite an
existing token and does not record the value in shell history:

```bash
(
  set -euo pipefail
  umask 077
  mkdir -p "$HOME/.config/cloudflared-ha"
  chmod 0700 "$HOME/.config/cloudflared-ha"
  set -o noclobber
  IFS= read -r -s -p 'Paste the tunnel token: ' cf_token </dev/tty
  printf '\n' >/dev/tty
  test -n "$cf_token"
  printf '%s' "$cf_token" > "$HOME/.config/cloudflared-ha/tunnel.token"
  unset cf_token
)
```

Do not run with shell tracing enabled. This is a protected plaintext file, not
an encrypted secret store; use your secret manager to supply it when available.

For Docker Compose on a Unix host, make the container user match the file owner:

```sh
export TUNNEL_TOKEN_FILE="$HOME/.config/cloudflared-ha/tunnel.token"
export CLOUDFLARED_UID="$(id -u)"
export CLOUDFLARED_GID="$(id -g)"
```

Use a non-root account. The image normally uses UID/GID `65532:65532`; the Compose
example allows overriding those IDs because local file-backed Compose secrets
retain host file permissions. Specifying a `uid`, `gid` or `mode` on a Compose
secret is not a reliable way to change a host bind-mounted file. Do not solve a
permission error with `chmod 777` or a world-readable token. With a rootless Docker
or user-namespace setup, account for its UID mapping and verify file readability.
See [Docker's secret behavior](https://docs.docker.com/compose/how-tos/use-secrets/)
and [file-backed secret permissions](https://docs.docker.com/reference/compose-file/services/#secrets).

On Windows, open **Windows PowerShell 5.1 as Administrator** and use the binary guide's
[private storage block](cloudflared-binaries.md#create-private-storage-and-enter-the-token)
to create the restricted file; skip binary/service installation when using Docker.
Set its path in PowerShell and keep Docker Desktop in Linux-container mode:

```powershell
$env:TUNNEL_TOKEN_FILE = Join-Path $env:ProgramData 'CloudflaredHomeAssistant\tunnel.token'
```

Keep the default container UID/GID unless your Docker file-sharing setup requires
a different mapping. The referenced block permits only SYSTEM/Administrators;
if Desktop's backend needs your user to read the source, grant read/traverse to
that specific account in the file's Security properties. Keep other users denied.
Docker Desktop must have access to the source path.

## Docker Compose

Use [`examples/docker/compose.yaml`](../examples/docker/compose.yaml) from the
repository root. It runs a single connector, mounts its token read-only, drops
capabilities, rotates logs and checks edge connectivity using cloudflared's own
`ready` command. No shell or curl is needed inside the minimal image, and no ports
are published on the host.

The example joins an **existing** Docker network. If HA already uses a suitable
network, set `HA_NETWORK` to that network's name. Otherwise, for a bridge-network
HA container, create one and attach HA (replace the container name as needed):

```sh
docker network create ha-origin
docker network connect --alias home-assistant ha-origin home-assistant
```

Do not repeat network creation if it already exists. A host-network HA container
cannot join this bridge: use the host-origin option below instead. Add the chosen
network to HA's own Compose configuration so it survives HA container recreation.

```sh
export HA_NETWORK=ha-origin
docker compose -f examples/docker/compose.yaml config --quiet
docker compose -f examples/docker/compose.yaml pull
docker compose -f examples/docker/compose.yaml up -d
docker compose -f examples/docker/compose.yaml ps
docker compose -f examples/docker/compose.yaml logs --tail=100 cloudflared
docker compose -f examples/docker/compose.yaml exec cloudflared \
  cloudflared tunnel --metrics 127.0.0.1:2000 ready
```

In PowerShell, use `$env:HA_NETWORK = 'ha-origin'`; run commands on one line instead
of using Bash `\` continuations. On Docker Desktop the engine must remain running;
a restart policy does not start Desktop before user login or keep a sleeping Mac
online. Linux Docker Engine must itself be enabled at boot.

For a Linux-host origin, add this small override to a **private local file** and
pass both files to each Compose command with `-f`:

```yaml
services:
  cloudflared:
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

The example still needs the selected Docker network. No host networking is
required, and the override does not make a loopback-only HA listener reachable.

### Equivalent Docker command

On Linux/macOS with the same token file and network prepared, this is an
alternative to Compose, not an additional connector you need to start:

```sh
export CLOUDFLARED_IMAGE='cloudflare/cloudflared:2026.10.3@sha256:faa8e0a1475f137c910be6025f43c8e4092fdd35461b31e19fd1390657a1ff39'
docker run -d --name cloudflared-ha --restart unless-stopped \
  --network "$HA_NETWORK" --user "$(id -u):$(id -g)" \
  --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --log-driver json-file --log-opt max-size=10m --log-opt max-file=3 \
  --mount "type=bind,src=$TUNNEL_TOKEN_FILE,dst=/run/secrets/tunnel_token,readonly" \
  "$CLOUDFLARED_IMAGE" tunnel --no-autoupdate --metrics 127.0.0.1:2000 \
  run --token-file /run/secrets/tunnel_token
```

Check with `docker logs --tail=100 cloudflared-ha` and
`docker exec cloudflared-ha cloudflared tunnel --metrics 127.0.0.1:2000 ready`.
Compose is preferable for keeping restart, logging and health settings together.
Neither edge readiness nor a healthy container proves HA login works: finish the
[acceptance checks](runbook.md#acceptance-checks).

## k3s / Kubernetes

Use an existing supported Linux k3s cluster and a `kubectl` client configured for
it. If starting from scratch, follow the [k3s quick start](https://docs.k3s.io/quick-start)
and [requirements](https://docs.k3s.io/installation/requirements) first; this
repository does not bootstrap or reconfigure the cluster. k3s uses containerd, so
pulling an image into your workstation's Docker cache does not install it on nodes.

The [`examples/k3s/cloudflared.yaml`](../examples/k3s/cloudflared.yaml) manifest
contains a Namespace, Deployment and narrowly scoped NetworkPolicy. There is no Ingress, LoadBalancer,
NodePort, host mount, privileged container, Kubernetes API token or public metrics
Service. HTTPS terminates at Cloudflare; the connector opens outbound connections.

### Create the private Secret and deploy

Verify the target context before changing the cluster. The following commands run
on your administration machine; its token file is not committed or copied into a
public manifest:

```sh
kubectl config current-context
kubectl create namespace cloudflared --dry-run=client -o yaml | kubectl apply -f -
kubectl -n cloudflared create secret generic cloudflared-token \
  --from-file=token="$TUNNEL_TOKEN_FILE" --dry-run=client -o yaml \
  | kubectl apply --server-side --field-manager=cloudflared-token -f -
kubectl apply -f examples/k3s/cloudflared.yaml
kubectl -n cloudflared rollout status deployment/cloudflared --timeout=180s
kubectl -n cloudflared get pods -o wide
kubectl -n cloudflared logs deployment/cloudflared --all-pods=true --tail=100
```

The Secret key must be `token` and the Secret must be in `cloudflared`. The pod
mounts it as `/etc/cloudflared/token`, read-only, with group `65532` and mode
`0440`. It is not injected into command arguments or environment values. Kubernetes
Secrets need restricted RBAC and encrypted storage/backups; base64 is not
encryption. Follow the [k3s secrets-encryption procedure](https://docs.k3s.io/security/secrets-encryption)
for your cluster version. Enabling it on an existing cluster is separate maintenance,
not a prerequisite command to run blindly during this installation.

The default is two replicas, with a preference for different nodes. On a single
node both can run, but this does not protect against node failure. Every replica
must reach the **same HA origin**. Replicas improve connector availability; they
do not make HA highly available, and active WebSockets may reconnect during a
rollout. Avoid autoscaling solely on CPU; see [Cloudflare's replica guidance](https://developers.cloudflare.com/tunnel/guides/kubernetes/#architecture).

Resource requests/limits are starting values for a small installation, not measured
capacity guarantees. Observe memory/CPU and adjust your private copy. Rolling
updates temporarily need a third pod. Keep enough spare capacity or adjust rollout
settings consciously; do not disable probes to hide insufficient capacity.

### Readiness and origin checks

Readiness checks `/ready` for a connection to Cloudflare. Liveness checks the local
`/healthcheck` HTTP handler, so an edge/network outage does not repeatedly restart a
healthy process. Neither probe checks HA. The metrics listener also exposes
diagnostic configuration. The included NetworkPolicy selects only these connector
pods and denies incoming connections from other pods, while kubelet probes from
the hosting node remain allowed. It leaves egress to your existing policies.
This requires a controller that actually enforces
[Kubernetes NetworkPolicy](https://kubernetes.io/docs/concepts/services-networking/network-policies/).
Other additive allow policies can reopen access; audit the effective rules.
Do not expose this listener through an Ingress or a public Service. If Prometheus
needs access, add a precise namespace/pod selector for its port instead of allowing
the whole cluster.

To inspect edge readiness, open a temporary local-only port forward:

```sh
kubectl -n cloudflared port-forward deployment/cloudflared 2000:2000
```

In another terminal, run `curl --fail http://127.0.0.1:2000/ready`, then stop the
port forward with Ctrl+C. This checks one selected replica; inspect the others if
only some requests fail. For in-cluster HA, confirm its Service and EndpointSlices
exist (replace these example names with yours):

```sh
kubectl -n home-assistant get service home-assistant
kubectl -n home-assistant get endpointslice \
  -l kubernetes.io/service-name=home-assistant
```

Use an approved temporary diagnostic pod in the connector namespace when you need
to test DNS or HTTP from the cluster. A request from your laptop is not the same
network path, and a debug pod with different labels may face different network
policies. The cloudflared image intentionally lacks a shell; do not add tools or
HA access tokens to the production container just to run curl.

For example, this pinned curl image makes an unauthenticated, read-only request
and removes its temporary pod when finished. Replace the example Service URL
with your private origin. An HTTP response, including a 400/401, demonstrates
reachability but does not establish correct proxy trust or authentication:

```sh
kubectl -n cloudflared run origin-check --rm -i --restart=Never \
  --image=curlimages/curl:8.23.0@sha256:11e64e28c5f58c8d93ee95fcf22ac055f48b0bc440e0ce7d8013bbb5ad6aa8ac \
  -- --connect-timeout 5 --max-time 15 --silent --show-error \
  --output /dev/null --write-out 'HTTP %{http_code}\n' \
  http://home-assistant.home-assistant.svc.cluster.local:8123/
```

If admission policy rejects this diagnostic pod, use your cluster's approved
debug-pod template; do not relax the namespace policy. If an interrupted command
leaves `pod/origin-check` behind, delete that pod after inspecting its result.
For Docker, the same check can run on the selected bridge without mounting any
secret:

```sh
docker run --rm --network "$HA_NETWORK" \
  curlimages/curl:8.23.0@sha256:11e64e28c5f58c8d93ee95fcf22ac055f48b0bc440e0ce7d8013bbb5ad6aa8ac \
  --connect-timeout 5 --max-time 15 --silent --show-error \
  --output /dev/null --write-out 'HTTP %{http_code}\n' \
  http://home-assistant:8123/
```

## Upgrade, rotate and remove

**Image upgrade:** keep a private copy of the old manifest/digest. Review the new
cloudflared release and multi-platform digest, update the image pin in your copy,
then use Compose `pull`/`up -d` or `kubectl apply`/`rollout status`. Verify both edge
readiness and HA acceptance. To roll back, restore the previous pin and repeat.
`kubectl rollout undo deployment/cloudflared -n cloudflared` can restore a retained
Deployment revision, but it does not restore a changed Secret or Terraform inputs.

**Token rotation:** rotate the token using the [Cloudflare token procedure](https://developers.cloudflare.com/tunnel/reference/tunnel-tokens/)
and replace the protected source file. Recreate Compose containers with
`up -d --force-recreate`; restarting alone can leave an old inode mounted after an
atomic file replacement. For k3s, update the Secret without displaying its content:

```sh
kubectl -n cloudflared create secret generic cloudflared-token \
  --from-file=token="$TUNNEL_TOKEN_FILE" --dry-run=client -o yaml \
  | kubectl apply --server-side --field-manager=cloudflared-token -f -
kubectl -n cloudflared rollout restart deployment/cloudflared
kubectl -n cloudflared rollout status deployment/cloudflared --timeout=180s
```

Do not run with shell tracing or redirect this secret-bearing pipe to logs. If a
Secret manager/controller owns that Secret, update it through that owner instead;
do not force server-side field ownership. Secret projection updates alone do not
guarantee the running process re-reads its token. Rotation changes the token used
for new connections; follow Cloudflare's procedure to disconnect old sessions when
responding to exposure.

**Remove only the connector:** use `docker compose -f examples/docker/compose.yaml
down`, or `docker rm -f cloudflared-ha` for the standalone container. Keep the
external HA network. In k3s, delete only `deployment/cloudflared` and the associated
Secret and `networkpolicy/cloudflared-metrics` from the `cloudflared` namespace
after confirming they are no longer needed.
Do not delete a shared namespace, HA workloads, or Terraform-managed tunnel/DNS as
a shortcut. Removing all connectors makes the public route unavailable.

## Container and cluster troubleshooting

- **Docker network not found:** create the intended bridge or set `HA_NETWORK` to
  the existing network. Verify HA remains attached after it is recreated.
- **Token permission denied / not a file:** inspect the source path and ownership,
  Docker Desktop sharing, rootless UID mapping and SELinux denial logs. Keep SELinux
  enabled; use an appropriate label for a dedicated secret directory if required.
  `--mount` fails for a missing source, which is safer than silently mounting a
  directory. Do not print the token or mount your entire home directory.
- **Unhealthy container / pod never Ready:** check the token belongs to this tunnel,
  host clock, DNS and outbound TCP/UDP `7844`. `auto` prefers QUIC and can fall back
  to HTTP/2. A temporary `--protocol http2` **before `run`** can help isolate UDP
  filtering; TCP `7844` still needs to work. See the
  [official connection diagnostics](https://developers.cloudflare.com/tunnel/troubleshooting/).
- **ImagePullBackOff / ErrImagePull:** inspect pod events with `kubectl -n cloudflared
  describe pod <pod-name>`; check node DNS, registry access, image name/digest and
  available disk. This example supports Linux AMD64/ARM64, not Windows nodes or
  32-bit ARM. Do not remove the digest merely to make the pull pass.
- **Pending:** inspect scheduling events, node readiness, taints and requested
  resources. The spreading preference is soft; the example does not require two
  nodes. Rolling updates need spare pod capacity.
- **CreateContainerConfigError / FailedMount:** check Secret name, namespace, key
  and pod events. Use `kubectl -n cloudflared describe secret cloudflared-token`
  for key names/sizes; avoid `get secret -o yaml` in shared output.
- **CrashLoopBackOff / OOMKilled:** inspect `kubectl -n cloudflared logs <pod-name>
  --previous` and `describe pod`; correct flags/token-file permissions or tune
  memory based on measurements. Do not remove all limits by default.
- **Ready but 502:** test HA reachability from the connector network; check Service
  ports/endpoints, DNS, policies, CNI, and host/LAN firewalls. In k3s an external HA
  may see a node's NAT address. Trust that observed proxy path narrowly.
- **HA 400 / login fails:** continue with [HA-specific troubleshooting](troubleshooting.md#ha-returns-400-or-rejects-the-proxy).
- **Intermittent success with multiple replicas:** compare node-level origin and
  edge reachability. All replicas use one remote configuration; node-local
  `localhost` routes can send each replica to a different or absent service.

For restricted egress, allow your DNS resolver, Cloudflare's documented tunnel
endpoints and the HA origin; image pulls also need registry connectivity from the
nodes. Use [Cloudflare's firewall requirements](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/configure-tunnels/tunnel-with-firewall/)
instead of opening all inbound ports. This guide does not change firewall or CNI
policy automatically. Keep logs private until topology and identifiers are removed.
