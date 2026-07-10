# Pilot Deployment Runbook

This runbook is for one real parking-station Ubuntu mini PC. It is not a
production rollout and must not be used for all stations.

Assumptions:

- Central source server: `13.140.180.178`
- Example edge mini PC user: `EDGE_USER=ptz`
- Example edge mini PC VPN address: `EDGE_VPN_IP=100.64.0.X`

Do not treat `100.64.0.X` as a real station address.

## A. Build Release On Source Server

On the source server:

```bash
cd /opt/city-skyline-control/alpr-edge
./scripts/build_pilot_release.sh
```

The script runs compile checks, shell syntax checks, pytest, staged secret
scanning, archive creation, checksum creation, manifest creation, and archive
verification. It does not install dependencies, use sudo, start services,
access a camera, or upload anything.

## B. Verify Release Archive

Use the archive printed by the build script:

```bash
./scripts/verify_pilot_release.sh dist-pilot/city-skyline-edge-pilot-<version>-<UTC_TIMESTAMP>.tar.gz
```

Confirm the verifier reports PASS for SHA256, archive structure, required
files, forbidden files, secret scan, and manifest validation.

## C. Copy Archive To Mini PC

Copy the archive and sidecars over Headscale/VPN:

```bash
EDGE_USER=ptz
EDGE_VPN_IP=100.64.0.X
ARCHIVE=dist-pilot/city-skyline-edge-pilot-<version>-<UTC_TIMESTAMP>.tar.gz
scp "${ARCHIVE}" "${ARCHIVE}.sha256" "${ARCHIVE%.tar.gz}.manifest.json" "${ARCHIVE%.tar.gz}.inventory.txt" "${EDGE_USER}@${EDGE_VPN_IP}:/tmp/"
```

## D. Verify SHA256 On Mini PC

On the mini PC:

```bash
cd /tmp
sha256sum -c city-skyline-edge-pilot-<version>-<UTC_TIMESTAMP>.tar.gz.sha256
```

## E. Extract To Temporary Source Directory

```bash
mkdir -p /tmp/city-skyline-edge-pilot-src
tar -xzf /tmp/city-skyline-edge-pilot-<version>-<UTC_TIMESTAMP>.tar.gz -C /tmp/city-skyline-edge-pilot-src
cd /tmp/city-skyline-edge-pilot-src/city-skyline-edge-pilot-<version>-<UTC_TIMESTAMP>
```

## F. Run Installation Script Manually

```bash
sudo ./deployment/ubuntu/install.sh
```

The installer must not start or enable systemd.

## G. Configure Edge Environment

Edit:

```bash
sudo nano /etc/city-skyline-edge/edge.env
```

Safe example:

```text
STATION_CODE=10001
CAMERA_ID=CAM-001
CAMERA_NAME=Test Parking PTZ
CAMERA_VENDOR=generic
CAMERA_LOCAL_IP=192.168.1.120

RTSP_URL=rtsp://USERNAME:PASSWORD@192.168.1.120:554/VENDOR_STREAM_PATH
RTSP_TRANSPORT=tcp

EDGE_API_HOST=127.0.0.1
EDGE_API_PORT=18080

PTZ_DRY_RUN=true

CENTRAL_API_URL=
CENTRAL_API_TOKEN=
```

Do not invent or document a vendor RTSP path. Use the real path only in the
private station environment file.

## H. Keep PTZ Dry Run

Confirm:

```bash
sudo grep '^PTZ_DRY_RUN=true$' /etc/city-skyline-edge/edge.env
```

## I. Run Doctor

```bash
sudo /opt/city-skyline-edge/deployment/ubuntu/doctor.sh
```

The camera is operational only after a valid frame is decoded.

## J. Start Service Without Enabling Permanently

```bash
sudo systemctl daemon-reload
sudo systemctl start city-skyline-edge.target
```

Do not run `systemctl enable` during the first pilot session.

## K. Check Systemd Logs

```bash
sudo systemctl status city-skyline-edge.target --no-pager
sudo systemctl status city-skyline-edge-api.service --no-pager
sudo systemctl status city-skyline-edge-worker.service --no-pager
journalctl -u city-skyline-edge-api.service -u city-skyline-edge-worker.service -n 100 --no-pager
```

## L. Open Local UI Through SSH Tunnel

From the operator workstation:

```bash
ssh -L 18080:127.0.0.1:18080 ptz@100.64.0.X
```

Open:

```text
http://localhost:18080/
```

Do not publicly expose port `18080`.

## M. Test RTSP Decoded Frame

In the UI, run the camera test. It must report a decoded frame, not only ping
or TCP success.

## N. Capture One Snapshot

Capture one reference snapshot and confirm it is saved under station runtime
data.

## O. Create Home Preset

Manually position the PTZ camera in the vendor UI, then create and save one
Home preset in the local UI.

## P. Draw One Polygon

Draw one normalized polygon zone on the snapshot.

## Q. Create 3-5 Parking Slots

Create 3-5 test slots in the polygon zone.

## R. Restart Service

```bash
sudo systemctl restart city-skyline-edge.target
```

## S. Confirm Data Persists

Open the UI again through the SSH tunnel and verify the Home preset, polygon,
and slots remain visible.

## T. Stop Pilot Service Safely If Test Fails

```bash
sudo systemctl stop city-skyline-edge.target
sudo /opt/city-skyline-edge/deployment/ubuntu/collect_logs.sh
```

After pilot validation, the future boot enable command is:

```bash
sudo systemctl enable --now city-skyline-edge.target
```

Review the support archive before sharing.
