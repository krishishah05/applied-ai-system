# Deployment Guide

## Prerequisites

Before deploying, set all required environment variables:

- `DATABASE_URL` — PostgreSQL connection string for the production database
- `AUTH_SECRET_KEY` — Signing key for authentication; must be long and unpredictable
- `ACCESS_EXPIRY_SECONDS` — How long a session credential remains valid (default: 3600)
- `PORT` — Port the server listens on (default: 8000)

## Steps to Deploy

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Run database migrations:
   ```
   python manage.py migrate
   ```

3. Collect static files:
   ```
   python manage.py collectstatic
   ```

4. Start the production server:
   ```
   gunicorn app:application --workers 4 --bind 0.0.0.0:$PORT
   ```

## Health Check

After deploying, verify the service is running:

```
GET /api/health
```

Expected response: `{"status": "ok", "version": "1.0"}`

## Rollback

To roll back, redeploy the last stable Docker image tag or
run `git checkout <previous-tag>` and restart the server.
