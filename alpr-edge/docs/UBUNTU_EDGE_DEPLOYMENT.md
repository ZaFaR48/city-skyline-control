# Ubuntu Edge Deployment

This package prepares one local Ubuntu mini PC for a single test parking station.
The camera and mini PC must be on the same local LAN so RTSP traffic stays local.
Only future events, health data, and selected evidence images should leave the
station.

Supported targets:

- Ubuntu 22.04
- Ubuntu 24.04

Default station paths:

- Application source: `/opt/city-skyline-edge`
- Runtime data: `/var/lib/city-skyline-edge`
- Configuration: `/etc/city-skyline-edge/edge.env`
- Virtualenv: `/opt/city-skyline-edge/.venv`

Runtime data is separated from source:

```text
/var/lib/city-skyline-edge/
  sqlite/
  frames/
  snapshots/
  queue/
  logs/
  backups/
  models/
```

## Install On The Mini PC

Copy the `alpr-edge` directory to the station mini PC, then run:

```bash
cd /path/to/alpr-edge
sudo ./deployment/ubuntu/install.sh
```

The installer creates the unprivileged `cityedge` user, prepares private
directories, creates a venv, installs Python dependencies, installs the systemd
unit template, and creates `/etc/city-skyline-edge/edge.env` only when it is
missing.

It does not enable or start the service.

Edit the station config:

```bash
sudo nano /etc/city-skyline-edge/edge.env
sudo chmod 0640 /etc/city-skyline-edge/edge.env
sudo chown root:cityedge /etc/city-skyline-edge/edge.env
```

Keep:

```text
EDGE_API_HOST=127.0.0.1
EDGE_API_PORT=18080
PTZ_DRY_RUN=true
```

Do not hardcode real credentials in docs, tickets, screenshots, or logs.

## Manual Service Commands

The deployment uses two supervised services under one target:

- `city-skyline-edge-api.service` runs the local API/UI.
- `city-skyline-edge-worker.service` runs the continuous parking session worker.
- `city-skyline-edge.target` starts and stops both together.

This is safer than one combined process because the worker can restart without
taking down the UI, and the UI can restart without losing the supervised worker.

After reviewing config on the mini PC:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now city-skyline-edge.target
```

Check status:

```bash
sudo systemctl status city-skyline-edge.target --no-pager
sudo systemctl status city-skyline-edge-api.service --no-pager
sudo systemctl status city-skyline-edge-worker.service --no-pager
journalctl -u city-skyline-edge-api.service -u city-skyline-edge-worker.service -f
```

## Local UI Access

The API/UI binds to localhost by default and must not be opened publicly.

Use SSH or VPN port forwarding:

```bash
ssh -L 18080:127.0.0.1:18080 USER@EDGE_VPN_IP
```

Then open:

```text
http://localhost:18080/
```

## Diagnostics

Run the station doctor:

```bash
sudo /opt/city-skyline-edge/deployment/ubuntu/doctor.sh
```

The doctor checks OS, Python, CPU architecture, RAM, disk, timezone, NTP,
camera reachability, RTSP TCP, decoded video frame, snapshot writes, SQLite
writes, local API availability, PTZ dry-run, Headscale/Tailscale command
health, DNS, internet, and queue depth.

A ping or open TCP port does not prove the camera works. The camera is
operational only when a valid video frame is decoded.

## Timezone And NTP

Parking records need accurate timestamps. Internal event timestamps remain UTC.
The station timezone should be `Asia/Dushanbe`.

Check:

```bash
timedatectl
```

Set only with operator approval:

```bash
sudo timedatectl set-timezone Asia/Dushanbe
sudo timedatectl set-ntp true
```

## Backup And Restore

Create a backup:

```bash
sudo /opt/city-skyline-edge/deployment/ubuntu/backup.sh
```

Restore manually:

```bash
sudo /opt/city-skyline-edge/deployment/ubuntu/restore.sh /var/lib/city-skyline-edge/backups/ARCHIVE.tar.gz
```

Backups include SQLite configuration data, the current environment file,
snapshots, queue, models, and metadata. Disposable cached frames are not backed
up by default.

## Manual Update

From a freshly copied package on the mini PC:

```bash
cd /path/to/new/alpr-edge
sudo ./deployment/ubuntu/update.sh
```

The update script creates a backup, stops the service if it was running,
updates application files, preserves `/etc/city-skyline-edge/edge.env`, updates
dependencies, runs migrations, compiles Python, runs tests when present, and
restarts only if the service was previously running.

No central automatic update flow exists in this MVP.

## Support Bundle

Collect redacted logs:

```bash
sudo /opt/city-skyline-edge/deployment/ubuntu/collect_logs.sh
```

Review the archive before sharing. It is designed to redact RTSP passwords,
ONVIF credentials, API tokens, and credential-containing URLs.
