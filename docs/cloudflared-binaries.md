# Run cloudflared as a native service

[README](../README.md) · [Configuration](configuration.md) · [Acceptance and recovery](runbook.md)

These instructions connect a **remotely managed tunnel already created by
Terraform** to Home Assistant. They cover Linux x86-64/ARM64, macOS Intel/Apple
silicon, and Windows x64. They do not create a tunnel, change its ingress rules,
or install Home Assistant. There is no `cloudflared tunnel login`, `cert.pem`,
locally managed credentials JSON, or local ingress configuration in this flow.

The examples pin **cloudflared 2026.10.3**, reviewed on 2026-10-23. Choose a newer
reviewed release when appropriate and update its version **and** checksums together.
Do not replace the URL with `latest` while keeping an old expected checksum.
The `--token-file` option requires 2025.4.0 or later.

## Before you start

1. Complete the Terraform apply and note `terraform output -raw tunnel_id` privately.
2. In the Cloudflare dashboard, select that exact tunnel and retrieve its connector
   token. Use only the token value, not the entire dashboard installation command.
   It is different from the Cloudflare API token used by Terraform.
3. Confirm the configured HA origin is reachable from this machine. The default
   `http://127.0.0.1:8123` works only if HA actually listens there; otherwise update
   `origin_service` through Terraform. The connector reads the remote tunnel config.
4. Identify any existing cloudflared installation/service. These are fresh-install
   examples; do not overwrite another connector or mix a package manager's service
   with these definitions. Keep independent local access to HA during setup.

Treat the token file as a secret even though it is not in Git. Keep it outside
synced source directories and diagnostic archives. Do not use `--token VALUE`,
`service install VALUE`, shell tracing (`set -x`), or a token in a service command
line. A stale `TUNNEL_TOKEN` environment variable takes precedence over the file;
remove that conflict from the intended service environment before continuing.

## Linux and macOS: download and verify

Run Unix snippets in **Bash** (`/bin/bash`), not Fish or PowerShell. You need `curl`,
`tar` on macOS, and the platform's checksum utility. This block downloads into a
private temporary directory, verifies SHA256, checks the reported version, and
installs a versioned binary. It creates the dedicated command
`/usr/local/bin/cloudflared-home-assistant` only if that path is unused. It does
not start a service or modify an existing active binary.

```bash
(
  set -euo pipefail
  umask 077
  cf_version='2026.10.3'
  case "$(uname -s):$(uname -m)" in
    Linux:x86_64)
      cf_asset='cloudflared-linux-amd64'
      cf_sha='053b80b0a23031a038fdbf3c073f59f82b8f1f152aa67971d7383ffafc0dbab0'
      ;;
    Linux:aarch64|Linux:arm64)
      cf_asset='cloudflared-linux-arm64'
      cf_sha='89297ebfb9e8c99c0dc013a1140601453cf3798d8306c5591651f4a3f5210be8'
      ;;
    Darwin:x86_64)
      cf_asset='cloudflared-darwin-amd64.tgz'
      cf_sha='81b7b85f2376815c4f59b1aa323887b62e16ce8b67555c2e1577dc23f2a82000'
      ;;
    Darwin:arm64)
      cf_asset='cloudflared-darwin-arm64.tgz'
      cf_sha='1165d14b6f6360a3b8c283d7d1100024d6ec7cd9bc9e32519e96150645f3ec55'
      ;;
    *) printf 'Unsupported OS/architecture for this example\n' >&2; exit 1 ;;
  esac

  cf_stage=$(mktemp -d)
  trap 'rm -rf "$cf_stage"' EXIT
  curl --fail --location --show-error --silent --proto '=https' --tlsv1.2 \
    "https://github.com/cloudflare/cloudflared/releases/download/${cf_version}/${cf_asset}" \
    --output "$cf_stage/$cf_asset"

  if [ "$(uname -s)" = 'Darwin' ]; then
    printf '%s  %s\n' "$cf_sha" "$cf_stage/$cf_asset" | shasum -a 256 --check -
    tar -xzf "$cf_stage/$cf_asset" -C "$cf_stage" cloudflared
    cf_binary="$cf_stage/cloudflared"
    codesign --verify --strict "$cf_binary"
  else
    printf '%s  %s\n' "$cf_sha" "$cf_stage/$cf_asset" | sha256sum --check -
    cf_binary="$cf_stage/$cf_asset"
  fi
  chmod 0755 "$cf_binary"
  "$cf_binary" --version
  test "$("$cf_binary" version --short)" = "$cf_version"

  cf_target="/usr/local/libexec/cloudflared-home-assistant/$cf_version"
  cf_link='/usr/local/bin/cloudflared-home-assistant'
  if sudo test -e "$cf_target/cloudflared"; then
    printf 'Version already installed; inspect it instead of overwriting it.\n' >&2
    exit 1
  fi
  sudo install -d -m 0755 "$cf_target" /usr/local/bin
  sudo install -m 0755 "$cf_binary" "$cf_target/cloudflared"
  if [ ! -e "$cf_link" ] && [ ! -L "$cf_link" ]; then
    sudo ln -s "$cf_target/cloudflared" "$cf_link"
  else
    printf 'New version installed; existing command link left unchanged.\n'
  fi
)
```

Use a native Apple-silicon terminal to select `Darwin:arm64`; a terminal running
under Rosetta can report `x86_64`. Check `uname -m` before downloading. The macOS
archives contain a member named `cloudflared`; the Linux assets are executable
files, not archives. Do not run an ARM64 binary on x86-64 or vice versa.

The pinned hashes come from the official release's **asset digests**, not an
unversioned download. Both macOS archives were downloaded and compared with those
digests when this guide was prepared. The release body at that time contained
different macOS archive checksums; use the pinned asset digests above and stop on
any mismatch. A checksum detects changed bytes; trusting it still depends on the
release publisher and where the expected value came from.

## Linux: dedicated systemd service

This example targets a systemd distribution with `useradd`, `getent`, `sudo` and
`journalctl`. OpenRC, SysV and WSL without systemd need a different service manager.
The service runs as the dedicated `cloudflared-ha` account with no interactive
login. Do not reuse an unrelated existing account of that name.

### Store the token without putting it in argv

Check for an existing account/service first, then create the account if absent:

```bash
getent passwd cloudflared-ha || true
systemctl status cloudflared-home-assistant.service --no-pager || true
# If either already belongs to an installation, inspect it instead of replacing it.
if ! id -u cloudflared-ha >/dev/null 2>&1; then
  sudo useradd --system --user-group --no-create-home \
    --home-dir /nonexistent --shell /bin/false cloudflared-ha
fi
sudo install -d -o root -g cloudflared-ha -m 0750 /etc/cloudflared-home-assistant
```

The following fresh-install block refuses to overwrite a token. Paste the value
at the hidden prompt. It is written through standard input, not command arguments.

```bash
(
  set -euo pipefail
  sudo -v
  cf_token_path='/etc/cloudflared-home-assistant/tunnel.token'
  if sudo test -e "$cf_token_path"; then
    printf 'Token file exists; use the rotation procedure.\n' >&2; exit 1
  fi
  sudo install -o root -g cloudflared-ha -m 0640 /dev/null "$cf_token_path"
  IFS= read -r -s -p 'Paste the tunnel token: ' cf_token </dev/tty
  printf '\n' >/dev/tty
  test -n "$cf_token"
  if [[ "$cf_token" == *[[:space:]]* ]]; then
    printf 'Enter only the token value, without a command or whitespace.\n' >&2; exit 1
  fi
  printf '%s' "$cf_token" | sudo tee "$cf_token_path" >/dev/null
  unset cf_token
)
```

Verify the file is nonempty and readable by the service account, then run in the
foreground. This establishes a **real connection** to your existing tunnel:

```bash
sudo -u cloudflared-ha test -s /etc/cloudflared-home-assistant/tunnel.token
sudo -u cloudflared-ha env -u TUNNEL_TOKEN -u TUNNEL_TOKEN_FILE \
  /usr/local/bin/cloudflared-home-assistant --no-autoupdate tunnel run \
  --token-file /etc/cloudflared-home-assistant/tunnel.token
```

Wait for registered tunnel connections and check the dashboard, then press
**Ctrl+C** before installing the service. A connection alone does not verify HA;
complete the [acceptance checks](runbook.md#acceptance-checks).

### Install and start the unit

Create `/etc/systemd/system/cloudflared-home-assistant.service` with `sudoedit`:

```ini
[Unit]
Description=Home Assistant Cloudflare Tunnel connector
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=cloudflared-ha
Group=cloudflared-ha
ExecStart=/usr/local/bin/cloudflared-home-assistant --no-autoupdate tunnel run --token-file /etc/cloudflared-home-assistant/tunnel.token
Restart=on-failure
RestartSec=5s
TimeoutStopSec=90s
UMask=0077
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
PrivateDevices=true
CapabilityBoundingSet=
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX

[Install]
WantedBy=multi-user.target
```

The unit intentionally has no auto-update timer and no deployment API token.
The hardening fits an HTTP(S) HA route; it does not enable ICMP/private-network
routing features. Check the unit before starting it:

```bash
sudo systemd-analyze verify /etc/systemd/system/cloudflared-home-assistant.service
sudo systemctl daemon-reload
sudo systemctl enable --now cloudflared-home-assistant.service
systemctl is-enabled cloudflared-home-assistant.service
systemctl is-active cloudflared-home-assistant.service
sudo journalctl -u cloudflared-home-assistant.service -n 80 --no-pager
```

`active` means the process is running, not that the hostname works. The boot service
and the network's online target do not eliminate the need for connectivity tests.

## macOS: system LaunchDaemon

This example uses a root-owned **LaunchDaemon**, so it starts at system boot after
the OS volume is available and does not depend on a user login session. It runs as
root, matching the native system-service model. Organizations requiring a dedicated
service identity should provision that account and adjust `UserName` plus file
permissions before using this example. A sleeping or powered-off Mac cannot serve
the tunnel; FileVault can require local unlock after a cold boot.

### Store and verify the token

```bash
sudo install -d -o root -g wheel -m 0700 \
  '/Library/Application Support/cloudflared-home-assistant'
(
  set -euo pipefail
  sudo -v
  cf_token_path='/Library/Application Support/cloudflared-home-assistant/tunnel.token'
  if sudo test -e "$cf_token_path"; then
    printf 'Token file exists; use the rotation procedure.\n' >&2; exit 1
  fi
  sudo install -o root -g wheel -m 0600 /dev/null "$cf_token_path"
  IFS= read -r -s -p 'Paste the tunnel token: ' cf_token </dev/tty
  printf '\n' >/dev/tty
  test -n "$cf_token"
  if [[ "$cf_token" == *[[:space:]]* ]]; then
    printf 'Enter only the token value, without a command or whitespace.\n' >&2; exit 1
  fi
  printf '%s' "$cf_token" | sudo tee "$cf_token_path" >/dev/null
  unset cf_token
)
sudo test -s '/Library/Application Support/cloudflared-home-assistant/tunnel.token'
sudo env -u TUNNEL_TOKEN -u TUNNEL_TOKEN_FILE \
  /usr/local/bin/cloudflared-home-assistant --no-autoupdate tunnel run \
  --token-file '/Library/Application Support/cloudflared-home-assistant/tunnel.token'
```

Verify the connections and HA access, then press **Ctrl+C**. Prepare private logs:

```bash
sudo install -d -o root -g wheel -m 0700 /var/log/cloudflared-home-assistant
sudo install -o root -g wheel -m 0600 /dev/null /var/log/cloudflared-home-assistant/stdout.log
sudo install -o root -g wheel -m 0600 /dev/null /var/log/cloudflared-home-assistant/stderr.log
```

### Install the LaunchDaemon

Create `/Library/LaunchDaemons/invalid.example.cloudflared-home-assistant.plist`
with `sudoedit`. This is a local service label, not a DNS name to deploy:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>invalid.example.cloudflared-home-assistant</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/local/bin/cloudflared-home-assistant</string>
    <string>--no-autoupdate</string>
    <string>tunnel</string>
    <string>run</string>
    <string>--token-file</string>
    <string>/Library/Application Support/cloudflared-home-assistant/tunnel.token</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>10</integer>
  <key>ExitTimeOut</key>
  <integer>90</integer>
  <key>ProcessType</key>
  <string>Background</string>
  <key>StandardOutPath</key>
  <string>/var/log/cloudflared-home-assistant/stdout.log</string>
  <key>StandardErrorPath</key>
  <string>/var/log/cloudflared-home-assistant/stderr.log</string>
</dict>
</plist>
```

```bash
sudo chown root:wheel /Library/LaunchDaemons/invalid.example.cloudflared-home-assistant.plist
sudo chmod 0644 /Library/LaunchDaemons/invalid.example.cloudflared-home-assistant.plist
plutil -lint /Library/LaunchDaemons/invalid.example.cloudflared-home-assistant.plist
sudo launchctl bootstrap system /Library/LaunchDaemons/invalid.example.cloudflared-home-assistant.plist
sudo launchctl print system/invalid.example.cloudflared-home-assistant
sudo tail -n 80 /var/log/cloudflared-home-assistant/stderr.log
```

Do not install the same label twice; use `bootout` before loading a replacement.
Schedule private log retention/rotation appropriate to your machine. The example
keeps logs local but does not configure automatic rotation.

## Windows x64: native Windows service

Use **64-bit Windows PowerShell 5.1 as Administrator**. This section uses the
built-in `New-EventLog` cmdlet, which is not available in PowerShell 7. The x64
binary is for x64 Windows; this example does not validate ARM Windows emulation.

The native binary uses the fixed service name **`Cloudflared`**. If that service
already exists, inspect the current installation instead of overwriting it. The
example runs as **LocalSystem** and restricts private files to SYSTEM and local
Administrators. A different service identity requires corresponding ACL changes.

### Download, verify and install a versioned executable

```powershell
$ErrorActionPreference = 'Stop'
$CfVersion = '2026.10.3'
$CfExpectedSha256 = '76b2805253d0d6ffacb092a7acfbee99e7af6917835c0c5410e23f3ef5052da2'
$CfStage = Join-Path $env:TEMP ('cloudflared-' + [guid]::NewGuid().ToString('N'))
$CfInstall = Join-Path $env:ProgramFiles ("CloudflaredHomeAssistant\$CfVersion")
$CfExe = Join-Path $CfInstall 'cloudflared.exe'
if (Test-Path -LiteralPath $CfExe) { throw 'Version already installed; inspect it first.' }
New-Item -ItemType Directory -Path $CfStage | Out-Null
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $CfDownloaded = Join-Path $CfStage 'cloudflared.exe'
    Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/cloudflare/cloudflared/releases/download/$CfVersion/cloudflared-windows-amd64.exe" -OutFile $CfDownloaded
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $CfDownloaded).Hash.ToLowerInvariant() -ne $CfExpectedSha256) {
        throw 'SHA256 mismatch; do not execute or install this file.'
    }
    & $CfDownloaded --version
    if ($LASTEXITCODE -ne 0) { throw 'Executable version check failed.' }
    if ((& $CfDownloaded version --short) -ne $CfVersion) { throw 'Unexpected executable version.' }
    New-Item -ItemType Directory -Path $CfInstall -Force | Out-Null
    Copy-Item -LiteralPath $CfDownloaded -Destination $CfExe
} finally {
    Remove-Item -LiteralPath $CfStage -Recurse -Force
}
```

### Create private storage and enter the token

The directory must be new, so this block cannot silently change an existing
installation's permissions. SID-based rules avoid localized group-name issues.

```powershell
$ErrorActionPreference = 'Stop'
if (Get-Service -Name Cloudflared -ErrorAction SilentlyContinue) {
    throw 'Cloudflared service already exists; inspect it before proceeding.'
}
$CfPrivate = Join-Path $env:ProgramData 'CloudflaredHomeAssistant'
$CfTokenPath = Join-Path $CfPrivate 'tunnel.token'
$CfLogPath = Join-Path $CfPrivate 'cloudflared.log'
if (Test-Path -LiteralPath $CfPrivate) { throw 'Private directory already exists; inspect it first.' }
New-Item -ItemType Directory -Path $CfPrivate | Out-Null
$CfAcl = New-Object System.Security.AccessControl.DirectorySecurity
$CfAcl.SetAccessRuleProtection($true, $false)
$CfAdmins = [System.Security.Principal.SecurityIdentifier]::new('S-1-5-32-544')
$CfSystem = [System.Security.Principal.SecurityIdentifier]::new('S-1-5-18')
$CfAcl.SetOwner($CfAdmins)
foreach ($CfSid in @($CfSystem, $CfAdmins)) {
    $CfRule = [System.Security.AccessControl.FileSystemAccessRule]::new(
        $CfSid, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
    $CfAcl.AddAccessRule($CfRule)
}
Set-Acl -LiteralPath $CfPrivate -AclObject $CfAcl

$CfSecret = Read-Host 'Paste the tunnel token' -AsSecureString
$CfPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($CfSecret)
try {
    $CfPlain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($CfPointer)
    if ([string]::IsNullOrWhiteSpace($CfPlain) -or $CfPlain -match '\s') {
        throw 'Enter only the token value, without spaces or a command.'
    }
    [IO.File]::WriteAllText($CfTokenPath, $CfPlain, [Text.UTF8Encoding]::new($false))
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($CfPointer)
    Remove-Variable CfPlain -ErrorAction SilentlyContinue
    $CfSecret.Dispose()
}
(Get-Acl -LiteralPath $CfTokenPath).Access
```

This writes plaintext inside the protected directory; SecureString input does
not turn the token file into an encrypted vault. The last command displays ACLs,
not the token. Do not display the file contents to check it.

### Foreground check and service registration

Use the same PowerShell session so the paths above remain defined:

```powershell
if ($env:TUNNEL_TOKEN -or [Environment]::GetEnvironmentVariable('TUNNEL_TOKEN', 'Machine')) {
    throw 'Remove the conflicting TUNNEL_TOKEN from the intended environment first.'
}
& $CfExe --no-autoupdate tunnel run --token-file $CfTokenPath
```

Check the tunnel and HA access, then press **Ctrl+C**. Register a service whose
command line contains only the **path** to the secret:

```powershell
$CfServiceCommand = '"{0}" --no-autoupdate --logfile "{1}" tunnel run --token-file "{2}"' -f $CfExe, $CfLogPath, $CfTokenPath
if (-not [Diagnostics.EventLog]::SourceExists('Cloudflared')) {
    New-EventLog -LogName Application -Source Cloudflared -MessageResourceFile (Join-Path $env:WINDIR 'System32\EventCreate.exe')
}
New-Service -Name Cloudflared -DisplayName 'Home Assistant Cloudflare Tunnel' -BinaryPathName $CfServiceCommand -StartupType Automatic | Out-Null
sc.exe config Cloudflared start= delayed-auto
if ($LASTEXITCODE -ne 0) { throw 'Cannot configure delayed automatic start.' }
sc.exe failure Cloudflared reset= 86400 actions= restart/5000/restart/15000/restart/60000
if ($LASTEXITCODE -ne 0) { throw 'Cannot configure service recovery.' }
Start-Service -Name Cloudflared
Get-Service -Name Cloudflared
if (Test-Path -LiteralPath $CfLogPath) {
    Get-Content -LiteralPath $CfLogPath -Tail 80
} else {
    Write-Output 'Service startup is asynchronous; recheck the private logfile and Event Viewer.'
}
```

The executable supports the Windows Service Control Manager directly; no service
wrapper is required. It logs its service arguments, so never substitute a literal
token into `$CfServiceCommand`. See Windows Event Viewer → Windows Logs →
Application for service lifecycle events, and the private logfile for connection
errors. Configure private logfile retention; it is not configured by this example.

## Upgrade, rollback and token rotation

An upgrade changes the connector binary, not Terraform's tunnel ID, DNS record or
remote ingress. Plan a short outage if this is the only connector. Do not delete
and recreate the tunnel to update cloudflared.

1. Review the new release and its asset checksum. Repeat the download/verification
   block with both values changed. Keep the previous verified version installed.
2. Stop the service using its OS command below; confirm it stopped before changing
   its binary path. A foreground `--version` check does not contact the tunnel.
3. For Linux/macOS, switch the dedicated command symlink to the new version:

   ```bash
   (
     set -euo pipefail
     cf_next_version='REPLACE_WITH_VERIFIED_VERSION'
     sudo test -x "/usr/local/libexec/cloudflared-home-assistant/$cf_next_version/cloudflared"
     sudo ln -s "/usr/local/libexec/cloudflared-home-assistant/$cf_next_version/cloudflared" \
       /usr/local/bin/cloudflared-home-assistant.next
     sudo mv -f /usr/local/bin/cloudflared-home-assistant.next \
       /usr/local/bin/cloudflared-home-assistant
     /usr/local/bin/cloudflared-home-assistant --version
   )
   ```

   Refuse an existing `.next` file rather than deleting an unknown path. The
   initial download block leaves the active symlink unchanged on upgrade.
4. On Windows, point the existing service at the newly verified version. Rebuild
   the command with your existing private paths, preserving quoting:

   ```powershell
   $CfNextVersion = 'REPLACE_WITH_VERIFIED_VERSION'
   $CfNextExe = Join-Path $env:ProgramFiles ("CloudflaredHomeAssistant\$CfNextVersion\cloudflared.exe")
   if (-not (Test-Path -LiteralPath $CfNextExe)) { throw 'Verified version is not installed.' }
   $CfNextCommand = '"{0}" --no-autoupdate --logfile "{1}" tunnel run --token-file "{2}"' -f $CfNextExe, $CfLogPath, $CfTokenPath
   $CfService = Get-CimInstance Win32_Service -Filter "Name='Cloudflared'"
   $CfResult = Invoke-CimMethod -InputObject $CfService -MethodName Change -Arguments @{ PathName = $CfNextCommand }
   if ($CfResult.ReturnValue -ne 0) { throw "Service path update failed: $($CfResult.ReturnValue)" }
   ```

5. Start the service and repeat the [acceptance checks](runbook.md#acceptance-checks),
   including external login and live dashboard updates. Roll back by stopping the
   service and selecting the previous verified binary using the same procedure.

To rotate a token, follow Cloudflare's token rotation workflow, write the new value
to a **new protected file with the same owner/ACL**, verify its permissions, then
replace the old file and restart the connector. The startup process reads the file;
editing it does not update an already running connection. Keep the token value out
of command arguments throughout. A known leak requires revocation/rotation, not
merely deleting a local file. Do not retain old token copies in public backups.

## Stop, start and remove only this installation

Stopping the connector interrupts this publication when no other connector serves
the tunnel. It leaves Terraform resources and HA data unchanged.

**Linux:**

```bash
sudo systemctl stop cloudflared-home-assistant.service
sudo systemctl start cloudflared-home-assistant.service
```

To remove the service instead:

```bash
sudo systemctl disable --now cloudflared-home-assistant.service
sudo rm /etc/systemd/system/cloudflared-home-assistant.service
sudo systemctl daemon-reload
```

**macOS:**

```bash
sudo launchctl bootout system/invalid.example.cloudflared-home-assistant
sudo launchctl bootstrap system /Library/LaunchDaemons/invalid.example.cloudflared-home-assistant.plist
```

To remove the service instead, unload it and delete only this guide's plist:

```bash
sudo launchctl bootout system/invalid.example.cloudflared-home-assistant
sudo rm /Library/LaunchDaemons/invalid.example.cloudflared-home-assistant.plist
```

**Windows PowerShell 5.1, Administrator:**

```powershell
Stop-Service -Name Cloudflared
(Get-Service -Name Cloudflared).WaitForStatus('Stopped', [TimeSpan]::FromSeconds(90))
Start-Service -Name Cloudflared
```

To remove the service instead:

```powershell
$ErrorActionPreference = 'Stop'
Stop-Service -Name Cloudflared
(Get-Service -Name Cloudflared).WaitForStatus('Stopped', [TimeSpan]::FromSeconds(90))
sc.exe delete Cloudflared
if ($LASTEXITCODE -ne 0) { throw 'Service deletion failed.' }
# Only if this guide created the source and no remaining service uses it:
Remove-EventLog -Source Cloudflared
```

After confirming removal, privately remove this installation's token, logs,
versioned binaries, and dedicated Unix symlink if they are no longer needed.
Keep unrelated services and their files. Remove the Linux service account only
if it was created for this installation and has no remaining use. Removing a
connector does not revoke its token or remove Cloudflare publication; manage
those actions separately and review the Terraform plan before resource deletion.

## OS-specific troubleshooting

- **Checksum mismatch:** stop before execution. Confirm version, asset name and
  architecture against the official release. Do not replace the expected digest
  with whatever the downloaded file happens to hash to.
- **Linux `Exec format error`:** wrong architecture or a corrupted download.
  **203/EXEC:** check the symlink target, execute permissions and mount `noexec`
  settings. **217/USER:** check the service account and group. A token read error
  needs directory traversal plus file-read permission for `cloudflared-ha`; do
  not fix it with world-readable permissions.
- **macOS bootstrap error:** validate the plist, owner/mode, executable path and
  whether the label is already loaded. A LaunchAgent is login-dependent; the
  supplied LaunchDaemon is system-wide. Check Gatekeeper/signature failures
  against the official publisher; do not globally disable Gatekeeper. Sleep,
  lid closure and a locked FileVault boot can explain an unavailable connector.
- **Windows service fails to start:** use the fixed `Cloudflared` service name,
  verify the fully quoted executable path and SYSTEM access to the token/log
  directory. A working interactive process can hide a service ACL problem.
  `$CfExe`, `$CfTokenPath` and `$CfLogPath` are session variables; re-establish them
  in a new admin session before following upgrade commands. Do not use `sc`
  without `.exe` in Windows PowerShell: `sc` is a different command alias.
- **Service running but no working HA:** inspect private logs, connector health,
  the actual origin address/port and HA reverse-proxy trust. Outbound DNS and
  tunnel transport must be allowed by the local network. There is no need to
  open inbound port 8123 on the router for this flow. Continue with the
  [layer-by-layer troubleshooting guide](troubleshooting.md).

## Verification basis

These are reviewed operating procedures, not a claim that this repository installs
or tests services on your OS. During preparation, the macOS ARM64 executable was
hash-verified and invoked only for version/help output; both macOS archive hashes
were verified. No real token, tunnel connection or system service was used.
Bash snippets passed syntax and ShellCheck validation, PowerShell snippets passed
parser validation, and the LaunchDaemon plist passed `plutil -lint`. These checks
do not execute service installation. Linux and Windows service instructions were
checked against the pinned upstream source and platform command interfaces, not
exercised against a live installation.

- [Official cloudflared downloads](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/)
- [Pinned release and assets: 2026.10.3](https://github.com/cloudflare/cloudflared/releases/tag/2026.10.3)
- [Release asset metadata and digests](https://api.github.com/repos/cloudflare/cloudflared/releases/tags/2026.10.3)
- [Tunnel run parameters and token-file support](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/configure-tunnels/run-parameters/)
- [Pinned CLI token precedence and file reading](https://github.com/cloudflare/cloudflared/blob/2026.10.3/cmd/cloudflared/tunnel/subcommands.go)
- [Pinned Windows service name, argument handling and event logging](https://github.com/cloudflare/cloudflared/blob/2026.10.3/cmd/cloudflared/windows_service.go)
- [Pinned macOS LaunchDaemon/LaunchAgent behavior](https://github.com/cloudflare/cloudflared/blob/2026.10.3/cmd/cloudflared/macos_service.go)
- [Pinned Linux service and update-timer behavior](https://github.com/cloudflare/cloudflared/blob/2026.10.3/cmd/cloudflared/linux_service.go)
- [systemd execution settings](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html)
- [Apple: LaunchDaemons and LaunchAgents](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html)
- [Microsoft: New-Service](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/new-service)
- [Microsoft: Windows PowerShell New-EventLog](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/new-eventlog?view=powershell-5.1)
- [Microsoft: Win32_Service.Change](https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/change-method-in-class-win32-service)
