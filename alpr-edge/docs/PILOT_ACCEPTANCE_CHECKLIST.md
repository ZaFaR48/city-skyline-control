# Pilot Acceptance Checklist

Station code: __________

Camera ID: __________

Mini PC operator: __________

Test date: __________

Use PASS or FAIL for each item and attach notes for any failure.

| Item | PASS | FAIL | Notes |
| --- | --- | --- | --- |
| Ubuntu version is 22.04 or 24.04 |  |  |  |
| Python version is 3.10 or newer |  |  |  |
| Timezone is Asia/Dushanbe |  |  |  |
| NTP synchronized |  |  |  |
| Camera ping succeeds |  |  |  |
| RTSP TCP port reachable |  |  |  |
| Decoded video frame confirmed |  |  |  |
| Snapshot saved |  |  |  |
| API health returns ok |  |  |  |
| UI loaded through SSH/VPN tunnel |  |  |  |
| PTZ dry-run true |  |  |  |
| Home preset saved |  |  |  |
| Polygon saved |  |  |  |
| 3-5 parking slots saved |  |  |  |
| SQLite persistence confirmed after restart |  |  |  |
| Service restart succeeds |  |  |  |
| No secrets in logs or support bundle |  |  |  |
| No public port exposure |  |  |  |
| CPU acceptable during pilot |  |  |  |
| RAM acceptable during pilot |  |  |  |
| Disk space acceptable during pilot |  |  |  |
| 24-hour stability test completed |  |  |  |

Pilot result:

- PASS:
- FAIL:
- Follow-up required:

This checklist does not approve production rollout.
