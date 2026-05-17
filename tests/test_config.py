"""
Tests for configuration module
Verifies bot configuration constants and environment setup
"""

import os
import pytest
from src.config import BotConfig, Environment, get_environment


class TestBotConfig:
    """Test suite for BotConfig class"""

    def test_command_prefix(self):
        """Test command prefix is set to /"""
        assert BotConfig.COMMAND_PREFIX == "/"

    def test_max_message_length(self):
        """Test Discord message length limit"""
        assert BotConfig.MAX_MESSAGE_LENGTH == 2000

    def test_message_preview_length(self):
        """Test message preview truncation length"""
        assert BotConfig.MESSAGE_PREVIEW_LENGTH == 50

    def test_max_destinations_per_message(self):
        """Test maximum destinations allowed per message"""
        assert BotConfig.MAX_DESTINATIONS_PER_MESSAGE == 20

    def test_message_check_interval(self):
        """Test message delivery check interval"""
        assert BotConfig.MESSAGE_CHECK_INTERVAL_MINUTES == 1
        assert isinstance(BotConfig.MESSAGE_CHECK_INTERVAL_MINUTES, int)

    def test_log_level_default(self):
        """Test log level respects environment or defaults to INFO"""
        # LOG_LEVEL is loaded at module import time, so just verify it's set
        assert BotConfig.LOG_LEVEL is not None
        assert isinstance(BotConfig.LOG_LEVEL, str)
        # Should be a valid log level
        assert BotConfig.LOG_LEVEL in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    def test_log_file_path(self):
        """Test log file path"""
        assert BotConfig.LOG_FILE == "logs/scheduler_bot.log"

    def test_log_max_bytes(self):
        """Test log max bytes for rotation"""
        assert BotConfig.LOG_MAX_BYTES == 10485760  # 10MB
        assert isinstance(BotConfig.LOG_MAX_BYTES, int)

    def test_log_backup_count(self):
        """Test log file backup count"""
        assert BotConfig.LOG_BACKUP_COUNT == 5

    def test_database_path(self):
        """Test database path"""
        assert BotConfig.DATABASE_PATH == "db/database.db"
        assert "database.db" in BotConfig.DATABASE_PATH

    def test_database_schema_path(self):
        """Test database schema path"""
        assert BotConfig.DATABASE_SCHEMA_PATH == "prisma/schema.prisma"


class TestEnvironment:
    """Test suite for Environment enum"""

    def test_environment_development(self):
        """Test development environment"""
        assert Environment.DEVELOPMENT.value == "development"

    def test_environment_production(self):
        """Test production environment"""
        assert Environment.PRODUCTION.value == "production"

    def test_environment_testing(self):
        """Test testing environment"""
        assert Environment.TESTING.value == "testing"

    def test_all_environments_defined(self):
        """Test that all expected environments are defined"""
        envs = [e.value for e in Environment]
        assert "development" in envs
        assert "production" in envs
        assert "testing" in envs


class TestGetEnvironment:
    """Test suite for get_environment function"""

    def test_get_environment_from_env_var(self):
        """Test reading environment from env var"""
        original = os.environ.get("ENVIRONMENT")
        try:
            os.environ["ENVIRONMENT"] = "production"
            env = get_environment()
            assert env == Environment.PRODUCTION
        finally:
            if original:
                os.environ["ENVIRONMENT"] = original
            else:
                os.environ.pop("ENVIRONMENT", None)

    def test_get_environment_default_development(self):
        """Test default environment is development"""
        original = os.environ.get("ENVIRONMENT")
        try:
            os.environ.pop("ENVIRONMENT", None)
            env = get_environment()
            assert env == Environment.DEVELOPMENT
        finally:
            if original:
                os.environ["ENVIRONMENT"] = original

    def test_get_environment_case_insensitive(self):
        """Test that environment name is case insensitive"""
        original = os.environ.get("ENVIRONMENT")
        try:
            os.environ["ENVIRONMENT"] = "PRODUCTION"
            env = get_environment()
            assert env == Environment.PRODUCTION

            os.environ["ENVIRONMENT"] = "DevelopMent"
            env = get_environment()
            assert env == Environment.DEVELOPMENT
        finally:
            if original:
                os.environ["ENVIRONMENT"] = original
            else:
                os.environ.pop("ENVIRONMENT", None)


class TestConfigConstants:
    """Test suite for configuration constants relationships"""

    def test_message_preview_less_than_max_length(self):
        """Test that preview length is less than max message length"""
        assert BotConfig.MESSAGE_PREVIEW_LENGTH < BotConfig.MAX_MESSAGE_LENGTH

    def test_log_backup_count_positive(self):
        """Test that log backup count is positive"""
        assert BotConfig.LOG_BACKUP_COUNT > 0

    def test_message_check_interval_positive(self):
        """Test that message check interval is positive"""
        assert BotConfig.MESSAGE_CHECK_INTERVAL_MINUTES > 0

    def test_max_destinations_reasonable(self):
        """Test that max destinations is reasonable"""
        assert 1 <= BotConfig.MAX_DESTINATIONS_PER_MESSAGE <= 100

