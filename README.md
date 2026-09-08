# Hamm Telegram Bot

Hamm is a Telegram bot to help you manage your money by tracking inflow (money received) and outflow (money spent).

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

All ports are bound to localhost only. Access via SSH tunnel if needed:

```bash
ssh -L 3701:localhost:3701 user@your-server
ssh -L 9091:localhost:9091 user@your-server
ssh -L 7002:localhost:7002 user@your-server
```

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
```

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

1. Access Grafana at <http://localhost:3701/grafana>
2. Login with admin/admin (change password after first login)
3. Add Prometheus data source: <http://prometheus:9090>
4. Import or create dashboards to visualize metrics

### Subdomain Configuration (Apache on Oracle Linux)

If using a single subdomain (e.g., `metrics.example.com`) with Apache `httpd` as reverse proxy, on **Oracle Linux / RHEL-based systems**.

> **Note:** Oracle Linux ships `httpd` (not Debian/Ubuntu's `apache2` package), so there is no `a2enmod` tool. Modules are enabled via `LoadModule` lines and, on a standard `httpd` install, the ones needed here (`mod_proxy`, `mod_proxy_http`, `mod_proxy_wstunnel`, `mod_rewrite`) are already compiled in and loaded by default — nothing to enable.

#### 1. Create DNS Record

Add an A record in your domain's DNS settings:

- **Type:** A
- **Name:** metrics (or your desired subdomain)
- **Value:** Your Oracle VM public IP address
- **TTL:** 300 (or default)

#### 2. Verify Apache Proxy Modules Are Loaded

```bash
httpd -M | grep -E 'proxy_module|proxy_http_module|proxy_wstunnel_module|rewrite_module'
```

You should see all four listed as `(shared)`. If any are missing, find their `LoadModule` line (commented out) under `/etc/httpd/conf.modules.d/` — typically in `00-proxy.conf` or `00-base.conf` — and uncomment it:

```bash
sudo grep -rn "proxy_module\|proxy_http_module\|proxy_wstunnel_module\|rewrite_module" /etc/httpd/conf.modules.d/
```

Then reload:

```bash
sudo apachectl configtest
sudo systemctl restart httpd
```

#### 3. Configure Apache VirtualHost (HTTP)

Set `METRICS_PUBLIC_URL=https://metrics.example.com` in the `.env` file on the VM first: Grafana and Prometheus need it to generate correct links and redirects when served under a sub-path.

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
</VirtualHost>
```

SELinux is enforcing by default on Oracle Linux, which blocks Apache from opening outbound connections to the containers unless you allow it:

```bash
sudo setsebool -P httpd_can_network_connect 1
```

If `firewalld` is active, make sure HTTP/HTTPS are open:

```bash
sudo firewall-cmd --permanent --add-service=http --add-service=https
sudo firewall-cmd --reload
```

Save the VirtualHost config to `/etc/httpd/conf.d/metrics.conf` (Oracle Linux auto-includes everything in `conf.d/`), test, and restart:

```bash
sudo apachectl configtest
sudo systemctl restart httpd
```

After running certbot, it will automatically create an HTTPS VirtualHost on port 443. The final HTTPS configuration will look like:

```apache
<VirtualHost *:443>
    ServerName metrics.example.com

    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/metrics.example.com/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/metrics.example.com/privkey.pem

    ProxyPreserveHost On

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
</VirtualHost>
```

#### 4. Enable SSL Certificate (Let's Encrypt)

On Oracle Linux (RHEL-based):

```bash
# Install EPEL repository
sudo dnf install -y epel-release

# Install certbot and Apache plugin
sudo dnf install -y certbot python3-certbot-apache

# Obtain and install certificate
sudo certbot --apache -d metrics.example.com

# Certificate will be auto-renewed via systemd timer
sudo systemctl enable --now certbot-renew.timer
```

Certbot will automatically update your VirtualHost configuration to use HTTPS.

#### 5. Verify Configuration

Access your services:

- `https://metrics.example.com/grafana/` → Grafana dashboard
- `https://metrics.example.com/prometheus/` → Prometheus UI
- `https://metrics.example.com/bot-metrics` → Raw bot metrics
- `https://metrics.example.com/logs` → Bot logs (HTML view)

Check the upstreams directly on the VM before debugging the proxy. Use GET requests (`-I` sends HEAD, which Prometheus answers with 405):

```bash
curl -sS -o /dev/null -w '%{http_code} %{redirect_url}\n' http://127.0.0.1:3701/grafana/  # Grafana
curl -sS -o /dev/null -w '%{http_code} %{redirect_url}\n' http://127.0.0.1:9091/          # Prometheus
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:7001/metrics                   # Bot metrics
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:7002/logs                      # Bot logs
```

If a curl fails, the problem is the container, not Apache: `docker compose ps` and `docker compose logs <service>`.

## Project Structure

```
hamm-telegram-bot/
├── src/
│   ├── main.py           # Application entry point
│   ├── bot.py            # Bot controller with handlers
│   ├── repository.py     # Database operations
│   └── logger.py         # Logging configuration
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
