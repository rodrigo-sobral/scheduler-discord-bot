"""
Utility functions for the Scheduler Bot
Includes validation, parsing, and queue management
"""

import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import re


class ValidationError(Exception):
    """Custom error for validation failures"""

    pass


def parse_time_input(time_str: str) -> Tuple[int, int]:
    """
    Parse time string in format HH:MM

    Args:
        time_str: Time string in format HH:MM

    Returns:
        Tuple of (hour, minute)

    Raises:
        ValidationError: If format is invalid or values are out of range
    """
    if not time_str or ":" not in time_str:
        raise ValidationError("Time must be in format HH:MM")

    parts = time_str.split(":")
    if len(parts) != 2:
        raise ValidationError("Time must be in format HH:MM")

    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        raise ValidationError("Hour and minute must be numbers")

    if not (0 <= hour <= 23):
        raise ValidationError(f"Hour must be between 0 and 23, got {hour}")
    if not (0 <= minute <= 59):
        raise ValidationError(f"Minute must be between 0 and 59, got {minute}")

    return hour, minute


def parse_date_input(date_str: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """
    Parse date string in format DD/MM/YYYY or DD/MM or just DD
    If not provided, returns None for missing components

    Args:
        date_str: Date string (optional)

    Returns:
        Tuple of (day, month, year) - any can be None if not provided

    Raises:
        ValidationError: If format is invalid or values are out of range
    """
    if not date_str:
        return None, None, None

    parts = date_str.split("/")
    day = month = year = None
    min_year = datetime.now().year

    try:
        if len(parts) >= 1:
            day = int(parts[0])
        if len(parts) >= 2:
            month = int(parts[1])
        if len(parts) >= 3:
            year = int(parts[2])
        if len(parts) > 3:
            raise ValidationError("Date format invalid. Use DD, DD/MM, or DD/MM/YYYY")
    except ValueError:
        raise ValidationError("Date components must be numbers")

    # Validate values
    if day is not None and not (1 <= day <= 31):
        raise ValidationError(f"Day must be between 1 and 31, got {day}")
    if month is not None and not (1 <= month <= 12):
        raise ValidationError(f"Month must be between 1 and 12, got {month}")
    if year is not None and year < min_year:
        raise ValidationError(f"Year must be {min_year} or later, got {year}")

    return day, month, year


def validate_destination(destination: str) -> bool:
    """
    Validate that a destination is a valid Discord ID, mention, or username

    Args:
        destination: Destination string (user ID, mention, or username)

    Returns:
        True if valid, False otherwise
    """
    if not destination or not isinstance(destination, str):
        return False

    destination = destination.strip()

    # Check for valid Discord ID (17-19 digits for user IDs)
    if destination.isdigit() and 17 <= len(destination) <= 19:
        return True

    # Check for Discord mention format <@ID> or <@!ID>
    if re.match(r"^<@!?\d+>$", destination):
        return True

    # Check for @mention format (username or ID)
    # Allows @username, @123456, etc.
    if re.match(r"^@[\w-]{1,32}$|^@\d+$", destination):
        return True

    # Check for plain username format (no @ prefix)
    # Allows: username, user-name, user_name, 123456
    if re.match(r"^[\w-]{1,32}$|^\d+$", destination):
        return True

    # Check for #channel mention #ID
    if re.match(r"^#\d+$", destination):
        return True

    return False


def extract_discord_id(destination: str) -> str:
    """
    Extract Discord ID or username from various mention formats

    Args:
        destination: Destination string

    Returns:
        Discord ID or username
    """
    if not destination:
        return destination

    destination = destination.strip()

    # If it's already a pure ID (digits), return as-is
    if destination.isdigit():
        return destination

    # Extract from <@ID>, <@!ID>, or similar mention format
    match = re.search(r"<@!?(\d+)>", destination)
    if match:
        return match.group(1)

    # Extract username from @username (remove @)
    if destination.startswith("@"):
        return destination[1:]

    # Extract ID from #channel mention
    match = re.search(r"#(\d+)", destination)
    if match:
        return match.group(1)

    # Return as-is if no pattern matched (could be plain username)
    return destination


def parse_destinations(raw_destinations: str) -> List[str]:
    """
    Parse destinations from raw string (space or comma separated)

    Args:
        raw_destinations: Raw destination string

    Returns:
        List of validated destination IDs

    Raises:
        ValidationError: If any destination is invalid
    """
    if not raw_destinations or not raw_destinations.strip():
        raise ValidationError("At least one destination is required")

    # Split by space or comma
    destinations = re.split(r"[,\s]+", raw_destinations.strip())
    destinations = [d.strip() for d in destinations if d.strip()]

    if not destinations:
        raise ValidationError("At least one destination is required")

    validated_ids = []
    for dest in destinations:
        if not validate_destination(dest):
            raise ValidationError(f"Invalid destination format: {dest}")
        validated_ids.append(extract_discord_id(dest))

    return validated_ids


def validate_message_content(content: str) -> None:
    """
    Validate message content

    Args:
        content: Message content

    Raises:
        ValidationError: If content is invalid
    """
    if not content or not content.strip():
        raise ValidationError("Message content cannot be empty")

    if len(content) > 2000:
        raise ValidationError(f"Message content cannot exceed 2000 characters (got {len(content)})")


def serialize_destinations(destinations: List[str]) -> str:
    """Serialize destinations list to JSON"""
    return json.dumps(destinations)


def deserialize_destinations(destinations_json: str) -> List[str]:
    """Deserialize destinations from JSON"""
    try:
        return json.loads(destinations_json)
    except json.JSONDecodeError:
        return []


def format_delivery_time(day: Optional[int], month: Optional[int], year: Optional[int], hour: int, minute: int) -> str:
    """
    Format delivery time for display

    Args:
        day, month, year: Date components (optional)
        hour, minute: Time components

    Returns:
        Formatted time string
    """
    now = datetime.now()

    # Use current date if not specified
    if day is None:
        day = now.day
    if month is None:
        month = now.month
    if year is None:
        year = now.year

    try:
        dt = datetime(year, month, day, hour, minute)
        return dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}"


def build_delivery_datetime(
    day: Optional[int], month: Optional[int], year: Optional[int], hour: int, minute: int
) -> datetime:
    """
    Build a datetime object from message delivery fields

    Args:
        day, month, year: Date components (optional)
        hour, minute: Time components

    Returns:
        datetime object
    """
    now = datetime.now()

    if day is None:
        day = now.day
    if month is None:
        month = now.month
    if year is None:
        year = now.year

    try:
        return datetime(year, month, day, hour, minute)
    except ValueError:
        # If invalid datetime, return current time (shouldn't happen with validation)
        return now


def compare_delivery_times(msg1: Dict, msg2: Dict) -> int:
    """
    Compare two messages' delivery times
    Returns -1 if msg1 < msg2, 0 if equal, 1 if msg1 > msg2
    """
    dt1 = build_delivery_datetime(
        msg1.get("delivery_day"),
        msg1.get("delivery_month"),
        msg1.get("delivery_year"),
        msg1["delivery_hour"],
        msg1["delivery_minute"],
    )
    dt2 = build_delivery_datetime(
        msg2.get("delivery_day"),
        msg2.get("delivery_month"),
        msg2.get("delivery_year"),
        msg2["delivery_hour"],
        msg2["delivery_minute"],
    )

    if dt1 < dt2:
        return -1
    elif dt1 > dt2:
        return 1
    else:
        return 0


def get_queue_position(messages: List[Dict], message_id: str) -> Optional[int]:
    """
    Get the position of a message in the queue (0 is next to deliver)

    Args:
        messages: List of messages
        message_id: Message ID to find

    Returns:
        Position (0-indexed) or None if not found
    """
    for idx, msg in enumerate(messages):
        if msg["id"] == message_id:
            return idx
    return None


def is_delivery_time(message: Dict) -> bool:
    """
    Check if a message's delivery time has arrived

    Args:
        message: Message dict with delivery fields

    Returns:
        True if current time >= delivery time, False otherwise
    """
    delivery_dt = build_delivery_datetime(
        message.get("delivery_day"),
        message.get("delivery_month"),
        message.get("delivery_year"),
        message["delivery_hour"],
        message["delivery_minute"],
    )

    now = datetime.now()

    # Consider message ready for delivery if current time is >= delivery time
    # and we're within the same minute (to avoid multiple deliveries)
    return (
        now.year == delivery_dt.year
        and now.month == delivery_dt.month
        and now.day == delivery_dt.day
        and now.hour == delivery_dt.hour
        and now.minute == delivery_dt.minute
    )
