# Codex Context

This project is City Skyline / CityParking only. MAGZ is separate and must not be touched.

## Canonical Paths

```text
backend:      /opt/city-skyline-control/backend
frontend:     /opt/city-skyline-control/frontend
telegram bot: /opt/city-skyline-control/telegram-bot
ALPR edge:    /opt/city-skyline-control/alpr-edge
```

## Services And Ports

```text
backend service:  city-backend.service
frontend service: city-frontend.service
backend port:     8001
frontend port:    3002
dashboard URL:    http://13.140.180.178:3002/map
```

The frontend service should run from `/opt/city-skyline-control/frontend`.

The backend service should run from `/opt/city-skyline-control/backend`.

## Do Not Touch

Do not modify MAGZ paths, MAGZ Docker containers, or MAGZ ports:

```text
/opt/magz
magz-web
magz-postgres
3000
5433
```

Do not delete:

```text
/opt/_old_city_versions/city-skyline-control-backup
```

That directory is the emergency rollback source for the frontend.

## Rollback

Use the latest consolidation backup if frontend service rollback is needed. For this migration:

```bash
cp -a /root/city-consolidation-backup-20260710-201017/etc-systemd-system/city-frontend.service /etc/systemd/system/city-frontend.service
systemctl daemon-reload
systemctl restart city-frontend.service
systemctl status city-frontend.service --no-pager
```

After rollback, verify:

```bash
curl -I http://127.0.0.1:3002
curl -I http://13.140.180.178:3002/map
```
