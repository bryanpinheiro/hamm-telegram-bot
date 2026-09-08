# Hamm Telegram Bot

Hamm is a Telegram bot to help you manage your money by tracking inflow (money received) and outflow (money spent).

[@hamm_assets_bot](https://t.me/hamm_assets_bot)

## Features

- Track money inflow and outflow
- SQLite database for transaction history
- Structured logging with structlog
- Prometheus metrics for monitoring
- Grafana dashboards for visualization
- Thread-safe database operations

## Running Locally

### Prerequisites

- Python 3.12+
- Docker and Docker Compose (for monitoring stack)
- Telegram Bot API token from [@BotFather](https://t.me/botfather)

### Setup

1. Clone the repository:

```bash
git clone https://github.com/bryanpinheiro/hamm-telegram-bot.git
cd hamm-telegram-bot
```

2. Create a virtual environment and install dependencies:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Create a `.env` file:

```bash
cp .env.example .env
```

4. Edit `.env` and add your Telegram bot token:

```
API_TOKEN=your_telegram_bot_token_here
```

5. Run the bot:

```bash
cd src
python main.py
```

### Running with Monitoring Stack (Optional)

To run Prometheus and Grafana locally:

```bash
docker compose up -d
```

Access points:

- Grafana: <http://localhost:3701/grafana> (admin/admin)
- Prometheus (direct): <http://localhost:9091>
- Prometheus (behind `/prometheus` prefix): <http://localhost:9091/prometheus/>
- Bot metrics: <http://localhost:7001/metrics>
- Bot logs: <http://localhost:7002/logs>
- Landing page: <http://localhost:7002/>

Grafana and Prometheus are served under `/grafana` and `/prometheus` so the same
URLs work locally and behind the reverse proxy. Set `METRICS_PUBLIC_URL` in `.env` to the public base URL when deploying.

## Oracle Cloud VM Deployment

### Requirements

- Oracle Cloud VM running **Oracle Linux (RHEL-based)**
- Docker and Docker Compose installed
- Apache `httpd` installed as the system reverse proxy (ships with the base OS image on Oracle Linux)
- SSH access to the VM
- GitHub repository with workflow secrets configured

### Infrastructure Overview

The deployment uses Docker Compose to orchestrate three main services:

1. **telegrambot** - The Python bot application
2. **prometheus** - Metrics collection and storage
3. **grafana** - Metrics visualization and dashboards

### Network Architecture

```
┌─────────────────┐
│  Telegram API   │
│  (External)     │
└────────┬────────┘
         │ HTTPS (polling)
         ▼
┌─────────────────┐
│  Telegram Bot   │
│  (Container)    │
│  Port 8000      │
└────────┬────────┘
         │ Metrics (internal)
         ▼
┌─────────────────┐
│   Prometheus    │
│  (Container)    │
│  Port 9090      │
└────────┬────────┘
         │ Query (internal)
         ▼
┌─────────────────┐
│    Grafana      │
│  (Container)    │
│  Port 3000      │
└─────────────────┘
```

### Traffic Flow

**Telegram Communication:**

- The bot uses **polling** (not webhooks) to communicate with Telegram
- Bot actively polls Telegram's servers for updates
- No incoming traffic required from external sources
- This simplifies firewall configuration - no need to open ports

**Metrics Flow:**

- Bot exposes Prometheus metrics on port 8000 (container internal)
- Prometheus scrapes metrics from bot every 15 seconds
- Grafana queries Prometheus for data visualization
- All monitoring services communicate via Docker bridge network
- External access to metrics is bound to 127.0.0.1 (localhost only) for security

### Port Bindings

| Service     | Container Port | Host Port | Access         |
| ----------- | -------------- | --------- | -------------- |
| Bot Metrics | 8000           | 7001      | 127.0.0.1:7001 |
| Bot Logs    | 8001           | 7002      | 127.0.0.1:7002 |
| Prometheus  | 9090           | 9091      | 127.0.0.1:9091 |
| Grafana     | 3000           | 3701      | 127.0.0.1:3701 |

All ports are bound to localhost only, and are reached through the Apache reverse proxy (see [Monitoring](#monitoring) below).

### GitHub Actions Deployment

The project uses GitHub Actions for automated deployment:

1. Push to `main` branch triggers deployment
2. Workflow connects to Oracle VM via SSH
3. Pulls latest code and rebuilds containers
4. Cleans up unused Docker images

**Required GitHub Secrets:**

- `ORACLE_HOST` - VM IP address
- `ORACLE_USERNAME` - SSH username
- `ORACLE_SSH_KEY` - SSH private key
- `ORACLE_SSH_PORT` - SSH port (default 22)

### Environment Variables

Create `.env` file on the VM:

```
API_TOKEN=your_telegram_bot_token
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=secure_password
METRICS_PUBLIC_URL=https://metrics.example.com
BOT_USERNAME=hamm_assets_bot
```

`BOT_USERNAME` is the Telegram handle the landing page button links to (a leading `@` is stripped). `.env` is read at container start, so run `docker compose up -d --build` after changing it.

## Database

The bot uses SQLite with explicit SQL queries:

- Direct SQL control for transparency
- Single connection with `check_same_thread=False` for telebot compatibility (multi-threaded polling)
- Automatic schema initialization on first run
- Data persists in `/app/data` volume

**Note:** Since the bot only handles single-user accounts (no transfers between users), complex transaction isolation is not needed. SQLite's default transaction isolation is sufficient for this use case.

## Monitoring

### Prometheus Metrics

The bot exposes the following metrics:

- `bot_inflow_total` - Total inflow transactions
- `bot_outflow_total` - Total outflow transactions
- `bot_messages_total` - Total messages received
- `bot_callbacks_total` - Total callback queries received

### Grafana Setup

This walks through connecting Grafana to Prometheus and viewing it from your own domain, step by step. It assumes you've already deployed the stack (see [Oracle Cloud VM Deployment](#oracle-cloud-vm-deployment)) and set up the reverse proxy below.

1. Open Grafana in your browser at your public URL, e.g. `https://metrics.example.com/grafana/` (or `http://localhost:3701/grafana` if you're just testing locally, before setting up the domain).
2. Log in with `admin` / `admin`, then set a new password when prompted.
3. In the left sidebar go to **Connections → Data sources → prometheus** (or **Add new connection** if it doesn't exist yet).
4. In the **Prometheus server URL** field, do **not** use `localhost`. Grafana and Prometheus run in separate Docker containers, so `localhost` from Grafana's point of view means "the Grafana container itself," not Prometheus. Instead, use the Docker Compose **service name**, which is how containers find each other on the internal Docker network:

   ```
   http://prometheus:9090
   ```

   (`prometheus` is the service name defined in `docker-compose.yml` — confirm it matches if you renamed it.)
5. Click **Save & test**. You should see a green "Successfully queried the Prometheus API" message.
6. Import or create dashboards to start visualizing metrics.

### Exposing Grafana on Your Own Domain (Apache on Oracle Linux)

By default, Grafana, Prometheus, and the bot's metrics only listen on `127.0.0.1` on the VM — they aren't reachable from the internet. To view them at a real URL like `https://metrics.example.com`, Apache sits in front as a **reverse proxy**: it receives the public request and forwards it internally to the right container.

This section assumes an Oracle Cloud VM running **Oracle Linux (RHEL-based)**, with Apache (`httpd`) already installed. (Oracle Linux uses the `httpd` package, not Debian/Ubuntu's `apache2` — there's no `a2enmod` command here. The proxy modules this setup needs, `mod_proxy`, `mod_proxy_http`, `mod_proxy_wstunnel`, and `mod_rewrite`, are already built in and loaded on a standard `httpd` install, so no extra step is needed to enable them.)

#### Step 1 — Point your domain at the VM

In your DNS provider's dashboard, add an **A record** so your subdomain resolves to the VM's public IP:

- **Type:** A
- **Name:** `metrics` (or whatever subdomain you want, e.g. `metrics.example.com`)
- **Value:** your Oracle VM's public IP address
- **TTL:** 300 (or the provider's default)

DNS changes can take a few minutes to propagate. You can check with `dig metrics.example.com` or `nslookup metrics.example.com` before moving on.

#### Step 2 — Tell the bot its public URL

On the VM, edit `.env` and set:

```
METRICS_PUBLIC_URL=https://metrics.example.com
```

Grafana and Prometheus use this to build correct links and redirects when served under a sub-path like `/grafana/`.

#### Step 3 — Create the Apache config file (HTTP first)

Create a new file at `/etc/httpd/conf.d/metrics.conf` (Oracle Linux automatically loads every file in `conf.d/`) with the following content. This tells Apache: "requests to `metrics.example.com/grafana/` should be forwarded to the Grafana container on port 3701," and similarly for Prometheus and the bot's endpoints.

```apache
<VirtualHost *:80>
    ServerName metrics.example.com

    ProxyPreserveHost On

    # Sub-paths must keep their trailing slash, otherwise the proxied app
    # receives an empty path and returns 404
    RedirectMatch ^/grafana$ /grafana/
    RedirectMatch ^/prometheus$ /prometheus/

    # Grafana Live uses websockets, which must be matched before the
    # plain http ProxyPass below
    RewriteEngine On
    RewriteCond %{HTTP:Upgrade} =websocket [NC]
    RewriteRule ^/grafana/(.*) ws://127.0.0.1:3701/grafana/$1 [P,L]

    # Grafana
    ProxyPass /grafana/ http://127.0.0.1:3701/grafana/
    ProxyPassReverse /grafana/ http://127.0.0.1:3701/grafana/

    # Prometheus
    ProxyPass /prometheus/ http://127.0.0.1:9091/
    ProxyPassReverse /prometheus/ http://127.0.0.1:9091/

    # Bot metrics
    ProxyPass /bot-metrics http://127.0.0.1:7001/metrics
    ProxyPassReverse /bot-metrics http://127.0.0.1:7001/metrics

    # Bot logs
    ProxyPass /logs http://127.0.0.1:7002/logs
    ProxyPassReverse /logs http://127.0.0.1:7002/logs

    # Landing page (root only, so unknown paths still 404 on Apache)
    ProxyPassMatch ^/$ http://127.0.0.1:7002/
    ProxyPassReverse / http://127.0.0.1:7002/
</VirtualHost>
```

#### Step 4 — Allow Apache to reach the containers

Two safety features are on by default on Oracle Linux and will silently block this setup unless you explicitly allow it:

**SELinux** stops Apache from opening outbound connections (needed to reach the Docker containers):

```bash
sudo setsebool -P httpd_can_network_connect 1
```

**firewalld** needs the HTTP/HTTPS ports open so the outside world can reach Apache in the first place:

```bash
sudo firewall-cmd --permanent --add-service=http --add-service=https
sudo firewall-cmd --reload
```

> If your VM is on Oracle Cloud, also double-check the **Security List / Network Security Group** in the OCI console — Oracle Cloud has its own firewall layer separate from `firewalld`, and it also needs ports 80/443 open.

#### Step 5 — Test and reload Apache

```bash
sudo apachectl configtest
sudo systemctl restart httpd
```

`configtest` should print `Syntax OK`. At this point, `http://metrics.example.com/grafana/` should already work over plain HTTP.

#### Step 6 — Add HTTPS with a free certificate (Let's Encrypt)

Once the HTTP VirtualHost above is working, run certbot to get a certificate and automatically upgrade the config to HTTPS. This assumes `certbot` and `python3-certbot-apache` are already installed on the VM.

```bash
sudo certbot --apache -d metrics.example.com
```

Certbot will edit `/etc/httpd/conf.d/metrics.conf` for you, adding a matching `<VirtualHost *:443>` block with the SSL certificate paths, and reload Apache automatically.

If a `<VirtualHost *:443>` block already exists from an earlier certbot run, certbot leaves its contents alone — copy any proxy directives you changed in step 3 into that block by hand, otherwise they only apply over plain HTTP.

If a certificate already exists for that domain (e.g. you're re-running this), certbot will ask:

```
1: Attempt to reinstall this existing certificate
2: Renew & replace the certificate (may be subject to CA rate limits)
```

Choose **1** unless the current certificate is broken or you need to add/remove domains — unnecessary renewals count against Let's Encrypt's rate limit (5 certificates per domain per week).

Certbot installs a systemd timer that renews the certificate automatically before it expires. Confirm it's active:

```bash
sudo systemctl enable --now certbot-renew.timer
```

You can simulate a renewal at any time, without actually renewing, using:

```bash
sudo certbot renew --dry-run
```

#### Step 7 — Verify everything works

Open these in your browser:

- `https://metrics.example.com/grafana/` → Grafana dashboard
- `https://metrics.example.com/prometheus/` → Prometheus UI
- `https://metrics.example.com/bot-metrics` → Raw bot metrics
- `https://metrics.example.com/logs` → Bot logs (HTML view)
- `https://metrics.example.com/` → Landing page with the "Open in Telegram" button

If something doesn't load, check the container itself first, directly on the VM, before assuming Apache is the problem (`-I` sends a HEAD request, which Prometheus rejects with 405, so use GET):

```bash
curl -sS -o /dev/null -w '%{http_code} %{redirect_url}\n' http://127.0.0.1:3701/grafana/  # Grafana
curl -sS -o /dev/null -w '%{http_code} %{redirect_url}\n' http://127.0.0.1:9091/          # Prometheus
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:7001/metrics                   # Bot metrics
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:7002/logs                      # Bot logs
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:7002/                          # Landing page
```

If these `curl` commands fail or time out, the problem is the container, not Apache — check with `docker compose ps` and `docker compose logs <service>`. If they succeed but the public URL doesn't work, the problem is in the Apache config, SELinux, or the firewall — revisit steps 3–5.

## Project Structure

```
hamm-telegram-bot/
├── src/
│   ├── main.py           # Application entry point
│   ├── bot.py            # Bot controller with handlers
│   ├── repository.py     # Database operations
│   ├── logger.py         # Logging configuration
│   └── landing.py        # Root landing page served on the logs port
├── Dockerfile            # Container image definition
├── docker-compose.yml    # Service orchestration
├── prometheus.yml        # Prometheus configuration
├── requirements.txt      # Python dependencies
└── .github/workflows/
    └── deploy.yml        # CI/CD pipeline
```

## Development

### Adding New Features

1. Add handlers in `bot.py`
2. Add database methods in `repository.py`
3. Add logging with `Logger.get_logger(__name__)`
4. Add metrics with Prometheus counters

### Testing

```bash
# Run locally
cd src
python main.py

# Test with Docker Compose
docker compose up --build
```
