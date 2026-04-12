"""
Discord bot commands for the Scheduler Bot
Implements: /help, /sch, /ls, /del, /mv (slash commands)

Follows Discord's Application Command structure (CHAT_INPUT type - type 1):
- Option Types: STRING (3), INTEGER (4), BOOLEAN (5), USER (6), CHANNEL (7), ROLE (8), ATTACHMENT (11)
- Required options must precede optional ones
- All options must have type, name, description, and required fields

Reference: https://docs.discord.com/developers/interactions/application-commands
"""

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from ..utils import (
    ValidationError,
    parse_time_input,
    parse_date_input,
    parse_destinations,
    validate_message_content,
    format_delivery_time,
    get_queue_position,
)
from ..db import DatabaseManager


class SchedulerCommands(commands.Cog):
    """Cog containing all scheduler slash commands (CHAT_INPUT type)"""

    def __init__(self, bot: commands.Bot, db: DatabaseManager):
        self.bot = bot
        self.db = db

    # ======================== /help Command ========================
    @app_commands.command(name="help", description="Show help information about the Scheduler Bot")
    async def help_command(self, interaction: discord.Interaction) -> None:
        """
        Display comprehensive help for all scheduler commands.

        CHAT_INPUT command with no parameters.
        No required options - optional parameters.
        """
        await interaction.response.defer()

        embed = discord.Embed(
            title="📅 Scheduler Bot - Help",
            description="Schedule and manage messages to be sent at a later time",
            color=discord.Color.blue(),
        )

        embed.add_field(name="/help", value="Show this help message", inline=False)

        embed.add_field(
            name="/sch [message] [destinations] [time] [date]",
            value="""Schedule a message for delivery at a specific time.

**Required Parameters:**
• `message` (STRING): Content to send
• `destinations` (STRING): Space-separated user/channel mentions or IDs (e.g., @user1 @user2 or 123456 789012)
• `time` (STRING): HH:MM format in 24-hour (e.g., "15:30")

**Optional Parameters:**
• `date` (STRING): DD/MM or DD/MM/YYYY format, defaults to today

**How to send to multiple users:**
Simply list them space-separated: `@rodrigo @alex @carlos` or `123456 789012 987654`

**Examples:**
`/sch message:"Hello!" destinations:"@rodrigo @alex" time:"15:30"`
`/sch message:"Report" destinations:"@rodrigo" time:"18:00" date:"25/12"`
`/sch message:"Files" destinations:"@rodrigo @alex @carlos" time:"09:00"`""",
            inline=False,
        )

        embed.add_field(name="/ls", value="List all your pending scheduled messages with delivery status", inline=False)

        embed.add_field(
            name="/del [message_id]",
            value="""Delete a pending scheduled message.

**Required Parameters:**
• `message_id` (STRING): Queue position (0 = next to send, 1 = after that, etc.)

**Example:** `/del message_id:"0"`""",
            inline=False,
        )

        embed.add_field(
            name="/mv [field] [message_id] [new_value]",
            value="""Update a pending message field.

**Required Parameters:**
• `field` (STRING): Field to update (content, destinations, day, or time)
• `message_id` (STRING): Queue position (0 = next)
• `new_value` (STRING): New value for the field

**Examples:**
`/mv field:"content" message_id:"0" new_value:"New message"`
`/mv field:"time" message_id:"0" new_value:"20:00"`""",
            inline=False,
        )

        embed.set_footer(text="Scheduler Bot - Discord Application Commands")
        await interaction.followup.send(embed=embed)

    # ======================== /sch Command ========================
    @app_commands.command(name="sch", description="Schedule a message for delivery at a specific time")
    @app_commands.describe(
        message="Message content to send (STRING)",
        destinations="User/channel mentions, space-separated (STRING)",
        time="Delivery time in HH:MM format, 24-hour (STRING)",
        date="Optional: delivery date in DD/MM or DD/MM/YYYY format (STRING)",
    )
    async def schedule_message(
        self,
        interaction: discord.Interaction,
        message: str,
        destinations: str,
        time: str,
        date: Optional[str] = None,
    ) -> None:
        """
        Schedule a new message for delivery.

        CHAT_INPUT command with 4 options:
        - 3 required: message, destinations, time
        - 1 optional: date
        """
        await interaction.response.defer()

        try:
            # Validate inputs
            validate_message_content(message)
            dests = parse_destinations(destinations)
            day, month, year = parse_date_input(date or "")
            hour, minute = parse_time_input(time)

            # Create message in database
            msg = await self.db.create_message(
                user_id=str(interaction.user.id),
                content=message,
                destinations=dests,
                day=day,
                month=month,
                year=year,
                hour=hour,
                minute=minute,
            )

            # Get queue position
            all_messages = await self.db.get_user_messages(str(interaction.user.id), include_delivered=False)
            position = get_queue_position(all_messages, msg["id"])

            # Send confirmation
            embed = discord.Embed(title="✅ Message Scheduled", color=discord.Color.green())
            embed.add_field(name="Message ID", value=str(position), inline=True)
            embed.add_field(name="Content", value=message[:100], inline=False)
            embed.add_field(
                name="Delivery Time", value=format_delivery_time(day, month, year, hour, minute), inline=True
            )
            embed.add_field(name="Destinations", value=f"{len(dests)} recipient(s)", inline=True)

            await interaction.followup.send(embed=embed)

        except ValidationError as e:
            embed = discord.Embed(title="❌ Error", description=str(e), color=discord.Color.red())
            await interaction.followup.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Unexpected Error", description=f"An error occurred: {str(e)}", color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)

    # ======================== /ls Command ========================
    @app_commands.command(name="ls", description="List all your pending scheduled messages")
    async def list_messages(self, interaction: discord.Interaction) -> None:
        """
        List all pending scheduled messages.

        CHAT_INPUT command with no parameters.
        """
        await interaction.response.defer()

        try:
            messages = await self.db.get_user_messages(str(interaction.user.id), include_delivered=False)

            if not messages:
                embed = discord.Embed(
                    title="📅 Your Scheduled Messages",
                    description="You have no pending scheduled messages",
                    color=discord.Color.blue(),
                )
                await interaction.followup.send(embed=embed)
                return

            embed = discord.Embed(title="📅 Your Pending Scheduled Messages", color=discord.Color.blue())

            for idx, msg in enumerate(messages):
                delivery_time = format_delivery_time(
                    msg.get("delivery_day"),
                    msg.get("delivery_month"),
                    msg.get("delivery_year"),
                    msg["delivery_hour"],
                    msg["delivery_minute"],
                )

                content_preview = msg["message_content"][:50]
                if len(msg["message_content"]) > 50:
                    content_preview += "..."

                status = "✅ Delivered" if msg.get("delivered_at") else "⏳ Pending"

                field_value = f"Content: {content_preview}\nDest: {len(msg['destinations'])} recipient(s)"

                embed.add_field(name=f"[{idx}] {delivery_time} {status}", value=field_value, inline=False)

            embed.set_footer(text=f"Total: {len(messages)} message(s). Use /del message_id to delete.")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            embed = discord.Embed(title="❌ Error", description=str(e), color=discord.Color.red())
            await interaction.followup.send(embed=embed)

    # ======================== /del Command ========================
    @app_commands.command(name="del", description="Delete a pending scheduled message")
    @app_commands.describe(message_id="Queue position of the message to delete (0 = next to send) (STRING)")
    async def delete_message(self, interaction: discord.Interaction, message_id: str) -> None:
        """
        Delete a pending scheduled message.

        CHAT_INPUT command with 1 required option:
        - message_id (STRING): Position in queue
        """
        await interaction.response.defer()

        try:
            # Get user's pending messages to convert position to ID
            messages = await self.db.get_user_messages(str(interaction.user.id), include_delivered=False)

            try:
                position = int(message_id)
                if position < 0 or position >= len(messages):
                    raise ValidationError(f"Invalid message ID: {message_id}. Valid range: 0-{len(messages) - 1}")
                actual_message_id = messages[position]["id"]
            except ValueError:
                actual_message_id = message_id

            # Delete message
            deleted = await self.db.delete_message(actual_message_id, str(interaction.user.id))

            if not deleted:
                raise ValidationError("Message not found or already deleted")

            embed = discord.Embed(
                title="✅ Message Deleted",
                description=f"Message {message_id} has been deleted",
                color=discord.Color.green(),
            )
            await interaction.followup.send(embed=embed)

        except ValidationError as e:
            embed = discord.Embed(title="❌ Error", description=str(e), color=discord.Color.red())
            await interaction.followup.send(embed=embed)

    # ======================== /mv Command ========================
    @app_commands.command(name="mv", description="Update a pending scheduled message field")
    @app_commands.describe(
        field="Field to update: content, destinations, day, or time (STRING)",
        message_id="Queue position of the message to update (0 = next) (STRING)",
        new_value="New value for the field (STRING)",
    )
    async def update_message(
        self, interaction: discord.Interaction, field: str, message_id: str, new_value: str
    ) -> None:
        """
        Update a pending scheduled message field.

        CHAT_INPUT command with 3 required options:
        - field (STRING): Which field to update
        - message_id (STRING): Position in queue
        - new_value (STRING): The new value
        """
        await interaction.response.defer()

        try:
            valid_fields = ["content", "destinations", "day", "time"]
            if field.lower() not in valid_fields:
                raise ValidationError(f"Unknown field: {field}. Valid fields: {', '.join(valid_fields)}")

            # Get user's pending messages
            messages = await self.db.get_user_messages(str(interaction.user.id), include_delivered=False)

            try:
                position = int(message_id)
                if position < 0 or position >= len(messages):
                    raise ValidationError(f"Invalid message ID: {message_id}. Valid range: 0-{len(messages) - 1}")
                actual_message_id = messages[position]["id"]
            except ValueError:
                actual_message_id = message_id

            # Get the message
            message = await self.db.get_message(actual_message_id, str(interaction.user.id))
            if not message:
                raise ValidationError("Message not found")

            # Update based on field
            update_data = {}
            field_lower = field.lower()

            if field_lower == "content":
                validate_message_content(new_value)
                update_data["message_content"] = new_value

            elif field_lower == "destinations":
                destinations = parse_destinations(new_value)
                update_data["destinations"] = destinations

            elif field_lower == "day":
                day, month, year = parse_date_input(new_value)
                if day is None:
                    raise ValidationError("Day is required in format DD/MM or DD/MM/YYYY")
                update_data["delivery_day"] = day
                if month is not None:
                    update_data["delivery_month"] = month
                if year is not None:
                    update_data["delivery_year"] = year

            elif field_lower == "time":
                hour, minute = parse_time_input(new_value)
                update_data["delivery_hour"] = hour
                update_data["delivery_minute"] = minute

            # Update in database
            updated = await self.db.update_message(actual_message_id, str(interaction.user.id), **update_data)

            if not updated:
                raise ValidationError("Failed to update message")

            # Get new position
            all_messages = await self.db.get_user_messages(str(interaction.user.id), include_delivered=False)
            new_position = get_queue_position(all_messages, actual_message_id)

            embed = discord.Embed(title="✅ Message Updated", color=discord.Color.green())
            embed.add_field(name="Field", value=field_lower, inline=True)
            embed.add_field(name="Queue Position", value=str(new_position), inline=True)

            # Show new delivery time if date/time was changed
            if field_lower in ["day", "time"]:
                new_message = await self.db.get_message(actual_message_id, str(interaction.user.id))
                if new_message:
                    delivery_time = format_delivery_time(
                        new_message.get("delivery_day"),
                        new_message.get("delivery_month"),
                        new_message.get("delivery_year"),
                        new_message["delivery_hour"],
                        new_message["delivery_minute"],
                    )
                    embed.add_field(name="New Delivery Time", value=delivery_time, inline=False)

            await interaction.followup.send(embed=embed)

        except ValidationError as e:
            embed = discord.Embed(title="❌ Error", description=str(e), color=discord.Color.red())
            await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    """Load the SchedulerCommands cog"""
    await bot.add_cog(SchedulerCommands(bot, bot.db))
