# Deployment Guide

Deploy the Scheduler Bot to your Raspberry Pi using Docker Compose.

## Prerequisites

- ✅ Raspberry Pi with Docker & Docker Compose installed
- ✅ Discord bot token (from https://discord.com/developers/applications)
- ✅ GitHub Personal Access Token with `read:packages` scope
- ✅ Raspberry Pi is in the `docker-compose.yaml` (scheduler-bot service already added)

## Step 1: Enable Privileged Intents (REQUIRED!)

Without this, the bot won't connect and autocomplete won't work.

1. Go to https://discord.com/developers/applications
2. Select your **Scheduler Bot**
3. Go to **Bot** section → **Privileged Gateway Intents**
4. Toggle **ON**:
   - ✅ Server Members Intent
   - ✅ Message Content Intent
5. Click **Save Changes**

## Step 2: Prepare Code for GitHub

```bash
cd scheduler-discord-bot
git add -A
git commit -m "Deploy scheduler bot to Raspberry Pi"
git push origin main

# GitHub Actions automatically builds Docker image (3-5 minutes)
# Monitor: https://github.com/YOUR_USERNAME/scheduler-discord-bot/actions
```

## Step 3: Configure Raspberry Pi

SSH into your Raspberry Pi:

```bash
ssh pi@your-pi-ip
cd /path/to/docker-compose

# 1. Login to GitHub Container Registry
export GITHUB_TOKEN=ghp_your_token_here
echo $GITHUB_TOKEN | docker login ghcr.io -u YOUR_USERNAME --password-stdin

# 2. Edit .env file
nano .env

# Add these lines:
# GITHUB_USERNAME=your_username
# DISCORD_TOKEN=your_bot_token
# (Keep existing variables: TZ, etc.)

# 3. Deploy
docker-compose pull scheduler-bot
docker-compose up -d scheduler-bot

# 4. Verify
docker logs -f scheduler_bot

# Expected output:
# "✅ Synced 5 slash command(s) with Discord"
```

## Step 4: Test in Discord

1. Open your Discord server
2. Type `/` to see slash commands
3. You should see `/help` command
4. Try `/sch` - members should appear as you type in destinations
5. Schedule a message - you should get a confirmation DM

## Monitoring & Maintenance

### Check Status
```bash
# See logs
docker logs -f scheduler_bot

# See if healthy
docker inspect scheduler_bot --format='{{.State.Health.Status}}'

# See resource usage
docker stats scheduler_bot
```

### Update Bot

When you push changes to GitHub (and GitHub Actions builds a new image):

```bash
docker-compose pull scheduler-bot
docker-compose up -d scheduler-bot
docker logs -f scheduler_bot
```

### Backup Database

```bash
docker cp scheduler_bot:/app/db ./scheduler_db_backup_$(date +%Y%m%d)
```

## Troubleshooting

### Bot Won't Connect
- Check Discord token is correct: `docker exec scheduler_bot env | grep DISCORD_TOKEN`
- Verify privileged intents are enabled in Discord Portal
- Check logs: `docker logs scheduler_bot | head -50`

### Image Won't Pull
- Verify GitHub login: `docker login ghcr.io`
- Check token has `read:packages` scope
- Try manually: `docker pull ghcr.io/YOUR_USERNAME/scheduler-discord-bot:latest`

### Autocomplete Empty
- **MUST enable privileged intents** (see Step 1)
- Restart bot: `docker-compose restart scheduler_bot`
- Wait 30 seconds for bot to reconnect

### High Memory Usage
- Reduce limit in docker-compose.yaml: `memory: 256M`
- Restart: `docker-compose restart scheduler_bot`

### Database Locked
- Restart bot: `docker-compose restart scheduler_bot`
- If persists, remove and recreate: `docker volume rm scheduler_data`

## Environment Variables

| Variable | Required | Example |
|----------|----------|---------|
| DISCORD_TOKEN | ✅ Yes | `MTC5NzA4...` |
| GITHUB_USERNAME | ✅ Yes | `rodrigo` |
| TZ | ✅ Yes | `Europe/London` |

## Architecture

```
Your Code (GitHub)
    ↓ (git push)
GitHub Actions
    ├─ Builds Docker image (ARM64 + AMD64)
    └─ Pushes to ghcr.io
        ↓ (docker pull)
Raspberry Pi Docker
    ├─ scheduler-bot container
    ├─ Volume: scheduler_data (database)
    ├─ Volume: scheduler_logs (logs)
    └─ Network: web (connects to other services)
        ↓ (DISCORD_TOKEN)
    Discord API
```

## Understanding the Setup

- **Dockerfile** - Multi-stage Python build, optimized for ARM64
- **.github/workflows/docker-build-push.yml** - Automatic CI/CD pipeline
- **docker-compose.yaml (raspi)** - Has scheduler-bot service already integrated
- **Volumes** - `scheduler_data` (database), `scheduler_logs` (logs)
- **Network** - `web` (shared with other services on your Pi)

## Security Notes

- ✅ Bot runs as non-root user (container security)
- ✅ Environment variables stored in .env (not committed to git)
- ✅ No privileged mode enabled
- ✅ Network isolation via Docker networks
- ⚠️ Keep DISCORD_TOKEN and GITHUB_TOKEN secret!

## Performance

- **CPU**: ~10% idle, scales with message volume
- **Memory**: 256-512MB (configurable)
- **Disk**: ~10MB per 1000 scheduled messages
- **Startup**: 10-20 seconds

Good for Raspberry Pi 3B+ and newer models.

## Getting Help

1. Check logs: `docker logs scheduler_bot`
2. See Troubleshooting section above
3. Verify privileged intents enabled in Discord Portal
4. Check GitHub Actions workflow completed
5. Verify environment variables in .env: `docker exec scheduler_bot env | grep DISCORD`

On your Raspberry Pi, authenticate with GitHub Container Registry:

```bash
# Create/use a GitHub Personal Access Token with 'read:packages' scope
# https://github.com/settings/tokens

export CR_PAT=YOUR_GITHUB_TOKEN
echo $CR_PAT | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin
```

## Step 3: Update Environment Variables

Add to your `.env` file on the Raspberry Pi:

```env
# Existing variables
TZ=Europe/London

# Scheduler Bot
DISCORD_TOKEN=your_discord_bot_token_here
```

## Step 4: Deploy to Docker Compose

### Option A: Separate Compose File (Recommended)

Add to your main `docker-compose.yaml`:

```yaml
services:
  scheduler-bot:
    image: ghcr.io/YOUR_GITHUB_USERNAME/scheduler-discord-bot:latest
    container_name: scheduler_bot
    restart: unless-stopped
    environment:
      TZ: ${TZ}
      DISCORD_TOKEN: ${DISCORD_TOKEN}
    volumes:
      - scheduler_data:/app/db
      - scheduler_logs:/app/logs
    networks:
      - web
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    healthcheck:
      test: ["CMD", "python", "-c", "print('healthy')"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: "1.00"
          memory: 512M

volumes:
  scheduler_data:
  scheduler_logs:
```

### Option B: Use Separate Compose File

```bash
# Deploy with both compose files
docker-compose -f docker-compose.yaml -f docker-compose.scheduler.yaml up -d

# Or with profile (if enabled)
docker-compose -f docker-compose.yaml -f docker-compose.scheduler.yaml --profile scheduler up -d
```

## Step 5: Verify Deployment

```bash
# Check container status
docker ps | grep scheduler_bot

# View logs
docker logs -f scheduler_bot

# Check health
docker inspect scheduler_bot --format='{{.State.Health.Status}}'
```

## Step 6: Update the Image

When new versions are released:

```bash
# Pull latest image
docker pull ghcr.io/YOUR_GITHUB_USERNAME/scheduler-discord-bot:latest

# Recreate container
docker-compose up -d scheduler-bot

# Verify
docker logs -f scheduler_bot
```

## Automatic Updates (Optional)

Use Watchtower to auto-update containers:

```yaml
services:
  watchtower:
    image: containrrr/watchtower:latest
    container_name: watchtower
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    command: --interval 3600 scheduler_bot
    networks:
      - web
```

## Troubleshooting

### Bot not connecting
- Check `DISCORD_TOKEN` is valid and set in `.env`
- Check docker logs: `docker logs scheduler_bot`
- Verify bot token has not expired

### "Privileged intents not enabled" error
- See Step 1 above - must enable in Discord Developer Portal
- Restart container after enabling: `docker-compose restart scheduler_bot`

### Database connection issues
- Check database path is accessible: `docker exec scheduler_bot ls -la /app/db`
- Verify volume permissions: `docker inspect scheduler_data`
- Check disk space: `df -h`

### High memory usage on Raspberry Pi
- Adjust memory limit in docker-compose: `memory: 256M`
- Reduce log retention: `max-file: "2"`
- Check active scheduled messages: `/ls` command

## Architecture Notes

The Docker setup follows your infrastructure patterns:
- **Base Image**: `python:3.12-alpine`
- **Multi-stage Build**: Reduces final image size for RPi
- **Non-root User**: Security best practice
- **Resource Limits**: Prevents Pi resource exhaustion
- **Health Checks**: Enables container orchestration
- **Logging**: Centralized JSON logging with rotation
- **Volumes**: Persistent storage for database and logs

## Network Considerations

The bot connects to:
- **Discord API** (outbound HTTPS to discord.com)
- **Local Network** (if scheduling messages for internal users)
- **Docker Network** (web network for inter-service communication)

No inbound ports needed - purely outbound bot.

## Database

By default, SQLite database is stored in:
- Container: `/app/db/database.db`
- Volume: `scheduler_data`

Ensure adequate disk space on your Raspberry Pi.

## Next Steps

1. Commit these files to your repo
2. Let GitHub Actions build the image (automatically)
3. Update the Raspberry Pi compose file with the new service
4. Deploy and verify
5. Test `/help` command in Discord

## Support

For issues, check:
- Bot logs: `docker logs scheduler_bot`
- Discord permissions: `/help` command should appear
- Environment variables: `docker exec scheduler_bot env | grep DISCORD`
