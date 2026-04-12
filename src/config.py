"""
Configuration for Scheduler Bot
Central place for all configuration variables
"""

import os
from enum import Enum


# Bot Configuration
class BotConfig:
    """Main bot configuration"""

    # Command settings
    COMMAND_PREFIX = "/"

    # Message settings
    MAX_MESSAGE_LENGTH = 2000
    MESSAGE_PREVIEW_LENGTH = 50
    MAX_DESTINATIONS_PER_MESSAGE = 20

    # Time settings
    MESSAGE_CHECK_INTERVAL_MINUTES = 1  # Check every minute for messages to send

    # Discord API settings
    # These are automatically handled by discord.py

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = "logs/scheduler_bot.log"
    LOG_MAX_BYTES = 10485760  # 10MB
    LOG_BACKUP_COUNT = 5

    # Database
    DATABASE_PATH = "db/database.db"
    DATABASE_SCHEMA_PATH = "prisma/schema.prisma"


class Environment(Enum):
    """Supported environments"""

    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"


def get_environment() -> Environment:
    """Get the current environment"""
    env = os.getenv("ENVIRONMENT", "development").lower()
    try:
        return Environment[env.upper()]
    except KeyError:
        return Environment.DEVELOPMENT


# Environment-specific settings
ENVIRONMENT = get_environment()

if ENVIRONMENT == Environment.PRODUCTION:
    # Production settings
    BotConfig.LOG_LEVEL = "WARNING"
else:
    # Development/Testing settings
    BotConfig.LOG_LEVEL = "DEBUG"
