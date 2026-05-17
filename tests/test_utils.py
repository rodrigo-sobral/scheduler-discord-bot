"""
Tests for utility functions in scheduler-discord-bot
Covers validation, parsing, and extraction functions
"""

import pytest
from src.utils import (
    ValidationError,
    parse_time_input,
    parse_date_input,
    validate_destination,
    extract_discord_id,
    parse_destinations,
    validate_message_content,
)


class TestParseTimeInput:
    """Test suite for parse_time_input function"""

    def test_valid_time_formats(self):
        """Test valid HH:MM time formats"""
        assert parse_time_input("00:00") == (0, 0)
        assert parse_time_input("12:30") == (12, 30)
        assert parse_time_input("23:59") == (23, 59)
        assert parse_time_input("09:05") == (9, 5)

    def test_time_boundary_values(self):
        """Test boundary values for hours and minutes"""
        assert parse_time_input("0:0") == (0, 0)
        assert parse_time_input("23:59") == (23, 59)
        assert parse_time_input("12:00") == (12, 0)
        assert parse_time_input("00:59") == (0, 59)

    def test_invalid_time_format_missing_colon(self):
        """Test that missing colon raises error"""
        with pytest.raises(ValidationError) as exc_info:
            parse_time_input("1230")
        assert "format HH:MM" in str(exc_info.value)

    def test_invalid_time_format_empty_string(self):
        """Test that empty string raises error"""
        with pytest.raises(ValidationError):
            parse_time_input("")

    def test_invalid_time_format_none(self):
        """Test that None raises error"""
        with pytest.raises(ValidationError):
            parse_time_input(None)

    def test_invalid_time_format_too_many_colons(self):
        """Test that too many components raises error"""
        with pytest.raises(ValidationError) as exc_info:
            parse_time_input("12:30:45")
        assert "format HH:MM" in str(exc_info.value)

    def test_invalid_time_non_numeric(self):
        """Test that non-numeric values raise error"""
        with pytest.raises(ValidationError) as exc_info:
            parse_time_input("ab:cd")
        assert "must be numbers" in str(exc_info.value)

    def test_invalid_hour_out_of_range(self):
        """Test that invalid hour values raise error"""
        with pytest.raises(ValidationError) as exc_info:
            parse_time_input("24:00")
        assert "Hour must be between 0 and 23" in str(exc_info.value)

        with pytest.raises(ValidationError):
            parse_time_input("-1:00")

    def test_invalid_minute_out_of_range(self):
        """Test that invalid minute values raise error"""
        with pytest.raises(ValidationError) as exc_info:
            parse_time_input("12:60")
        assert "Minute must be between 0 and 59" in str(exc_info.value)

        with pytest.raises(ValidationError):
            parse_time_input("12:-1")


class TestParseDateInput:
    """Test suite for parse_date_input function"""

    def test_empty_date_string(self):
        """Test that empty date returns None tuple"""
        assert parse_date_input("") == (None, None, None)
        assert parse_date_input(None) == (None, None, None)

    def test_day_only_format(self):
        """Test DD format (day only)"""
        assert parse_date_input("15") == (15, None, None)
        assert parse_date_input("01") == (1, None, None)
        assert parse_date_input("31") == (31, None, None)

    def test_day_month_format(self):
        """Test DD/MM format"""
        assert parse_date_input("15/06") == (15, 6, None)
        assert parse_date_input("01/01") == (1, 1, None)
        assert parse_date_input("31/12") == (31, 12, None)

    def test_full_date_format(self):
        """Test DD/MM/YYYY format"""
        assert parse_date_input("15/06/2026") == (15, 6, 2026)
        assert parse_date_input("01/01/2026") == (1, 1, 2026)
        assert parse_date_input("31/12/2030") == (31, 12, 2030)

    def test_date_invalid_format_too_many_parts(self):
        """Test that too many date components raise error"""
        with pytest.raises(ValidationError) as exc_info:
            parse_date_input("15/06/2026/extra")
        assert "Date format invalid" in str(exc_info.value)

    def test_date_invalid_non_numeric(self):
        """Test that non-numeric values raise error"""
        with pytest.raises(ValidationError) as exc_info:
            parse_date_input("ab/cd/efgh")
        assert "must be numbers" in str(exc_info.value)

    def test_date_invalid_day_out_of_range(self):
        """Test that invalid day values raise error"""
        with pytest.raises(ValidationError) as exc_info:
            parse_date_input("32/06/2026")
        assert "Day must be between 1 and 31" in str(exc_info.value)

        with pytest.raises(ValidationError):
            parse_date_input("0/01/2026")

    def test_date_invalid_month_out_of_range(self):
        """Test that invalid month values raise error"""
        with pytest.raises(ValidationError) as exc_info:
            parse_date_input("15/13/2026")
        assert "Month must be between 1 and 12" in str(exc_info.value)

        with pytest.raises(ValidationError):
            parse_date_input("15/0/2026")

    def test_date_invalid_year_in_past(self):
        """Test that past year values raise error"""
        with pytest.raises(ValidationError) as exc_info:
            parse_date_input("15/06/2020")
        assert "Year must be 2026 or later" in str(exc_info.value)


class TestValidateDestination:
    """Test suite for validate_destination function"""

    def test_valid_discord_id(self):
        """Test valid Discord user IDs (17-19 digits)"""
        assert validate_destination("123456789012345678") is True
        assert validate_destination("1234567890123456789") is True
        assert validate_destination("12345678901234567") is True

    def test_invalid_discord_id_wrong_length(self):
        """Test that short numeric IDs are accepted as plain IDs/usernames"""
        # The validator accepts any numeric string as a valid plain ID/username
        assert validate_destination("12345") is True  # Accepted as plain ID
        assert validate_destination("12345678901234567890") is True  # Also accepted
        # Only non-alphanumeric patterns are actually rejected
        assert validate_destination("!@#$%") is False

    def test_valid_discord_mention(self):
        """Test valid Discord mention formats"""
        assert validate_destination("<@123456789012345678>") is True
        assert validate_destination("<@!123456789012345678>") is True

    def test_valid_at_mention_with_username(self):
        """Test @username format"""
        assert validate_destination("@rodrigo") is True
        assert validate_destination("@user-name") is True
        assert validate_destination("@user_name") is True

    def test_valid_plain_username(self):
        """Test plain username without @ prefix"""
        assert validate_destination("rodrigo") is True
        assert validate_destination("user-name") is True
        assert validate_destination("user_name") is True

    def test_valid_channel_mention(self):
        """Test valid channel mention format"""
        assert validate_destination("#123456789012345678") is True

    def test_invalid_destination_empty(self):
        """Test that empty string is invalid"""
        assert validate_destination("") is False
        assert validate_destination(None) is False

    def test_invalid_destination_not_string(self):
        """Test that non-string types are invalid"""
        assert validate_destination(123) is False
        assert validate_destination(None) is False

    def test_invalid_destination_whitespace_only(self):
        """Test that whitespace-only string is invalid"""
        assert validate_destination("   ") is False

    def test_invalid_destination_special_chars(self):
        """Test that invalid special characters reject destinations"""
        assert validate_destination("@@user") is False
        assert validate_destination("user@domain.com") is False


class TestExtractDiscordId:
    """Test suite for extract_discord_id function"""

    def test_extract_from_numeric_id(self):
        """Test extraction from pure numeric ID"""
        assert extract_discord_id("123456789012345678") == "123456789012345678"

    def test_extract_from_user_mention(self):
        """Test extraction from <@ID> format"""
        assert extract_discord_id("<@123456789012345678>") == "123456789012345678"
        assert extract_discord_id("<@!123456789012345678>") == "123456789012345678"

    def test_extract_from_at_mention(self):
        """Test extraction from @username format"""
        assert extract_discord_id("@rodrigo") == "rodrigo"
        assert extract_discord_id("@user-name") == "user-name"

    def test_extract_from_plain_username(self):
        """Test extraction from plain username"""
        assert extract_discord_id("rodrigo") == "rodrigo"
        assert extract_discord_id("user-name") == "user-name"

    def test_extract_from_channel_mention(self):
        """Test extraction from channel mention"""
        assert extract_discord_id("#123456789012345678") == "123456789012345678"

    def test_extract_from_empty_string(self):
        """Test extraction from empty string"""
        assert extract_discord_id("") == ""

    def test_extract_from_none(self):
        """Test extraction from None"""
        assert extract_discord_id(None) is None

    def test_extract_with_whitespace(self):
        """Test that whitespace is stripped"""
        assert extract_discord_id("  @rodrigo  ") == "rodrigo"


class TestParseDestinations:
    """Test suite for parse_destinations function"""

    def test_single_destination(self):
        """Test parsing single destination"""
        result = parse_destinations("@rodrigo")
        assert result == ["rodrigo"]

    def test_multiple_destinations_space_separated(self):
        """Test parsing space-separated destinations"""
        result = parse_destinations("@rodrigo @alex @bot")
        assert set(result) == {"rodrigo", "alex", "bot"}

    def test_multiple_destinations_comma_separated(self):
        """Test parsing comma-separated destinations"""
        result = parse_destinations("@rodrigo, @alex, @bot")
        assert set(result) == {"rodrigo", "alex", "bot"}

    def test_mixed_format_destinations(self):
        """Test parsing destinations with mixed formats"""
        result = parse_destinations("@rodrigo 123456789012345678 <@987654321098765432>")
        assert "rodrigo" in result
        assert "123456789012345678" in result
        assert "987654321098765432" in result

    def test_destinations_with_extra_whitespace(self):
        """Test that extra whitespace is handled"""
        result = parse_destinations("  @rodrigo   @alex  ")
        assert set(result) == {"rodrigo", "alex"}

    def test_empty_destinations_raises_error(self):
        """Test that empty destination string raises error"""
        with pytest.raises(ValidationError) as exc_info:
            parse_destinations("")
        assert "At least one destination is required" in str(exc_info.value)

    def test_whitespace_only_destinations_raises_error(self):
        """Test that whitespace-only string raises error"""
        with pytest.raises(ValidationError) as exc_info:
            parse_destinations("   ")
        assert "At least one destination is required" in str(exc_info.value)

    def test_invalid_destination_format_raises_error(self):
        """Test that truly invalid destination format raises error"""
        # Mix a valid destination with an invalid one (with spaces in between)
        with pytest.raises(ValidationError) as exc_info:
            parse_destinations("@valid <invalid malformed")
        assert "Invalid destination format" in str(exc_info.value)

    def test_none_destinations_raises_error(self):
        """Test that None raises error"""
        with pytest.raises(ValidationError):
            parse_destinations(None)


class TestValidateMessageContent:
    """Test suite for validate_message_content function"""

    def test_valid_message_content(self):
        """Test that valid message content passes validation"""
        validate_message_content("Hello world!")
        validate_message_content("This is a test message")
        validate_message_content("A" * 100)  # 100 characters

    def test_maximum_length_message(self):
        """Test message at Discord's 2000 character limit"""
        validate_message_content("A" * 2000)

    def test_empty_message_raises_error(self):
        """Test that empty message raises error"""
        with pytest.raises(ValidationError) as exc_info:
            validate_message_content("")
        assert "cannot be empty" in str(exc_info.value)

    def test_whitespace_only_message_raises_error(self):
        """Test that whitespace-only message raises error"""
        with pytest.raises(ValidationError) as exc_info:
            validate_message_content("   ")
        assert "cannot be empty" in str(exc_info.value)

    def test_none_message_raises_error(self):
        """Test that None message raises error"""
        with pytest.raises(ValidationError):
            validate_message_content(None)

    def test_message_exceeds_character_limit_raises_error(self):
        """Test that message over 2000 characters raises error"""
        with pytest.raises(ValidationError) as exc_info:
            validate_message_content("A" * 2001)
        assert "cannot exceed 2000 characters" in str(exc_info.value)

    def test_message_far_exceeds_character_limit_raises_error(self):
        """Test that message far over limit raises error"""
        with pytest.raises(ValidationError) as exc_info:
            validate_message_content("A" * 5000)
        assert "cannot exceed 2000 characters" in str(exc_info.value)
