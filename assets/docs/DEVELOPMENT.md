# Development Guide

Set up the bot for local development.

## Prerequisites

- Python 3.10 or higher
- Node.js (for Prisma)
- pip and npm
- Git

## Step 1: Clone and Setup

```bash
git clone <repo-url> && cd scheduler-discord-bot

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install Python dependencies
pip install -r config/requirements.txt

# Generate Prisma client
cd db
npx prisma generate
cd ..
```

## Step 2: Create Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **New Application** and give it a name
3. Go to **Bot** section → Click **Add Bot**
4. Under **TOKEN**, click **Copy** (this is your `DISCORD_TOKEN`)
5. Go to **OAuth2** → **URL Generator**
6. Select scopes: `bot`
7. Select permissions:
   - Read Messages/View Channels
   - Send Messages
   - Read Message History
   - Use Slash Commands
8. Copy the generated URL and invite your bot to a test server

## Step 3: Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and set:

```env
DISCORD_TOKEN=your_bot_token_here
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
python -m src
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
cd db
npx prisma studio
cd ..
```

This opens Prisma Studio at http://localhost:5555

To reset the database (⚠️ deletes all messages):

```bash
cd db
npx prisma migrate reset
cd ..
```

## Stopping the Bot

Press `Ctrl+C` in the terminal.

## Troubleshooting

### "Bot is not responding"
- Verify `DISCORD_TOKEN` is correct in `.env`
- Check privileged intents are enabled in Discord Portal
- Restart the bot
- Check bot has permissions in your Discord server

### "Commands not showing"
- Wait 1 minute for Discord to sync
- Restart the bot
- Check logs for errors

### "Database is locked"
- Restart the bot
- If persists: `rm -rf db/database.db` and restart

### "ModuleNotFoundError"
- Activate virtual environment: `source venv/bin/activate`
- Reinstall dependencies: `pip install -r config/requirements.txt`

## Code Organization

```
src/
├── __main__.py          Entry point & Discord events
├── commands/
│   └── scheduler.py     Slash command implementations
├── delivery.py          Message delivery service
├── db.py                Database operations
└── utils.py             Validation & parsing utilities

db/
└── schema.prisma        Database schema

config/
└── requirements.txt     Python dependencies
```

## Making Changes

After making code changes:

1. Stop the bot (`Ctrl+C`)
2. Make your changes
3. Restart the bot (`python -m src`)

If you modify the database schema:

```bash
cd db
npx prisma migrate dev --name describe_your_change
cd ..
python -m src
```

## Next Steps

When ready to deploy, see [DEPLOYMENT.md](DEPLOYMENT.md)
