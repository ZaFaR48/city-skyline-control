# Parking Session Engine

The pilot edge runtime keeps the local API/UI separate from continuous parking
monitoring.

Runtime concepts:

- Ubuntu auto-start: `city-skyline-edge.target` starts the API and worker after boot when enabled.
- Parking schedule: monitoring and billing logic uses `07:00-22:00` in `Asia/Dushanbe`.
- Future PTZ patrol: real movement remains blocked unless every approval gate is explicitly open.

## State Machine

Supported session states:

- `candidate`
- `active_free`
- `active_billable`
- `paid`
- `unpaid`
- `exit_pending`
- `closed`
- `violation_candidate`
- `needs_review`
- `cancelled`

One frame is not enough to confirm a vehicle. The pilot defaults are:

```text
SESSION_CONFIRMATION_OBSERVATIONS=2
SESSION_CONFIRMATION_WINDOW_SECONDS=120
SESSION_EXIT_MISSES=2
SESSION_EXIT_TIMEOUT_SECONDS=180
```

Active sessions are stored in SQLite and survive service restarts, mini PC
reboots, camera disconnects, and internet disconnects.

## Tariff

Pilot defaults:

```text
PARKING_TIMEZONE=Asia/Dushanbe
PARKING_START_TIME=07:00
PARKING_END_TIME=22:00
PARKING_FREE_MINUTES=10
PARKING_RATE_TJS_PER_HOUR=3.00
PARKING_ROUNDING_MODE=exact_minute
```

No charge accrues outside configured paid hours. The pilot default is
`exact_minute`; the business owner/legal policy must confirm the final rounding
mode before production.

## Payments

The current payment provider is `UnavailablePaymentProvider`.

It returns:

- `payment_status=unknown`
- `provider_status=not_integrated`

The system must not claim a driver did not pay while payment integration is
missing. Billable sessions become `needs_review`, not `unpaid`.

## Violation Candidates

Violation candidates are internal moderation records only. They are not legal
fines and are not sent to authorities.

A candidate can be created only when payment is explicitly confirmed unpaid by
a payment provider or an authorized operator.

## PTZ Patrol Safety

Real PTZ movement is refused unless all of these are true:

- `PTZ_DRY_RUN=false`
- `PTZ_AUTO_PATROL=true`
- `PTZ_PATROL_REQUIRE_APPROVAL=true`
- `PTZ_PATROL_APPROVED=true`
- ONVIF is configured
- preset mapping is validated

Pilot defaults keep real movement blocked:

```text
PTZ_DRY_RUN=true
PTZ_AUTO_PATROL=false
PTZ_PATROL_REQUIRE_APPROVAL=true
PTZ_PATROL_APPROVED=false
```
