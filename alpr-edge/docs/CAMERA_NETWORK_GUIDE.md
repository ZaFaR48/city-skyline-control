# Camera Network Guide

The PTZ camera and Ubuntu mini PC should be connected to the same local LAN.

Example:

- Camera local IP: `192.168.1.120`
- Mini PC local IP: `192.168.1.x`

RTSP video must remain local. Do not route continuous camera video through the
central server.

## Configuration Fields

Use placeholders when documenting examples:

```text
STATION_CODE=STATION-TEST-001
CAMERA_ID=CAM-001
CAMERA_NAME=Entrance PTZ
CAMERA_VENDOR=vendor-name
CAMERA_LOCAL_IP=192.168.1.120
RTSP_URL=rtsp://USERNAME:PASSWORD@CAMERA_LOCAL_IP/VENDOR_PATH
RTSP_TRANSPORT=tcp
PTZ_DRY_RUN=true
```

Do not publish the real RTSP path if it contains credentials.

## Validation Order

1. Confirm the mini PC has a local LAN address.
2. Confirm the camera has a static or reserved local LAN address.
3. Ping the camera IP.
4. Check the RTSP TCP port.
5. Decode one video frame.
6. Save one snapshot.
7. Open the local UI through an SSH tunnel.

Ping and TCP success are not enough. A camera is operational only when a valid
frame is decoded.

## Local API Tunnel

Keep the API bound to localhost:

```text
EDGE_API_HOST=127.0.0.1
EDGE_API_PORT=18080
```

Access the UI through:

```bash
ssh -L 18080:127.0.0.1:18080 USER@EDGE_VPN_IP
```

Open:

```text
http://localhost:18080/
```

Do not publicly open port `18080`.
