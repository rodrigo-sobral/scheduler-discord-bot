# Development Guide

Set up the bot for local development using `uv`.

## Prerequisites

- Python 3.12 or higher
- Node.js (for Prisma)
- Git

## Step 1: Clone and Setup

```bash
git clone <repo-url> && cd scheduler-discord-bot

# Run setup script (installs uv if needed, creates .venv, syncs dependencies)
bash scripts/setup.sh
```

The setup script will:
- Install `uv` if not already installed
- Create a Python virtual environment (`.venv`)
- Install all project dependencies
- Set up Prisma client
- Create `.env` file from `.env.example`

## Step 2: Create Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **New Application** and give it a name
3. Go to **Bot** section → Click **Add Bot**
4. Under **TOKEN**, click **Copy** (this is your `BOT_TOKEN`)
5. Go to **OAuth2** → **URL Generator**
6. Select scopes: `bot`
7. Select permissions:
   - Read Messages/View Channels
   - Send Messages
   - Read Message History
   - Use Slash Commands
8. Copy the generated URL and invite your bot to a test server

## Step 3: Configure Environment Variables

Edit `.env`:

```env
BOT_TOKEN=your_bot_token_here
TZ=Europe/London
```

**Get your token from:**
- Discord Developer Portal → Your Application → Bot → Copy Token

## Step 4: Enable Required Intents

In Discord Developer Portal:

1. Go to your Application → **Bot**
2. Scroll to **Privileged Gateway Intents**
3. Enable:
   - ✅ Server Members Intent
   - ✅ Message Content Intent
4. Click **Save Changes**

**These intents are required for the bot to work properly.**

## Step 5: Run the Bot

```bash
uv run python -m src
```

You should see:
```
✅ Synced 5 slash command(s) with Discord
```

Test in Discord by typing `/` to see available commands.

## Testing Commands

With the bot running, test each command:

```
/help                          # Show help
/sch "Test" @user 15:30        # Schedule message
/ls                            # List messages
/del 0                         # Delete message at position 0
/mv time 0 20:00               # Update time
```

## Database

To view or manage the database:

```bash
uv run prisma studio
```

Opens Prisma Studio at http://localhost:5555

To reset the database (⚠️ deletes all messages):

```bash
uv run prisma migrate reset
```

## Stopping the Bot

Press `Ctrl+C` in the terminal.

## Troubleshooting

### "uv: command not found"
Install uv:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### ".venv not found"
Run setup again:
```bash
bash scripts/setup.sh
```

### "Bot is not responding"
- Verify `BOT_TOKEN` is correct in `.env`
- Check privileged intents are enabled in Discord Portal
- Restart the bot
- Check bot has permissions in your Discord server

### "Commands not showing"
- Wait 1 minute for Discord to sync
- Restart the bot
- Check logs for errors

### "Database is locked"
- Restart the bot
- If persists: `uv run prisma migrate reset`

### Import errors after adding dependencies
```bash
uv sync
```

## Project Structure

```
.
├── pyproject.toml              Project metadata and dependencies
├── uv.lock                     Locked dependency versions
├── src/
│   ├── __main__.py             Entry point & Discord events
│   ├── commands/
│   │   └── scheduler.py        Slash command implementations
│   ├── delivery.py             Message delivery service
│   ├── db.py                   Database operations
│   └── utils.py                Validation & parsing utilities
├── prisma/
│   └── schema.prisma           Database schema
├── scripts/
│   ├── setup.sh                One-time setup
│   ├── run.sh                  Run with auto-restart
│   └── check.sh                Format and lint
└── Dockerfile                  Container build
```

## Making Changes

After making code changes:

1. Stop the bot (`Ctrl+C`)
2. Make your changes
3. Run linting: `bash scripts/check.sh`
4. Restart the bot: `uv run python -m src`

If you modify the database schema:

```bash
uv run prisma migrate dev --name describe_your_change
uv run python -m src
```

## Next Steps

When ready to deploy, see [DEPLOYMENT.md](DEPLOYMENT.md)
