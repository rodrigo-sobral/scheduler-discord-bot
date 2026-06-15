"""
Scheduler Discord Bot
Main entry point for the bot
"""

import os
import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

from .config import BotConfig
from .db import DatabaseManager
from .commands.scheduler import SchedulerCommands
from .delivery import MessageDeliveryService
from .utils import is_delivery_time

# Load environment variables
load_dotenv()


# Configure logging
def setup_logging():
    """Configure logging with both file and console handlers"""
    logger = logging.getLogger()
    logger.setLevel(BotConfig.LOG_LEVEL)

    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)

    # File handler
    file_handler = logging.FileHandler(BotConfig.LOG_FILE)
    file_handler.setLevel(BotConfig.LOG_LEVEL)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(BotConfig.LOG_LEVEL)

    # Formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Reduce logging noise from libraries
    for noisy in [
        "prisma",
        "httpcore",
        "httpx",
        "discord.http",
        "discord.gateway",
        "asyncio",
    ]:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return logger


logger = setup_logging()

# Bot setup with intents
intents = discord.Intents.default()
intents.message_content = True  # Required to read message content
intents.guilds = True  # Required for guild info and member access
intents.members = True  # Required for autocomplete to see guild members
intents.dm_messages = True

bot = commands.Bot(
    command_prefix=BotConfig.COMMAND_PREFIX,
    description="📅 Scheduler Bot - Schedule messages to be sent at a later time",
    intents=intents,
    help_command=None,  # We have custom help command
)

# Global database manager
db_manager: DatabaseManager = None

# Global delivery service
delivery_service: MessageDeliveryService = None


@bot.event
async def on_ready():
    """Called when the bot is ready"""
    logger.info(f"{bot.user} has connected to Discord!")
    logger.info(f"Bot ID: {bot.user.id}")
    logger.info(f"Logged in as: {bot.user}")

    # Sync command tree with Discord
    # This registers all @app_commands with Discord's API
    try:
        synced = await bot.tree.sync()
        logger.info(f"✅ Synced {len(synced)} slash command(s) with Discord")
    except Exception as e:
        logger.error(f"❌ Failed to sync commands with Discord: {e}", exc_info=e)

    # Set bot activity
    activity = discord.Activity(type=discord.ActivityType.watching, name="📬 Message Scheduler")
    await bot.change_presence(activity=activity)

    # Start the message delivery task
    if not message_delivery_loop.is_running():
        message_delivery_loop.start()
        logger.info("Message delivery loop started")


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    """Handle command errors"""
    if isinstance(error, commands.CommandNotFound):
        embed = discord.Embed(
            title="❌ Command Not Found",
            description=f"Unknown command: {ctx.invoked_with}\nUse `/help` for available commands",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)
    elif isinstance(error, commands.MissingRequiredArgument):
        embed = discord.Embed(
            title="❌ Missing Arguments",
            description="This command requires additional arguments.\nUse `/help` for usage information",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)
    else:
        logger.error(f"Command error in {ctx.command}: {error}", exc_info=error)
        embed = discord.Embed(
            title="❌ Error", description=f"An error occurred: {str(error)}", color=discord.Color.red()
        )
        await ctx.send(embed=embed)


@tasks.loop(minutes=BotConfig.MESSAGE_CHECK_INTERVAL_MINUTES)
async def message_delivery_loop():
    """
    Background task that runs every minute to check and deliver scheduled messages
    Runs frequently (every minute) to allow for minute-level precision
    """
    try:
        if db_manager is None or delivery_service is None:
            return

        now = datetime.now()

        logger.debug(f"Checking for messages to deliver at {now.strftime('%Y-%m-%d %H:%M')}")

        # Get all pending messages
        pending_messages = await db_manager.get_pending_messages()

        if not pending_messages:
            logger.debug("No pending messages to check")
            return

        # Check each message to see if it's time to deliver
        for message in pending_messages:
            # Get user timezone from database
            user_tz = (await db_manager.get_user_timezone(message["user_id"])).get("timezone", "UTC")
            tzinfo = ZoneInfo(user_tz)

            # Check if delivery time has arrived
            if is_delivery_time(message, tzinfo=tzinfo):
                logger.info(f"Delivering message {message['id']} to {len(message['destinations'])} destination(s)")

                # Attempt delivery
                success, failure_reason = await delivery_service.deliver_message(message)

                # Update message status in database
                await db_manager.mark_delivered(message["id"], success, failure_reason)

                if success:
                    logger.info(f"✅ Message {message['id']} delivered successfully")
                else:
                    logger.warning(f"❌ Message {message['id']} delivery failed: {failure_reason}")

    except Exception as e:
        logger.error(f"Error in message delivery loop: {e}", exc_info=e)


@message_delivery_loop.before_loop
async def before_message_delivery_loop():
    """Wait for bot to be ready before starting the loop"""
    await bot.wait_until_ready()


async def setup_bot():
    """Setup bot and load cogs"""
    global db_manager, delivery_service

    # Initialize database
    db_manager = DatabaseManager()

    try:
        # Log setup start
        logger.info("=== Bot Setup Starting ===")

        logger.info("Initializing database manager...")
        await db_manager.connect()

        logger.info("Initializing delivery service...")
        delivery_service = MessageDeliveryService(bot)

        # Add scheduler commands cog
        logger.info("Loading scheduler commands...")
        await bot.add_cog(SchedulerCommands(bot, db_manager))

        logger.info("=== Bot Setup Complete ✅ ===")
    except Exception as e:
        logger.error(f"❌ Error during bot setup: {e}", exc_info=e)
        raise


async def main():
    """Main entry point"""
    token = os.getenv("BOT_TOKEN")

    if not token:
        logger.error("""❌ BOT_TOKEN environment variable not set
                    Please create a .env file with your Discord Bot Token
                    You can copy from .env.example: cp .env.example .env""")
        raise ValueError("BOT_TOKEN environment variable is required")

    # Setup bot
    await setup_bot()

    # Run the bot
    try:
        logger.info("🚀 Starting bot...")
        await bot.start(token)
    except KeyboardInterrupt:
        logger.info("⏹️  Bot shutdown requested by user")
        await bot.close()
    except Exception as e:
        logger.error(f"❌ Fatal bot error: {e}", exc_info=e)
        raise
    finally:
        # Cleanup
        if db_manager:
            logger.info("Disconnecting from database...")
            await db_manager.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=e)
        raise
