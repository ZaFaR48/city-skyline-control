# One Station Test Plan

Do not test all 300 stations yet. Use one local mini PC and one local PTZ
camera.

## Phase 1

- copy application to one local mini PC
- configure one test camera
- keep `PTZ_DRY_RUN=true`
- run doctor
- test RTSP
- capture snapshot
- create one Home preset
- draw one polygon zone
- create 3-5 test parking slots
- restart application
- verify data persists

## Phase 2

- create multiple reference presets manually
- draw all required zones
- run patrol dry-run simulation
- verify estimated patrol cycle

## Phase 3

- run continuously for 24 hours
- observe reconnects
- observe CPU, RAM and disk
- disconnect internet
- verify local operation
- reconnect internet
- verify queue behavior

Record exact dates, station code, camera model, local IP, app version, and any
doctor failures in the test notes.
