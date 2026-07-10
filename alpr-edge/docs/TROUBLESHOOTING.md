# Troubleshooting

## Doctor Fails NTP

Check:

```bash
timedatectl
```

With operator approval:

```bash
sudo timedatectl set-timezone Asia/Dushanbe
sudo timedatectl set-ntp true
```

## Ping Works But Video Fails

Ping only proves the host answered ICMP. Check the RTSP URL, camera user
permissions, vendor RTSP path, TCP port, and whether the camera allows the mini
PC IP to stream.

Run:

```bash
sudo /opt/city-skyline-edge/deployment/ubuntu/doctor.sh
```

The camera is not operational until the doctor reports a decoded frame.

## UI Not Reachable

Check that the service is running:

```bash
sudo systemctl status city-skyline-edge.target --no-pager
sudo systemctl status city-skyline-edge-api.service --no-pager
sudo systemctl status city-skyline-edge-worker.service --no-pager
```

Check local binding:

```bash
curl http://127.0.0.1:18080/api/v1/health
```

Use a tunnel from your workstation:

```bash
ssh -L 18080:127.0.0.1:18080 USER@EDGE_VPN_IP
```

Then open `http://localhost:18080/`.

Do not bind the API to `0.0.0.0` for the MVP.

## PTZ Movement

For the one-station MVP, keep:

```text
PTZ_DRY_RUN=true
```

Preset design uses manually positioned camera views. Real ONVIF movement should
remain disabled until RTSP capture is stable, ONVIF credentials are verified,
preset tokens are mapped, and manual approval is given.

## Logs

Collect a redacted support bundle:

```bash
sudo /opt/city-skyline-edge/deployment/ubuntu/collect_logs.sh
```

Review before sharing. The archive should not include raw RTSP passwords, ONVIF
passwords, API tokens, or complete credential-containing URLs.
