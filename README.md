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
git clone https://github.com/yourusername/hamm-telegram-bot.git
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
- Grafana: http://localhost:3701 (admin/admin)
- Prometheus: http://localhost:9091
- Bot metrics: http://localhost:7001/metrics

## Oracle VM Deployment

### Requirements

- Oracle Cloud VM with Ubuntu
- Docker and Docker Compose installed
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
│   Prometheus   │
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

| Service | Container Port | Host Port | Access |
|---------|---------------|-----------|--------|
| Bot Metrics | 8000 | 7001 | 127.0.0.1:7001 |
| Bot Logs | 8001 | 7002 | 127.0.0.1:7002 |
| Prometheus | 9090 | 9091 | 127.0.0.1:9091 |
| Grafana | 3000 | 3701 | 127.0.0.1:3701 |

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

```bash
BOT_TOKEN=your_telegram_bot_token
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=secure_password
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

1. Access Grafana at http://localhost:3701
2. Login with admin/admin (change password after first login)
3. Add Prometheus data source: http://prometheus:9090
4. Import or create dashboards to visualize metrics

### Subdomain Configuration

If using a single subdomain (e.g., `metrics.example.com`) with Apache httpd as reverse proxy:

#### 1. Create DNS Record

Add an A record in your domain's DNS settings:
- **Type:** A
- **Name:** metrics (or your desired subdomain)
- **Value:** Your Oracle VM public IP address
- **TTL:** 300 (or default)

#### 2. Enable Apache Proxy Modules

```bash
sudo a2enmod proxy
sudo a2enmod proxy_http
sudo systemctl restart httpd
```

#### 3. Configure Apache VirtualHost (HTTP)

```apache
<VirtualHost *:80>
    ServerName metrics.example.com

    ProxyPreserveHost On

    # Grafana
    ProxyPass /grafana/ http://127.0.0.1:3701/
    ProxyPassReverse /grafana/ http://127.0.0.1:3701/

    # Prometheus
    ProxyPass /prometheus/ http://127.0.0.1:9091/
    ProxyPassReverse /prometheus/ http://127.0.0.1:9091/

    # Bot metrics
    ProxyPass /bot-metrics http://127.0.0.1:7001/metrics
    ProxyPassReverse /bot-metrics http://127.0.0.1:7001/metrics

    # Bot logs
    ProxyPass /logs http://127.0.0.1:7002/
    ProxyPassReverse /logs http://127.0.0.1:7002/
</VirtualHost>
```

Save to `/etc/httpd/conf.d/metrics.conf` and restart:
```bash
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

    # Grafana
    ProxyPass /grafana/ http://127.0.0.1:3701/
    ProxyPassReverse /grafana/ http://127.0.0.1:3701/

    # Prometheus
    ProxyPass /prometheus/ http://127.0.0.1:9091/
    ProxyPassReverse /prometheus/ http://127.0.0.1:9091/

    # Bot metrics
    ProxyPass /bot-metrics http://127.0.0.1:7001/metrics
    ProxyPassReverse /bot-metrics http://127.0.0.1:7001/metrics

    # Bot logs
    ProxyPass /logs http://127.0.0.1:7002/
    ProxyPassReverse /logs http://127.0.0.1:7002/
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
- `https://metrics.example.com/grafana` → Grafana dashboard
- `https://metrics.example.com/prometheus` → Prometheus UI
- `https://metrics.example.com/bot-metrics` → Raw bot metrics
- `https://metrics.example.com/logs` → Bot logs (JSON format)

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
