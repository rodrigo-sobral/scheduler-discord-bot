# Development Guide

Local development setup and testing.

## Setup

```bash
git clone <repo-url> && cd scheduler-discord-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r config/requirements.txt

# Generate Prisma client
cd db && npx prisma generate && cd ..

# Configure bot token
cp .env.example .env
# Edit .env: DISCORD_TOKEN=your_token_here
```

## Running Locally

```bash
python -m src

# Bot will:
# 1. Connect to Discord
# 2. Sync slash commands
# 3. Start listening for scheduled messages
```

## Project Structure

```
src/
├── __main__.py          Bot entry point & events
├── commands/
│   └── scheduler.py     5 slash commands + autocomplete
├── delivery.py          Message delivery service
├── db.py                Database operations
├── utils.py             Validation & utilities
└── config.py            Configuration

db/
└── schema.prisma        Database schema

config/
└── requirements.txt     Dependencies
```

## Database Operations

```bash
# View database
cd db && npx prisma studio && cd ..

# Reset database (clears all data!)
cd db && npx prisma migrate reset && cd ..
```

## Adding Features

### Adding a New Command

Edit `src/commands/scheduler.py`:

```python
@app_commands.command(name='mycommand', description='My command')
@app_commands.describe(param="Description")
async def my_command(self, interaction: discord.Interaction, param: str) -> None:
    await interaction.response.defer()
    # Your code here
    await interaction.followup.send("Response")
```

### Adding Database Fields

1. Edit `db/schema.prisma`
2. Run migration: `cd db && npx prisma migrate dev --name description && cd ..`
3. Update code to use new fields

## Testing

### Manual Testing
```bash
# While bot is running in Discord:
1. Type /help to see commands
2. Try scheduling messages
3. Check database: cd db && npx prisma studio
```

### Syntax Check
```bash
python -c "import ast; ast.parse(open('src/__main__.py').read()); print('✅ OK')"
```

## Debugging

```bash
# Run with debug logging
LOG_LEVEL=DEBUG python -m src

# Check logs
tail -f logs/scheduler_bot.log

# View bot presence
# (In Discord: bot activity shows "watching..." status)
```

## Common Issues

**Bot not starting?**
- Check DISCORD_TOKEN is valid
- Check privileged intents enabled in Discord Portal
- Verify database initialized: `ls -la db/db/`

**Database locked?**
- Restart bot: `Ctrl+C` and rerun

**Commands not showing?**
- Wait 1 minute for tree sync
- Or restart bot: `Ctrl+C` and rerun

## Environment Variables

```
DISCORD_TOKEN=your_token_here
LOG_LEVEL=INFO (or DEBUG)
TZ=Europe/London
DATABASE_URL=file:./db/database.db (optional)
```

## Before Committing

```bash
# Check syntax
python -c "import ast; ast.parse(open('src/__main__.py').read())"
python -c "import ast; ast.parse(open('src/commands/scheduler.py').read())"

# Keep code clean
black src/  (if installed)

# Test locally
python -m src
```

---

**For deployment**, see [DEPLOYMENT.md](docs/DEPLOYMENT.md)

tests/                    # Unit and integration tests (to be added)
assets/docs/              # Documentation
```

## Development Setup on macOS

### Prerequisites
- Python 3.10+
- Node.js (for Prisma)
- Git

### Environment Setup with Homebrew
```bash
brew install python@3.11
brew install node
```

### Verify Python
```bash
python3 --version  # Should be 3.10+
which python3
```

## Database Setup

### Using Prisma

First-time setup:
```bash
cd db
npx prisma generate
cd ../..
```

After schema changes:
```bash
cd db
npx prisma migrate dev --name <migration_name>
cd ../..
```

Reset database (⚠️ deletes all messages):
```bash
cd db
npx prisma migrate reset
cd ../..
```

### Explore Database
```bash
cd db
npx prisma studio
cd ../..
```

Opens Prisma Studio at http://localhost:5555

## Code Structure

### Database Manager (`src/db.py`)
Handles all database operations:
```python
db_manager = DatabaseManager()
await db_manager.connect()

# Create
msg = await db_manager.create_message(user_id, content, destinations, day, month, year, hour, minute)

# Read
messages = await db_manager.get_user_messages(user_id)

# Update
updated = await db_manager.update_message(message_id, user_id, message_content="new")

# Delete
await db_manager.delete_message(message_id, user_id)

await db_manager.disconnect()
```

### Utilities (`src/utils.py`)
Validation and parsing:
```python
from utils import (
    parse_time_input,          # "HH:MM" -> (hour, minute)
    parse_date_input,          # "DD/MM/YYYY" -> (day, month, year)
    parse_destinations,        # "<@123> <#456>" -> ["123", "456"]
    validate_message_content,  # Check message is valid
    format_delivery_time,      # Format for display
)
```

### Commands (`src/commands/scheduler.py`)
Command handlers using discord.py Cogs:
```python
class SchedulerCommands(commands.Cog):
    @commands.command(name='help')
    async def help_command(self, ctx):
        # Handle /help
        
    @commands.command(name='sch')
    async def schedule_message(self, ctx, *, args):
        # Handle /sch
```

## Testing

### Manual Testing
1. Invite bot to test server
2. Run bot: `python -m src`
3. Use commands in Discord

### Command Testing Checklist

#### `/help`
```
/help
```
Should show formatted help embed with all commands.

#### `/sch` Scheduling
```
/sch "Test message" <@yourID> 15:30
/sch "Tomorrow" <@yourID> 25/12 14:00
/sch "Future" <@yourID> 01/01/2025 09:00
```

#### `/ls sch` Listing
```
/ls sch
```
Should show queue sorted by delivery time.

#### `/del sch` Deletion
```
/del sch 0
```
Should delete message at position 0.

#### `/mv sch` Updates
```
/mv sch content 0 "Updated message"
/mv sch time 0 18:00
/mv sch day 0 31/12
/mv sch destinations 0 <@user1> <#channel1>
```

## Debugging

### Enable Debug Logging
Set in `.env`:
```
LOG_LEVEL=DEBUG
```

### View Logs
```bash
tail -f logs/scheduler_bot.log
```

### Database Debug
```bash
cd db
npx prisma studio
```

### Common Issues

**Bot doesn't respond**
1. Check bot has "Send Messages" permission
2. Verify BOT_TOKEN in .env
3. Check logs for errors

**Database errors**
```bash
# Reset everything
rm db/database.db
cd db
npx prisma migrate reset
cd ../..
```

**Module not found errors**
```bash
source venv/bin/activate
pip install -r config/requirements.txt
```

## Adding Features

### Adding a New Command

1. Create command method in `src/commands/scheduler.py`:
```python
@commands.command(name='example')
async def example_command(self, ctx: commands.Context, *, args: str = None):
    try:
        # Validate inputs
        if not args:
            raise ValidationError("Usage: /example <arg>")
        
        # Process
        result = await self.db.some_operation(...)
        
        # Respond
        embed = discord.Embed(title="Success", color=discord.Color.green())
        await ctx.send(embed=embed)
        
    except ValidationError as e:
        embed = discord.Embed(title="Error", description=str(e), color=discord.Color.red())
        await ctx.send(embed=embed)
```

2. Update `/help` command if needed

3. Test with bot

### Adding Validation

Add to `src/utils.py`:
```python
def validate_something(value: str) -> None:
    if not value:
        raise ValidationError("Value required")
    if len(value) > 100:
        raise ValidationError("Value too long")
```

### Database Schema Changes

1. Edit `db/schema.prisma`
2. Create migration:
```bash
cd db
npx prisma migrate dev --name describe_change
cd ../..
```
3. Test with bot

## Performance Considerations

- Message queue is sorted by delivery time in database query
- Each user has their own queue (isolated by user_id)
- Database queries use indexes for fast lookups
- Message delivery loop runs every minute (configurable)

## Security Best Practices

✅ **Implemented:**
- User isolation (users can only access their own messages)
- Input validation for all user inputs
- No hardcoded secrets (uses environment variables)
- Bot requests minimum permissions

⚠️ **To Implement:**
- Rate limiting for message scheduling
- Message content filtering
- Audit logging for message delivery
- Better error messages for security (don't expose DB errors)

## Deployment

### Pre-deployment Checklist
- [ ] All tests pass
- [ ] No debug logging in production
- [ ] BOT_TOKEN set securely
- [ ] Database backed up
- [ ] ENVIRONMENT=production in `.env`

### Running in Production
```bash
ENVIRONMENT=production LOG_LEVEL=WARNING python -m src
```

## Contributing

1. Create a feature branch: `git checkout -b feature/xyz`
2. Make changes following code style
3. Test thoroughly
4. Commit with clear messages
5. Push and create PR

## Resources

- [discord.py Documentation](https://discordpy.readthedocs.io/)
- [Prisma Python Docs](https://prisma-client-py.readthedocs.io/)
- [Discord Developer Portal](https://discord.com/developers/)
