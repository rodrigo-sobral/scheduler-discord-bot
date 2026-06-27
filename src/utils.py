"""
Utility functions for the Scheduler Bot
Includes validation, parsing, and queue management
"""

import calendar
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import re

import dateparser
import discord
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    from geonamescache import GeonamesCache

    gc = GeonamesCache()
    _geonames_available = True
except ImportError:
    _geonames_available = False


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


def format_delivery_time(day: Optional[int], month: Optional[int], year: Optional[int], hour: int, minute: int, user_tz: Optional[str] = None) -> str:
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
        if user_tz and user_tz != "UTC":
            try:
                from zoneinfo import ZoneInfo
                utc_dt = dt.replace(tzinfo=ZoneInfo("UTC"))
                local_dt = utc_dt.astimezone(ZoneInfo(user_tz))
                return local_dt.strftime("%Y-%m-%d %H:%M") + f" ({user_tz})"
            except Exception:
                pass
        return dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}"


def build_delivery_datetime(
    day: Optional[int], month: Optional[int], year: Optional[int], hour: int, minute: int, tzinfo: Optional[ZoneInfo]
) -> datetime:
    """
    Build a datetime object from message delivery fields

    Args:
        day, month, year: Date components (optional)
        hour, minute: Time components

    Returns:
        datetime object
    """
    now = datetime.now(tzinfo)

    if day is None:
        day = now.day
    if month is None:
        month = now.month
    if year is None:
        year = now.year

    try:
        return datetime(year, month, day, hour, minute, tzinfo=tzinfo)
    except ValueError:
        # If invalid datetime, return current time (shouldn't happen with validation)
        return now


def compare_delivery_times(msg1: Dict, msg2: Dict, tzinfo: Optional[str]) -> int:
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
        tzinfo=tzinfo
    )
    dt2 = build_delivery_datetime(
        msg2.get("delivery_day"),
        msg2.get("delivery_month"),
        msg2.get("delivery_year"),
        msg2["delivery_hour"],
        msg2["delivery_minute"],
        tzinfo=tzinfo
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


def is_delivery_time(message: Dict, tzinfo: Optional[ZoneInfo]) -> bool:
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
        tzinfo=tzinfo
    )

    return datetime.now(tzinfo) >= delivery_dt


def validate_timezone(tz_name: str) -> None:
    """Raise ValidationError if tz_name is not a valid IANA timezone."""
    try:
        ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, KeyError):
        raise ValidationError(
            f"Unknown timezone: `{tz_name}`. Use an IANA name such as `Europe/Lisbon`, `America/New_York`, or `UTC`."
        )


def city_to_timezone(city: str) -> str:
    """
    Convert a city name to IANA timezone using modern geonamescache 3.0+ API.

    Uses search_cities() with intelligent filtering strategy:
    1. Exact name matches → picks highest population
    2. Names starting with query → picks highest population
    3. All results → picks highest population

    Args:
        city: City name (case-insensitive, e.g., "Tokyo", "London", "New York")

    Returns:
        IANA timezone name

    Raises:
        ValidationError: If city not found
    """
    if not _geonames_available:
        raise ValidationError(
            "Geonames library not available. Use IANA timezone directly (e.g., `Europe/Lisbon`, `America/New_York`)"
        )

    city = city.strip()
    if not city:
        raise ValidationError("City name cannot be empty.")

    city_lower = city.lower()

    # Use search_cities() - the modern method in geonamescache 3.0+
    try:
        results = gc.search_cities(city)
        if not results:
            raise ValidationError(f"City `{city}` not found.")

        # Strategy 1: Look for exact name matches (case-insensitive)
        exact_matches = [c for c in results if c.get("name", "").lower() == city_lower]
        if exact_matches:
            # If multiple exact matches, pick the highest population
            best = max(exact_matches, key=lambda x: x.get("population", 0) or 0)
            timezone = best.get("timezone")
            if timezone:
                return timezone

        # Strategy 2: Filter for good matches (name starts with query) and pick by population
        good_matches = [c for c in results if c.get("name", "").lower().startswith(city_lower)]
        if good_matches:
            # Sort by population descending to get the most significant city
            best = max(good_matches, key=lambda x: x.get("population", 0) or 0)
            timezone = best.get("timezone")
            if timezone:
                return timezone

        # Strategy 3: Return highest population city from all results
        best = max(results, key=lambda x: x.get("population", 0) or 0)
        timezone = best.get("timezone")
        if timezone:
            return timezone

    except ValidationError:
        raise
    except Exception as e:
        raise ValidationError(f"Error searching cities: {e}")

    raise ValidationError(
        f"City `{city}` not found in geonames database.\n"
        f"Try: city name like `Tokyo`, `London`, `New York`, `Berlin`\n"
        f"Or use IANA timezone directly (e.g., `Europe/Lisbon`, `America/New_York`)"
    )


def resolve_timezone(input_str: str) -> str:
    """
    Resolve timezone from either a city name or IANA timezone name.

    Args:
        input_str: City name or IANA timezone

    Returns:
        IANA timezone name

    Raises:
        ValidationError: If neither valid city nor timezone
    """
    # First, try as IANA timezone
    try:
        validate_timezone(input_str)
        return input_str
    except ValidationError:
        pass

    # Then, try as city name
    try:
        return city_to_timezone(input_str)
    except ValidationError:
        pass

    raise ValidationError(
        f"Invalid timezone or city: `{input_str}`.\n"
        f"Use either:\n"
        f"• A city name (e.g., `Tokyo`, `London`, `New York`)\n"
        f"• An IANA timezone (e.g., `Europe/Lisbon`, `America/New_York`)"
    )

def parse_time_expression(expr: str, user_tz: str = "UTC") -> Tuple[int, int, Optional[int], Optional[int], Optional[int]]:
    """
    Parse a time expression (natural language or structured) and return
    (hour, minute, day, month, year) adjusted to server-local time.

    Accepts: "15:30", "25/12 09:00", "tomorrow at 3pm", "next Friday", "in 2 hours"
    """
    expr = expr.strip()
    if not expr:
        raise ValidationError("Time expression cannot be empty.")

    try:
        tz = ZoneInfo(user_tz)
    except (ZoneInfoNotFoundError, KeyError):
        tz = ZoneInfo("UTC")
        user_tz = "UTC"

    now_in_tz = datetime.now(tz)

    parsed = dateparser.parse(
        expr,
        settings={
            "TIMEZONE": user_tz,
            "RETURN_AS_TIMEZONE_AWARE": True,
            "PREFER_DATES_FROM": "future",
            "DATE_ORDER": "DMY",
            "RELATIVE_BASE": now_in_tz,
        },
    )

    if parsed is not None:
        # Convert to UTC — format_delivery_time and is_delivery_time both work in UTC
        utc_dt = parsed.astimezone(tz)
        return utc_dt.hour, utc_dt.minute, utc_dt.day, utc_dt.month, utc_dt.year

    # Fallback: "DD/MM HH:MM" or "DD/MM/YYYY HH:MM"
    parts = expr.split()
    if len(parts) == 2:
        try:
            day, month, year = parse_date_input(parts[0])
            hour, minute = parse_time_input(parts[1])
            y = year or now_in_tz.year
            m = month or now_in_tz.month
            d = day or now_in_tz.day
            local_dt = datetime(y, m, d, hour, minute, tzinfo=tz)
            utc_dt = local_dt.astimezone(ZoneInfo("UTC"))
            return utc_dt.hour, utc_dt.minute, utc_dt.day, utc_dt.month, utc_dt.year
        except ValidationError:
            pass

    # Fallback: bare "HH:MM"
    try:
        hour, minute = parse_time_input(expr)
        local_dt = now_in_tz.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return local_dt.hour, local_dt.minute, local_dt.day, local_dt.month, local_dt.year
    except ValidationError:
        pass

    raise ValidationError(
        f"Could not parse `{expr}`. Try: `15:30`, `25/12 09:00`, `tomorrow at 3pm`, `next Friday 15:30`, `in 2 hours`."
    )


def get_relative_time_str(day: Optional[int], month: Optional[int], year: Optional[int], hour: int, minute: int, tzinfo: Optional[ZoneInfo]) -> str:
    """Return a short relative-time label: 'overdue', 'in 4h 20m', 'in 2d', etc."""
    delivery_dt = build_delivery_datetime(day, month, year, hour, minute, tzinfo=tzinfo)
    delta = delivery_dt - datetime.now(tzinfo)
    total_secs = delta.total_seconds()
    print(f"Delivery time: {delivery_dt}\nnow: {datetime.now(tzinfo)}\ndelta: {delta}\ntotal_secs: {total_secs}")

    if total_secs < 0:
        return "overdue"

    total_mins = int(total_secs / 60)
    if total_mins < 60:
        return f"in {total_mins}m"
    hours = total_mins // 60
    mins = total_mins % 60
    if hours < 24:
        return f"in {hours}h {mins}m" if mins else f"in {hours}h"
    days = hours // 24
    hrs = hours % 24
    if days < 7:
        return f"in {days}d {hrs}h" if hrs else f"in {days}d"
    return f"in {days // 7}w"


def get_urgency_color(day: Optional[int], month: Optional[int], year: Optional[int], hour: int, minute: int, tzinfo: Optional[ZoneInfo]) -> discord.Color:
    """Red for <1h or overdue, orange for <24h, green otherwise."""
    delivery_dt = build_delivery_datetime(day, month, year, hour, minute, tzinfo=tzinfo)
    secs = (delivery_dt - datetime.now(tzinfo)).total_seconds()
    if secs < 3600:
        return discord.Color.red()
    if secs < 86400:
        return discord.Color.orange()
    return discord.Color.green()


def compute_next_recurrence(message: Dict, tzinfo: Optional[ZoneInfo]) -> Optional[Tuple[int, int, Optional[int], Optional[int], Optional[int]]]:
    """
    Given a recurring message, return (hour, minute, day, month, year) for its
    next delivery, or None if the message is not recurring.
    """
    interval = message.get("repeat_interval")
    if not interval:
        return None

    current = build_delivery_datetime(
        message.get("delivery_day"),
        message.get("delivery_month"),
        message.get("delivery_year"),
        message["delivery_hour"],
        message["delivery_minute"],
        tzinfo=tzinfo
    )

    if interval == "daily":
        nxt = current + timedelta(days=1)
    elif interval == "weekly":
        nxt = current + timedelta(weeks=1)
    elif interval == "monthly":
        m = current.month + 1
        y = current.year
        if m > 12:
            m, y = 1, y + 1
        max_day = calendar.monthrange(y, m)[1]
        nxt = current.replace(year=y, month=m, day=min(current.day, max_day))
    else:
        return None

    return nxt.hour, nxt.minute, nxt.day, nxt.month, nxt.year

async def format_destinations_with_names(bot, destination_ids: list[str], max_names: int = 5) -> str:
    """
    Format destination IDs as readable names (usernames or channel names).

    Args:
        bot: Discord bot instance to fetch user/channel info
        destination_ids: List of Discord user/channel IDs
        max_names: Maximum names to show before using count

    Returns:
        Formatted string with names or count
    """
    if not destination_ids:
        return "No destinations"

    names = []
    for dest_id in destination_ids[:max_names]:
        try:
            # Try to fetch as user first
            user = await bot.fetch_user(int(dest_id))
            names.append(f"@{user.name}")
        except (discord.NotFound, ValueError):
            try:
                # Try to fetch as channel
                channel = bot.get_channel(int(dest_id))
                if channel:
                    names.append(f"#{channel.name}")
                else:
                    names.append(f"ID:{dest_id[:8]}")
            except ValueError:
                names.append(dest_id)

    if len(destination_ids) > max_names:
        return ", ".join(names) + f" +{len(destination_ids) - max_names} more"

    return ", ".join(names)
