# 📅 Scheduler Discord Bot

A minimal Discord bot that schedules messages to users/channels at specific times. Features member autocomplete, delivery confirmations, and reliable message queuing.

## Features

✨ **Scheduling** - Schedule messages to users/channels at specific times  
 **Autocomplete** - Members show in dropdown as you type  
✅ **Confirmations** - Get notified when messages deliver  
🗂️ **Management** - List, update, and delete pending messages  
⚡ **Reliable** - SQLite + Prisma ORM, automatic error handling  

## Quick Start (Local)

```bash
# Setup
git clone <repo> && cd scheduler-discord-bot
python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r config/requirements.txt

# Configure
cd db && npx prisma generate && cd ..
cp .env.example .env
# Edit .env: DISCORD_TOKEN=your_token_here

# Run
python -m src
```

## Commands

```
/help                                    Show help
/sch "message" <destinations> HH:MM ...  Schedule a message
/ls                                      List pending messages
/del <id>                                Delete a message
/mv <field> <id> <value>                 Update a message
```

**Examples:**
```
/sch "Hello!" <@user> 15:30
/sch "Report" <#channel> 25/12 18:00
/mv time 0 20:00
/del 0
```

## Deploy to Raspberry Pi

### Prerequisites
- Raspberry Pi with Docker & Docker Compose
- Discord bot token (from https://discord.com/developers/applications)
- GitHub Personal Access Token (for container registry)

### Setup

1. **Enable Privileged Intents** (required!)
   - Go to https://discord.com/developers/applications
   - Select your bot → Bot → Privileged Gateway Intents
   - Toggle ON: Server Members Intent + Message Content Intent
   - Save

2. **Push Code**
   ```bash
   git add -A && git commit -m "Deploy scheduler bot"
   git push origin main
   # GitHub Actions automatically builds Docker image
   ```

3. **On Raspberry Pi**
   ```bash
   cd /path/to/raspi/docker-compose
   
   # Login to container registry
   echo $GITHUB_TOKEN | docker login ghcr.io -u YOUR_USERNAME --password-stdin
   
   # Configure
   nano .env
   # Add: GITHUB_USERNAME=your_username
   #      DISCORD_TOKEN=your_bot_token
   
   # Deploy
   docker-compose up -d scheduler-bot
   docker logs -f scheduler_bot
   ```

4. **Test** - Type `/` in Discord, should see `/help` ✅

## Project Structure

```
src/
├── __main__.py           Bot entry point & tree sync
├── commands/scheduler.py  5 slash commands + autocomplete
├── delivery.py           Scheduled delivery service
├── db.py                 Database manager
└── utils.py              Utilities & validation

config/requirements.txt    Python dependencies
db/schema.prisma          Database schema
Dockerfile                Container image (multi-stage)
.github/workflows/        Automated CI/CD (builds Docker image)
```

## Architecture

**Local**: Discord Bot → Discord API ← Message Queue (SQLite)  
**Docker**: GitHub Actions builds image → Push to ghcr.io → Pull on Pi → Run in Docker Compose  

## Documentation

- **[DEPLOYMENT.md](assets/docs/DEPLOYMENT.md)** - Detailed deployment & troubleshooting
- **[DEVELOPMENT.md](assets/docs/DEVELOPMENT.md)** - Local development & testing

## Support

**Bot not connecting?** Enable privileged intents in Discord Portal  
**Autocomplete empty?** Must enable Server Members Intent  
**Docker issues?** Check logs: `docker logs scheduler_bot`  
**Need help?** See [DEPLOYMENT.md](assets/docs/DEPLOYMENT.md)

---

**Status**: ✅ Production Ready | **Version**: 1.0.0 | **License**: MIT
