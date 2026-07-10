# City Skyline Architecture

This repository is for City Skyline / CityParking only.

MAGZ is a separate system. Do not touch MAGZ paths, MAGZ Docker containers, or MAGZ ports from this project.

## Runtime Layout

Project root:

```text
/opt/city-skyline-control
```

Important paths:

```text
/opt/city-skyline-control/backend
/opt/city-skyline-control/frontend
/opt/city-skyline-control/telegram-bot
/opt/city-skyline-control/alpr-edge
```

Services:

```text
city-backend.service
city-frontend.service
```

Ports:

```text
backend: 8001
frontend: 3002
```

Current dashboard URL:

```text
http://13.140.180.178:3002/map
```

## Frontend

The production frontend service runs from:

```text
/opt/city-skyline-control/frontend
```

The service command is:

```text
/usr/bin/npm run preview -- --host 0.0.0.0 --port 3002
```

Do not delete this emergency rollback source:

```text
/opt/_old_city_versions/city-skyline-control-backup
```

## Backend

The production backend service runs from:

```text
/opt/city-skyline-control/backend
```

The backend API listens on port `8001`.

## Safety Boundaries

Do not edit or delete:

```text
/opt/magz
magz-web
magz-postgres
Docker containers related to MAGZ
ports 3000 or 5433
/opt/_old_city_versions/city-skyline-control-backup
```

Do not change backend API behavior, database schema, frontend visuals, Telegram bot behavior, or ALPR edge behavior during architecture cleanup tasks.

## Frontend Rollback

The current consolidation backup is:

```text
/root/city-consolidation-backup-20260710-201017
```

To restore the previous frontend service definition:

```bash
cp -a /root/city-consolidation-backup-20260710-201017/etc-systemd-system/city-frontend.service /etc/systemd/system/city-frontend.service
systemctl daemon-reload
systemctl restart city-frontend.service
systemctl status city-frontend.service --no-pager
```
