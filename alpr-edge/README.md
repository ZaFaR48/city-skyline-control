# ALPR Edge MVP

Safe Python-first skeleton for an edge ALPR application at parking stations.

This module is intentionally isolated from the existing dashboard, backend,
database schema, and Telegram bot. It does not integrate with the central
FastAPI server yet.

## Current Scope

- Load runtime settings from `.env`.
- Connect to a local RTSP/IP camera using OpenCV.
- Read frames continuously.
- Sample one frame every configured interval.
- Save sampled frames locally for inspection and model testing.
- Provide interfaces for real plate detection, OCR, and event upload.
- Queue event JSON files locally when the central server is unavailable.
- Retry queued events later.
- Run a local parking session engine with restart-safe SQLite state.

The MVP does not perform fake plate recognition. If no detector/OCR model is
configured, the app logs:

```text
ALPR model not configured; frame captured only.
```

## Folder Layout

```text
alpr-edge/
  README.md
  requirements.txt
  .env.example
  app/
    __init__.py
    main.py
    config.py
    camera.py
    detector.py
    ocr.py
    event_queue.py
    api_client.py
    models.py
    logger.py
  scripts/
    run_dev.sh
    run_api.sh
    run_edge.sh
  deployment/
    systemd/
    ubuntu/
  docs/
```

## Business Rules To Preserve

- Working hours: `07:00-22:00`
- First 10 minutes free
- Parking rate: `1 hour = 3 TJS`
- Supported zone types:
  - `paid_parking`
  - `no_parking`
  - `disabled_only`

These rules are documented here for the future backend integration. They are
not enforced by this edge skeleton yet.

## Event Schema

Future uploaded events should use this shape:

```json
{
  "station_code": "STATION-001",
  "camera_id": "CAM-001",
  "timestamp": "2026-07-03T15:30:00Z",
  "plate_text": null,
  "confidence": null,
  "image_path": "data/frames/sample.jpg",
  "direction": "unknown",
  "zone_type": "paid_parking",
  "status": "needs_review"
}
```

Allowed statuses:

- `detected`
- `needs_review`
- `rejected`
- `confirmed`

## Setup

```bash
cd /opt/city-skyline-control/alpr-edge
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with the local camera URL and station metadata. Do not commit real
secrets or production environment files.

## Run

```bash
./scripts/run_dev.sh
```

or:

```bash
python -m app.main
```

## Run The Local PTZ Zone Designer

The PTZ designer is a separate local FastAPI application and does not replace
the ALPR frame sampling loop.

```bash
uvicorn app.api.main:app --host 127.0.0.1 --port 18080
```

Local UI:

```text
http://localhost:18080/
```

Swagger:

```text
http://localhost:18080/docs
```

API base:

```text
http://localhost:18080/api/v1
```

PTZ dry-run mode is enabled by default:

```text
PTZ_DRY_RUN=true
```

Real ONVIF movement remains disabled in this MVP.

## Real RTSP Camera Test Workflow

1. Copy `.env.example` to `.env`.
2. Set `RTSP_URL`, `CAMERA_NAME`, `CAMERA_VENDOR`, and `CAMERA_LOCAL_IP`.
3. Keep `PTZ_DRY_RUN=true`.
4. Start the local API/UI.
5. Open `http://localhost:18080/`.
6. Use **Test Camera** to verify a decoded frame.
7. Select or create a preset.
8. Manually position the PTZ camera in the camera vendor UI.
9. Use **Capture Snapshot** to save a reference image.
10. Draw normalized zone and slot polygons over that snapshot.

The video stream stays local to the mini PC. This MVP does not send continuous
video to the central server and does not perform ALPR recognition.

Ubuntu station deployment materials live in
`docs/UBUNTU_EDGE_DEPLOYMENT.md`. Do not run the installer from the central
server; copy this package to the local mini PC at the test parking station.

Pilot release packaging is documented in `docs/PILOT_DEPLOYMENT_RUNBOOK.md`.
Build archives with `./scripts/build_pilot_release.sh` and verify them with
`./scripts/verify_pilot_release.sh`.

The continuous parking session engine is documented in
`docs/PARKING_SESSION_ENGINE.md`. The worker is separate from the local API/UI
and can be run manually with:

```bash
./scripts/run_worker.sh
```

Real ONVIF preset movement should be enabled only after RTSP capture is stable,
ONVIF credentials are verified, preset tokens are mapped, and manual approval is
given.

## Model Integration Notes

`PlateDetector` and `PlateOCR` are placeholders for real model adapters. A real
implementation should:

- Load configured model files from local paths.
- Return bounding boxes and confidence values from the detector.
- Run OCR only on detector crops.
- Mark low-confidence or ambiguous reads as `needs_review`.
- Avoid making final parking decisions on the edge device until the central
  server contract is defined.

No large model files are included or downloaded by this skeleton.

## Offline Queue

When `CENTRAL_API_URL` is configured, `EventUploader` posts events to the future
central API endpoint. If upload fails, the event is stored as JSON in
`QUEUE_DIR`. The app periodically retries pending queue files and deletes a file
only after the server accepts it.

When the central API is not configured, events remain local and no network call
is attempted.

## Windows Notes

The application uses `pathlib` and avoids shell-specific paths in Python code.
The `scripts/run_dev.sh` helper is for Ubuntu/Linux development; on Windows, run
`python -m app.main` from the `alpr-edge` directory after activating a virtual
environment.
