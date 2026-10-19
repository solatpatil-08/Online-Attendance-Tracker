# Production Deployment & Readiness Guide

This guide provides technical instructions for configuring, securing, and deploying the **Online Attendance Tracking System** in a public or institutional production environment.

---

## 🏗️ 1. Production Architecture Overview

In a production environment, the system utilizes a multi-tier, industry-standard architecture:

```
[ User Web Browser ]
        │  HTTPS (Port 443)
        ▼
[ Reverse Proxy: Nginx / Cloudflare / AWS ALB ]  <-- SSL/TLS Termination, Rate Limiting, DDoS Protection
        │  HTTP (Reverse Proxy Header: X-Forwarded-Proto = https)
        ▼
[ Production WSGI Server: Gunicorn / Waitress ]  <-- Multi-worker process management
        │
   ┌────┴──────────────────────────┐
   ▼                               ▼
[ Django Application Core ]   [ WhiteNoise Middleware ]  <-- Serves compressed, cache-busted static assets
   │
   ▼  PostgreSQL Connection Pool (conn_max_age=600, conn_health_checks=True)
[ PostgreSQL 14+ Relational Database ]
```

---

## ⚙️ 2. Environment Configuration Reference

All secrets, infrastructure endpoints, and runtime toggles must be configured via environment variables.

| Environment Variable | Required | Type | Production Recommendation | Description |
|---|---|---|---|---|
| `SECRET_KEY` | **Yes** | String | 50+ char random string | Cryptographic key used for sessions, password resets, and CSRF token signing. Must **never** be committed or use default development prefixes. |
| `DEBUG` | **Yes** | Boolean | `False` | Disables standard Django debug error pages and sensitive traceback leakage. |
| `ALLOWED_HOSTS` | **Yes** | CSV String | `attendance.institution.edu` | Comma-delimited list of host/domain names that this application is allowed to serve. |
| `CSRF_TRUSTED_ORIGINS` | **Yes** | CSV String | `https://attendance.institution.edu` | Comma-delimited list of trusted origin URLs (including `https://`) allowed to send POST/mutation requests. |
| `DATABASE_URL` | **Yes** | URI String | `postgresql://user:pass@host:5432/dbname` | Full database connection string. Enables PostgreSQL with connection pooling. |
| `CONN_MAX_AGE` | No | Integer | `600` | Lifetime (in seconds) of persistent database connections. Reduces per-request handshake overhead. |
| `SECURE_SSL_REDIRECT` | No | Boolean | `True` | Redirects all unencrypted HTTP traffic to HTTPS. |
| `USE_X_FORWARDED_PROTO` | No | Boolean | `True` | Instructs Django to trust `X-Forwarded-Proto: https` from an upstream reverse proxy (Nginx, AWS ALB, Cloudflare). |
| `SECURE_HSTS_SECONDS` | No | Integer | `31536000` (1 year) | Instructs client browsers to strictly communicate over HTTPS via the HTTP Strict Transport Security header. |
| `SECURE_HSTS_SUBDOMAINS`| No | Boolean | `True` | Applies HSTS policy to all subdomains. |
| `SECURE_HSTS_PRELOAD` | No | Boolean | `True` | Requests inclusion in the global browser HSTS preload list. |
| `SESSION_COOKIE_AGE` | No | Integer | `1209600` (14 days) | Age in seconds for user sessions. |
| `MAX_BACKDATED_ATTENDANCE_DAYS` | No | Integer | `7` | Maximum number of past calendar days faculty can backdate roll-call attendance without administrative override. |
| `LOG_LEVEL` | No | String | `INFO` | Base logging level for stdout/stderr log emission. |
| `DJANGO_LOG_LEVEL` | No | String | `INFO` | Django subsystem logging level. |

---

## 🗄️ 3. Database: PostgreSQL vs. SQLite Technical Evaluation

### Why SQLite is Unsuitable for Production Attendance Tracking
1. **Concurrency and Table/Database Locking:** SQLite operates with database-level write locks. In an institutional setting, dozens of instructors simultaneously mark roll call at class period intervals (e.g. 9:00 AM, 11:00 AM). Concurrent write bursts on SQLite trigger `sqlite3.OperationalError: database is locked` exceptions, dropping attendance records.
2. **PostgreSQL Row-Level MVCC:** PostgreSQL uses Multi-Version Concurrency Control (MVCC) with row-level locking. Multiple instructors marking attendance for different classrooms simultaneously write in parallel without contention.
3. **Connection Pooling & Health Checking:** PostgreSQL supports connection pooling (`CONN_MAX_AGE=600`, `conn_health_checks=True`), reducing TLS handshake overhead and scaling to high concurrent traffic.
4. **Data Durability & High Availability:** PostgreSQL supports Write-Ahead Logging (WAL), continuous archiving, read replicas, point-in-time recovery (PITR), and managed cloud failover (AWS RDS, GCP Cloud SQL, Supabase, Neon).

> [!NOTE]
> SQLite support is intentionally preserved in the codebase for local development and rapid test suite execution. When `DATABASE_URL` and `DB_ENGINE` are absent from the environment, the system automatically falls back to SQLite.

### PostgreSQL Setup & Migration Instructions

#### Step 1: Install PostgreSQL Server and Create Database
On your database server (or cloud database dashboard):

```sql
-- Create production database user
CREATE USER attendance_user WITH PASSWORD 'ReplaceWithStrongDbPassword123!';

-- Create production database owned by the user
CREATE DATABASE attendance_db OWNER attendance_user;

-- Grant schema privileges
GRANT ALL PRIVILEGES ON DATABASE attendance_db TO attendance_user;
```

#### Step 2: Configure `DATABASE_URL` in Production Environment
In your production environment or secrets manager:
```ini
DATABASE_URL=postgresql://attendance_user:ReplaceWithStrongDbPassword123!@127.0.0.1:5432/attendance_db
```

#### Step 3: Run Database Migrations
```bash
python manage.py migrate
```

#### Optional: Migrating Existing Development Data from SQLite to PostgreSQL
If migrating existing data from a local SQLite instance to PostgreSQL:
```bash
# 1. Dump data from SQLite excluding contenttypes and permissions
python manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.Permission --indent 2 > datadump.json

# 2. Point environment to PostgreSQL (set DATABASE_URL)
# 3. Apply schema migrations on PostgreSQL
python manage.py migrate

# 4. Load dumped data into PostgreSQL
python manage.py loaddata datadump.json
```

---

## 🔒 4. Security Hardening & Verification

### Built-in Production Safeguards
1. **Secret Key Guard:** `settings.py` prevents starting with default or `django-insecure-` keys when `DEBUG=False`.
2. **Automated Deployment Verification:** `python manage.py check --deploy` verifies that cookies are secure, HSTS is configured, SSL redirect is active, and clickjacking protection is in place.
3. **Demo & Development Account Lockout:** The management commands `create_dev_users` (`admin123`/`teacher123`), `seed_sample_data`, and `seed_demo_data` are strictly blocked when `DEBUG=False`. Attempting to run them in production aborts with `CommandError` unless `--confirm-production` is explicitly passed.
4. **Cookie Security:**
   - `SESSION_COOKIE_HTTPONLY = True` (mitigates JavaScript cookie theft)
   - `CSRF_COOKIE_HTTPONLY = True` (forms use hidden input `{% csrf_token %}`)
   - `SESSION_COOKIE_SECURE = True` (cookies only transmitted over HTTPS)
   - `CSRF_COOKIE_SECURE = True`
   - `SESSION_COOKIE_SAMESITE = 'Lax'`
   - `CSRF_COOKIE_SAMESITE = 'Lax'`
5. **Static File Serving (WhiteNoise):** WhiteNoise serves static files directly via WSGI with gzip/brotli compression and content-hashed filenames (`CompressedManifestStaticFilesStorage`), enabling infinite-cache HTTP headers without Nginx file routing errors.

---

## 🚀 5. Step-by-Step Deployment Walkthrough

### Step 1: Install System Prerequisites (Ubuntu/Debian Example)
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip libpq-dev nginx
```

### Step 2: Clone Codebase and Configure Virtual Environment
```bash
cd /var/www
sudo git clone https://github.com/solatpatil-08/Online-Attendance-Tracker.git attendance-system
cd attendance-system

# Create and activate virtual environment
sudo python3 -m venv .venv
sudo chown -R www-data:www-data /var/www/attendance-system
source .venv/bin/activate
```

### Step 3: Install Production Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Generate a Cryptographic `SECRET_KEY`
```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

### Step 5: Configure Production Environment Variables
Create `/var/www/attendance-system/.env` (permissions `600`, owned by `www-data`):
```ini
# Django Core Settings
SECRET_KEY=your_generated_cryptographic_secret_key_from_step_4
DEBUG=False
ALLOWED_HOSTS=attendance.yourinstitution.edu,127.0.0.1

# CSRF Trusted Origins (must include https://)
CSRF_TRUSTED_ORIGINS=https://attendance.yourinstitution.edu

# Production Database (PostgreSQL)
DATABASE_URL=postgresql://attendance_user:YourDbPassword@127.0.0.1:5432/attendance_db
CONN_MAX_AGE=600

# HTTPS & Proxy Security
SECURE_SSL_REDIRECT=True
USE_X_FORWARDED_PROTO=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True

# Attendance Business Rules
MAX_BACKDATED_ATTENDANCE_DAYS=7
SESSION_COOKIE_AGE=1209600
```

### Step 6: Apply Database Migrations
```bash
python manage.py migrate
```

### Step 7: Collect and Hash Static Files
```bash
python manage.py collectstatic --noinput
```

### Step 8: Create Initial Administrator Account
```bash
python manage.py createsuperuser
```
*(Enter the institutional administrator username, email, and strong password when prompted).*

### Step 9: Run Django Deployment Check
Verify that zero security warnings or configuration defects exist:
```bash
python manage.py check --deploy
```
*Expected output:*
```text
System check identified no issues (0 silenced).
```

### Step 10: Configure WSGI Application Server

#### Option A: Gunicorn (Linux Production Standard)
Create a systemd unit `/etc/systemd/system/attendance.service`:
```ini
[Unit]
Description=Online Attendance Tracking System (Gunicorn WSGI)
After=network.target postgresql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/attendance-system
EnvironmentFile=/var/www/attendance-system/.env
ExecStart=/var/www/attendance-system/.venv/bin/gunicorn \
    --workers 4 \
    --threads 2 \
    --bind 127.0.0.1:8000 \
    --timeout 60 \
    --access-logfile - \
    --error-logfile - \
    config.wsgi:application

Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable attendance
sudo systemctl start attendance
sudo systemctl status attendance
```

#### Option B: Waitress (Windows Server Production)
On Windows Server, run Waitress as a Windows Service or via task scheduler:
```powershell
python -m waitress --listen=127.0.0.1:8000 --threads=8 config.wsgi:application
```

### Step 11: Configure Reverse Proxy (Nginx) & SSL/TLS
Create `/etc/nginx/sites-available/attendance`:
```nginx
server {
    listen 80;
    server_name attendance.yourinstitution.edu;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name attendance.yourinstitution.edu;

    ssl_certificate /etc/letsencrypt/live/attendance.yourinstitution.edu/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/attendance.yourinstitution.edu/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    client_max_body_size 25M;

    # Media uploads directory
    location /media/ {
        alias /var/www/attendance-system/media/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    # Proxy all application requests (WhiteNoise handles /static/)
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_redirect off;
    }
}
```

Enable the Nginx site and obtain SSL certificate with Certbot:
```bash
sudo ln -s /etc/nginx/sites-available/attendance /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Install SSL Certificate via Let's Encrypt
sudo certbot --nginx -d attendance.yourinstitution.edu
```

---

## ✅ 6. Remaining Manual Configuration Checklist

Before opening the deployed application to institutional end users, review and complete each item:

- [ ] **DNS Record:** Point your institutional domain/subdomain `A` record to the production server public IP.
- [ ] **SSL/TLS Certificate:** Verify that the SSL certificate is valid and auto-renewal is scheduled (`certbot renew --dry-run`).
- [ ] **Database Backups:** Schedule automated daily backups for PostgreSQL (e.g. `pg_dump` cron job or managed cloud snapshot).
- [ ] **Media Directory Permissions:** Ensure the `media/` directory exists and is writable by the application worker user (`chmod 750 media`).
- [ ] **Firewall Hardening:** Restrict incoming server ports to `80` (HTTP), `443` (HTTPS), and `22` (SSH). Ensure PostgreSQL port `5432` is bound only to `127.0.0.1` or a private VPC subnet.
- [ ] **Admin Password Verification:** Ensure the initial superuser created via `createsuperuser` has a strong, unique password and two-factor or institutional SSO if applicable.
- [ ] **Disable Unused Demo Scripts:** Verify that no automated cron jobs or deployment scripts invoke `create_dev_users` or `seed_demo_data`.
- [ ] **Test Live Authentication & Attendance Submission:** Perform a test login as an administrator and teacher over HTTPS, verify CSS/JS rendering, and test an attendance submission.
