# PTZ Preset, Zone and Patrol Designer Specification

This MVP configures one local PTZ camera for one parking station. It is a
calibration and configuration tool, not a production billing authority.

## Safety Rules

- `PTZ_DRY_RUN=true` is the default.
- Real ONVIF movement is disabled in this MVP.
- RTSP capture is used only for local snapshot calibration in this step.
- Dry-run actions log the intended command and explicitly report that the
  physical camera did not move.
- RTSP URLs, ONVIF passwords, API tokens, and other secrets must not be returned
  by API responses or rendered in browser HTML.

## Presets

Each preset represents a camera viewpoint:

- `home`
- `entrance`
- `exit`
- `parking`
- `no_parking`
- `disabled`
- `service`

The Home preset is identifiable and should have the highest priority. After a
future patrol cycle scans other presets, the camera should return to Home.

## Polygon Zones

Each preset can contain multiple arbitrary polygon zones. Coordinates are
normalized between `0.0` and `1.0` so zones remain valid when snapshot
resolution changes.

Validation rejects:

- fewer than 3 points
- coordinates outside image bounds
- duplicate consecutive points
- zero-area polygons
- self-intersecting polygons

The API warns when saved zones on the same preset may overlap. Overlap warnings
are conservative and should be reviewed by an operator.

## Parking Slots

Parking slots are individual polygons inside logical zones. A station may have
10-60 slots across multiple presets.

Slot types:

- `normal`
- `disabled`
- `service`
- `reserved`

Occupancy states:

- `unknown`
- `free`
- `occupied`
- `needs_review`

## Patrol Plan

Recommended future execution flow:

```text
Home preset
  -> enabled preset
  -> wait settle_time_ms
  -> capture burst
  -> publish preset.capture.ready
  -> next preset
  -> return Home
```

This MVP implements patrol configuration, validation, dry-run simulation, and
estimated cycle duration. It does not implement autonomous camera movement.

## Billing Limitation

One PTZ camera sees only one preset at a time.

Therefore:

- entry and exit timestamps may be delayed by the patrol interval
- a 60-second patrol cycle can create up to approximately 60 seconds of
  detection delay
- exact billing should preferably use a dedicated entrance/exit camera
- if only one PTZ camera exists, the Home/Entrance preset must have highest
  priority
- the system must not claim perfect continuous coverage of all 10-60 spaces

Parking rules documented for future integration:

- working hours: `07:00-22:00`
- first 10 minutes free
- `3 TJS / hour`
- zone types: `paid`, `no_parking`, `disabled`, `service`

## Deduplication Design

Future ALPR and occupancy logic should use these fields:

- `overlap_group`
- `deduplication_window_seconds`
- `event_id`
- `frame_hash`
- `preset_id`
- `zone_id`
- `slot_id`
- `tracking_id`

Use cases:

- same plate seen in overlapping presets
- same vehicle detected repeatedly during one patrol
- same parking slot visible in two presets
- same event uploaded twice after internet recovery

This MVP prepares configuration fields only. It does not implement fake
tracking.

## Local API

Base URL:

```text
http://localhost:8080/api/v1
```

Swagger:

```text
http://localhost:8080/docs
```

Local UI:

```text
http://localhost:8080/
```

Local API authentication is not implemented in this isolated MVP. It is required
before production deployment.

## Camera Diagnostics API

The local camera API supports:

```text
GET  /api/v1/camera/status
POST /api/v1/camera/test
POST /api/v1/camera/snapshot
GET  /api/v1/camera/snapshot/latest
POST /api/v1/camera/reconnect
```

Camera status reports only safe fields, including a redacted RTSP URL such as:

```text
rtsp://***:***@192.168.1.120:8554/...
```

Online means a valid video frame was decoded. TCP port reachability alone is not
treated as camera online.

Recommended `.env` settings for a real local test:

```text
RTSP_URL=rtsp://username:password@192.168.1.120:554/stream1
RTSP_TRANSPORT=tcp
RTSP_CONNECT_TIMEOUT_SECONDS=10
RTSP_READ_TIMEOUT_SECONDS=10
RTSP_RECONNECT_DELAY_SECONDS=3
RTSP_MAX_RECONNECT_DELAY_SECONDS=30
RTSP_LOW_LATENCY=true
CAMERA_NAME=Parking PTZ
CAMERA_VENDOR=generic
CAMERA_LOCAL_IP=192.168.1.120
SNAPSHOT_JPEG_QUALITY=90
PREVIEW_REFRESH_SECONDS=2
PTZ_DRY_RUN=true
```

Do not commit a real `.env` file.

## Real-Camera Calibration Workflow

1. Create or select a preset.
2. Keep the edge application in dry-run mode.
3. Manually position the PTZ camera using the camera vendor UI.
4. Capture a reference snapshot from RTSP.
5. Draw arbitrary polygon zones.
6. Create individual slot polygons.
7. Save the preset calibration.
8. Repeat for each camera position.

Real ONVIF preset movement remains disabled until:

- RTSP capture is stable
- ONVIF credentials are verified
- preset tokens are mapped
- manual approval is given
