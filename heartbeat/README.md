# NEXUS Heartbeat Monitoring

Automated health monitoring and recovery system for NEXUS AI Team.

## Features

- **Health Checks**: Monitors Gateway, Redis, PostgreSQL, Agents, GPU/Ollama, Token Budget, and Disk usage
- **Alerting**: Sends notifications via Telegram and logs
- **Auto-Recovery**: Attempts automatic recovery for common failures
- **Flexible Deployment**: Run as systemd service, cron job, or standalone script

## Components

### 1. Monitor (`monitor.py`)
Periodically checks:
- Gateway HTTP/WebSocket responsiveness
- Redis connectivity and memory usage
- PostgreSQL connectivity and work order count
- Agent activity (detects stuck work orders)
- GPU/Ollama availability
- Token budget usage
- Disk space

### 2. Alerts (`alerts.py`)
Sends notifications via:
- **Telegram**: For critical and warning alerts (with rate limiting)
- **Logging**: All issues logged with appropriate severity
- **Future**: WebSocket push to connected clients

### 3. Recovery (`recovery.py`)
Automatic recovery actions:
- **Gateway down**: Restart service (if enabled)
- **Disk full**: Cleanup old logs, reports, and `__pycache__`
- **Agents stuck**: Notify for manual intervention
- **Budget exceeded**: Alert and recommend action

### 4. Service (`service.py`)
Standalone runner with two modes:
- **Continuous**: Long-running service (for systemd)
- **Once**: Single check and exit (for cron)

## Installation

### Option 1: Systemd Service (Recommended)

1. **Install dependencies**:
   ```bash
   pip install aiohttp psutil redis psycopg
   ```

2. **Configure environment** (`.env`):
   ```bash
   DATABASE_URL=postgresql://nexus:password@localhost:5432/nexus
   TELEGRAM_BOT_TOKEN=your-bot-token
   TELEGRAM_CHAT_ID=your-chat-id
   ```

3. **Install systemd service**:
   ```bash
   sudo cp heartbeat/nexus-heartbeat.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable nexus-heartbeat
   sudo systemctl start nexus-heartbeat
   ```

4. **Check status**:
   ```bash
   sudo systemctl status nexus-heartbeat
   journalctl -u nexus-heartbeat -f
   ```

### Option 2: Cron Job

1. **Install dependencies** (same as above)

2. **Setup cron**:
   ```bash
   crontab -e
   ```

   Add (adjust paths):
   ```cron
   */5 * * * * cd /home/leonard/Desktop/nexus-ai-team && .venv/bin/python -m heartbeat.service --once --enable-telegram --enable-recovery >> logs/heartbeat-cron.log 2>&1
   ```

### Option 3: Manual/Development

Run once:
```bash
python -m heartbeat.service --once --enable-telegram --enable-recovery
```

Run continuously:
```bash
python -m heartbeat.service --enable-telegram --enable-recovery
```

## Configuration

Command-line options:
- `--once`: Run single check and exit
- `--check-interval`: Seconds between checks (default: 30)
- `--gateway-url`: Gateway URL (default: http://localhost:8000)
- `--redis-url`: Redis URL (default: redis://localhost:6379/0)
- `--postgres-url`: PostgreSQL URL (from DATABASE_URL env)
- `--telegram-token`: Telegram bot token (from TELEGRAM_BOT_TOKEN env)
- `--telegram-chat-id`: Telegram chat ID (from TELEGRAM_CHAT_ID env)
- `--enable-telegram`: Enable Telegram notifications
- `--enable-recovery`: Enable auto-recovery (default: true)
- `--enable-restart`: Enable service restart (requires systemd permissions)
- `--log-level`: Logging level (default: INFO)

## Telegram Setup

1. **Create bot**: Talk to [@BotFather](https://t.me/botfather)
   - `/newbot`
   - Get your `TELEGRAM_BOT_TOKEN`

2. **Get chat ID**:
   - Send a message to your bot
   - Visit: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   - Find your `chat_id` in the response

3. **Add to `.env`**:
   ```bash
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   TELEGRAM_CHAT_ID=987654321
   ```

## Health Status Levels

- **healthy**: All systems operational
- **degraded**: Minor issues, system still functional
- **critical**: Major failure, immediate attention required
- **unknown**: Unable to check (e.g., optional component not configured)

## Auto-Recovery Actions

| Issue | Action | Severity |
|-------|--------|----------|
| Gateway down | Restart service (if enabled) | Critical |
| Redis down | Notify for manual check | Critical |
| PostgreSQL down | Notify for manual check | Critical |
| Agents stuck | Notify, suggest manual intervention | Warning |
| Disk full (>95%) | Cleanup logs/reports/__pycache__ | Critical |
| Disk high (>85%) | Cleanup logs/reports/__pycache__ | Warning |
| Budget exceeded | Alert, recommend pause | Critical |

## Monitoring

**Systemd**:
```bash
sudo systemctl status nexus-heartbeat
journalctl -u nexus-heartbeat -f
journalctl -u nexus-heartbeat --since "1 hour ago"
```

**Cron**:
```bash
tail -f logs/heartbeat-cron.log
```

**Manual**:
```bash
python -m heartbeat.service --once
```

## Integration with Gateway

The Gateway exposes detailed health information via:
- `GET /api/health/detailed` - Full system health report
- WebSocket notifications for health changes (future)

## Troubleshooting

**Heartbeat not running**:
```bash
sudo systemctl status nexus-heartbeat
journalctl -u nexus-heartbeat -n 50
```

**Telegram not working**:
- Check bot token and chat ID
- Verify bot is not blocked
- Test: `curl -X POST "https://api.telegram.org/bot<TOKEN>/sendMessage" -d "chat_id=<CHAT_ID>&text=test"`

**Recovery not working**:
- Check `--enable-recovery` flag
- Verify permissions for file cleanup
- For service restart, ensure proper systemd permissions

**High disk usage persists**:
- Manual cleanup: `du -sh logs/ reports/ && find . -name '__pycache__' -type d`
- Check Docker volumes: `docker system df`
- Expand storage or archive old data

## Future Enhancements

- [ ] WebSocket push for real-time health updates
- [ ] Agent process monitoring and restart
- [ ] Historical health trends and charts
- [ ] Configurable recovery strategies
- [ ] Email notifications
- [ ] Slack/Discord integrations
- [ ] Custom health check plugins
