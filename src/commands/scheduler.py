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
    format_destinations_with_names,
    get_queue_position,
    parse_time_expression,
    get_relative_time_str,
    get_urgency_color,
    resolve_timezone,
)
from ..db import DatabaseManager


REPEAT_CHOICES = [
    app_commands.Choice(name="None (one-time)", value="none"),
    app_commands.Choice(name="Daily",           value="daily"),
    app_commands.Choice(name="Weekly",          value="weekly"),
    app_commands.Choice(name="Monthly",         value="monthly"),
]


class ConfirmScheduleView(discord.ui.View):
    def __init__(self, owner_id: str):
        super().__init__(timeout=60)
        self.owner_id = owner_id
        self.confirmed: Optional[bool] = None

    def _disable_all(self):
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.owner_id:
            await interaction.response.send_message("This is not your action.", ephemeral=True)
            return
        self.confirmed = True
        self._disable_all()
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.owner_id:
            await interaction.response.send_message("This is not your action.", ephemeral=True)
            return
        self.confirmed = False
        self._disable_all()
        await interaction.response.edit_message(view=self)
        self.stop()


class EditMessageModal(discord.ui.Modal, title="Edit Scheduled Message"):
    def __init__(self, message: dict, db: DatabaseManager, user_tz: str):
        super().__init__()
        self._msg = message
        self._db = db
        self._tz = user_tz
        self.content_input: discord.ui.TextInput = discord.ui.TextInput(
            label="Message content",
            default=message["message_content"][:4000],
            style=discord.TextStyle.paragraph,
            max_length=2000,
            required=True,
        )
        self.time_input: discord.ui.TextInput = discord.ui.TextInput(
            label="Delivery time (e.g. tomorrow 3pm)",
            default=format_delivery_time(
                message.get("delivery_day"), message.get("delivery_month"),
                message.get("delivery_year"), message["delivery_hour"], message["delivery_minute"],
            ),
            max_length=100,
            required=True,
        )
        self.add_item(self.content_input)
        self.add_item(self.time_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            validate_message_content(self.content_input.value)
            h, m, d, mo, y = parse_time_expression(self.time_input.value, self._tz)
            await self._db.update_message(
                self._msg["id"], str(interaction.user.id),
                message_content=self.content_input.value,
                delivery_hour=h, delivery_minute=m,
                delivery_day=d, delivery_month=mo, delivery_year=y,
            )
            embed = discord.Embed(title="✅ Message Updated", color=discord.Color.green())
            embed.add_field(name="Content", value=self.content_input.value[:100], inline=False)
            embed.add_field(name="New Time", value=format_delivery_time(d, mo, y, h, m, self._tz), inline=True)
            await interaction.followup.send(embed=embed, ephemeral=True)
        except ValidationError as e:
            await interaction.followup.send(f"❌ {e}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Unexpected error: {e}", ephemeral=True)


class EditButton(discord.ui.Button):
    def __init__(self, idx: int, msg: dict, db: DatabaseManager, user_tz: str, owner_id: str):
        super().__init__(label=f"✏️ Edit #{idx}", style=discord.ButtonStyle.secondary, row=idx)
        self._msg, self._db, self._tz, self._owner_id = msg, db, user_tz, owner_id

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self._owner_id:
            await interaction.response.send_message("This is not your queue.", ephemeral=True)
            return
        await interaction.response.send_modal(EditMessageModal(self._msg, self._db, self._tz))


class DeleteButton(discord.ui.Button):
    def __init__(self, idx: int, msg: dict, db: DatabaseManager, owner_id: str):
        super().__init__(label=f"🗑️ #{idx}", style=discord.ButtonStyle.danger, row=idx)
        self._idx, self._msg, self._db, self._owner_id = idx, msg, db, owner_id

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self._owner_id:
            await interaction.response.send_message("This is not your queue.", ephemeral=True)
            return
        deleted = await self._db.delete_message(self._msg["id"], str(interaction.user.id))
        if deleted:
            await interaction.response.send_message(f"✅ Message **#{self._idx}** deleted.", ephemeral=True)
        else:
            await interaction.response.send_message("Failed to delete — it may already be gone.", ephemeral=True)


class PauseResumeButton(discord.ui.Button):
    def __init__(self, idx: int, msg: dict, db: DatabaseManager, owner_id: str):
        is_paused = msg.get("paused", False)
        super().__init__(
            label="▶️ Resume" if is_paused else "⏸️ Pause",
            style=discord.ButtonStyle.primary if is_paused else discord.ButtonStyle.secondary,
            row=idx,
        )
        self._idx, self._msg, self._db, self._owner_id = idx, msg, db, owner_id

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self._owner_id:
            await interaction.response.send_message("This is not your queue.", ephemeral=True)
            return
        is_paused = self._msg.get("paused", False)
        if is_paused:
            result = await self._db.resume_message(self._msg["id"], str(interaction.user.id))
            label = "resumed"
        else:
            result = await self._db.pause_message(self._msg["id"], str(interaction.user.id))
            label = "paused"
        if result:
            await interaction.response.send_message(f"{'▶️' if is_paused else '⏸️'} Message **#{self._idx}** {label}.", ephemeral=True)
        else:
            await interaction.response.send_message("Could not update message.", ephemeral=True)


class QueueView(discord.ui.View):
    """Edit + Pause/Resume + Delete buttons for the /ls response (one row per message, up to 5)."""
    def __init__(self, messages: list, db: DatabaseManager, user_tz: str, owner_id: str):
        super().__init__(timeout=300)
        for idx, msg in enumerate(messages[:5]):
            self.add_item(EditButton(idx, msg, db, user_tz, owner_id))
            self.add_item(PauseResumeButton(idx, msg, db, owner_id))
            self.add_item(DeleteButton(idx, msg, db, owner_id))


class SchedulerCommands(commands.Cog):
    """Cog containing all scheduler slash commands (CHAT_INPUT type)"""

    def __init__(self, bot: commands.Bot, db: DatabaseManager):
        self.bot = bot
        self.db = db

    async def _get_user_tz(self, user_id: str) -> str:
        record = await self.db.get_user_timezone(user_id)
        return record["timezone"] if record else "UTC"

    # ======================== /help Command ========================
    @app_commands.command(name="help", description="Show help information about the Scheduler Bot")
    @app_commands.describe(command="Get detailed help for a specific command")
    @app_commands.choices(command=[
        app_commands.Choice(name="sch",     value="sch"),
        app_commands.Choice(name="ls",      value="ls"),
        app_commands.Choice(name="del",     value="del"),
        app_commands.Choice(name="mv",      value="mv"),
        app_commands.Choice(name="history", value="history"),
        app_commands.Choice(name="tz",      value="tz"),
        app_commands.Choice(name="dup",     value="dup"),
        app_commands.Choice(name="pause",   value="pause"),
        app_commands.Choice(name="resume",  value="resume"),
        app_commands.Choice(name="tpl",     value="tpl"),
    ])
    async def help_command(self, interaction: discord.Interaction, command: Optional[str] = None) -> None:
        """
        Display comprehensive help for all scheduler commands.

        CHAT_INPUT command with no parameters.
        No required options - optional parameters.
        """
        await interaction.response.defer()

        if command == "sch":
            embed = discord.Embed(title="📅 /sch — Schedule a Message", color=discord.Color.blue())
            embed.add_field(
                name="Parameters",
                value=(
                    "• `message` *(required)*: Content to send\n"
                    "• `destinations` *(required)*: Space-separated user/channel mentions or IDs\n"
                    "• `time` *(required)*: Delivery time — HH:MM or natural language\n"
                    "• `date` *(optional)*: DD/MM or DD/MM/YYYY — only needed if not included in `time`\n"
                    "• `repeat` *(optional)*: `daily`, `weekly`, `monthly`, or none\n"
                    "• `attachment` *(optional)*: File to attach to the delivered message"
                ),
                inline=False,
            )
            embed.add_field(
                name="Time formats",
                value=(
                    "`15:30` · `25/12 09:00` · `tomorrow at 3pm` · `next Friday` · `in 2 hours`\n"
                    "Set your timezone with `/tz set` so times are interpreted correctly."
                ),
                inline=False,
            )
            embed.add_field(
                name="Examples",
                value=(
                    '`/sch message:"Hello!" destinations:"@username1 @username2" time:"15:30"`\n'
                    '`/sch message:"Report" destinations:"@username1" time:"18:00" date:"25/12"`\n'
                    '`/sch message:"Stand-up" destinations:"#general" time:"tomorrow at 9am" repeat:Daily`'
                ),
                inline=False,
            )

        elif command == "ls":
            embed = discord.Embed(title="📋 /ls — List Pending Messages", color=discord.Color.blue())
            embed.add_field(
                name="What it shows",
                value=(
                    "All your pending scheduled messages, sorted by delivery time.\n"
                    "Each entry is colour-coded by urgency:\n"
                    "🔴 Overdue or < 1 h · 🟠 < 24 h · 🟢 Later"
                ),
                inline=False,
            )
            embed.add_field(
                name="Buttons",
                value=(
                    "Each message (up to 5) has **✏️ Edit** and **🗑️ Delete** buttons.\n"
                    "Edit opens a form pre-filled with the current content and time.\n"
                    "For positions beyond #4 use `/del` or `/mv`."
                ),
                inline=False,
            )
            embed.add_field(name="Example", value="`/ls`", inline=False)

        elif command == "del":
            embed = discord.Embed(title="🗑️ /del — Delete a Pending Message", color=discord.Color.blue())
            embed.add_field(
                name="Parameters",
                value="• `message_id` *(required)*: Queue position to delete — `0` = next to send",
                inline=False,
            )
            embed.add_field(
                name="Examples",
                value="`/del message_id:0`\n`/del message_id:2`",
                inline=False,
            )

        elif command == "mv":
            embed = discord.Embed(title="✏️ /mv — Update a Pending Message", color=discord.Color.blue())
            embed.add_field(
                name="Parameters",
                value=(
                    "• `message_id` *(required)*: Queue position — `0` = next to send\n"
                    "• `field` *(required)*: `content`, `destinations`, `day`, or `time`\n"
                    "• `new_value` *(required)*: New value for the field"
                ),
                inline=False,
            )
            embed.add_field(
                name="Examples",
                value=(
                    '`/mv message_id:0 field:content new_value:"Updated message"`\n'
                    '`/mv message_id:0 field:time new_value:"20:00"`\n'
                    '`/mv message_id:1 field:time new_value:"next Monday 9am"`\n'
                    '`/mv message_id:0 field:day new_value:"25/12"`'
                ),
                inline=False,
            )

        elif command == "history":
            embed = discord.Embed(title="📜 /history — Delivery History", color=discord.Color.blue())
            embed.add_field(
                name="Parameters",
                value="• `limit` *(optional)*: Number of messages to show — default `10`, max `25`",
                inline=False,
            )
            embed.add_field(
                name="Examples",
                value="`/history`\n`/history limit:25`",
                inline=False,
            )

        elif command == "tz":
            embed = discord.Embed(title="🌍 /tz — Timezone Settings", color=discord.Color.blue())
            embed.add_field(
                name="/tz set",
                value=(
                    "Set your personal timezone. All times you provide to `/sch` and `/mv` "
                    "are interpreted in this timezone, and displayed back to you in it.\n"
                    "• `city` *(required)*: Name of a major city in your timezone or a valid tz database name"
                    "Examples: `/tz set city:Lisbon` or `/tz set city:Europe/Lisbon`"
                ),
                inline=False,
            )
            embed.add_field(
                name="/tz get",
                value="Show your current timezone and local time.",
                inline=False,
            )
            embed.add_field(
                name="Examples",
                value="`/tz set timezone:Europe/Lisbon`\n`/tz get`",
                inline=False,
            )

        elif command == "dup":
            embed = discord.Embed(title="📋 /dup — Duplicate a Scheduled Message", color=discord.Color.blue())
            embed.add_field(
                name="Parameters",
                value=(
                    "• `message_id` *(required)*: Queue position to clone — `0` = next to send\n"
                    "• `time` *(required)*: New delivery time (HH:MM or natural language)\n"
                    "• `date` *(optional)*: New delivery date in DD/MM or DD/MM/YYYY"
                ),
                inline=False,
            )
            embed.add_field(
                name="Examples",
                value="`/dup message_id:0 time:18:00`\n`/dup message_id:1 time:\"next Monday 9am\"`",
                inline=False,
            )

        elif command == "pause":
            embed = discord.Embed(title="⏸️ /pause — Pause a Scheduled Message", color=discord.Color.blue())
            embed.add_field(name="Parameters", value="• `message_id` *(required)*: Queue position to pause — `0` = next to send", inline=False)
            embed.add_field(name="Note", value="Paused messages stay in your queue but are skipped by the delivery loop. Use `/resume` to re-activate.", inline=False)
            embed.add_field(name="Example", value="`/pause message_id:2`", inline=False)

        elif command == "resume":
            embed = discord.Embed(title="▶️ /resume — Resume a Paused Message", color=discord.Color.blue())
            embed.add_field(name="Parameters", value="• `message_id` *(required)*: Queue position to resume", inline=False)
            embed.add_field(name="Example", value="`/resume message_id:2`", inline=False)

        elif command == "tpl":
            embed = discord.Embed(title="📁 /tpl — Message Templates", color=discord.Color.blue())
            embed.add_field(
                name="/tpl save",
                value=(
                    "Save a reusable template (content + destinations, no time).\n"
                    "• `name` *(required)*: Template name\n"
                    "• `message` *(required)*: Message content\n"
                    "• `destinations` *(required)*: Space-separated mentions or IDs"
                ),
                inline=False,
            )
            embed.add_field(
                name="/tpl use",
                value=(
                    "Schedule a message from a saved template.\n"
                    "• `name` *(required)*: Template name\n"
                    "• `time` *(required)*: Delivery time (HH:MM or natural language)\n"
                    "• `date` *(optional)*: Delivery date\n"
                    "• `repeat` *(optional)*: Recurrence interval"
                ),
                inline=False,
            )
            embed.add_field(name="/tpl ls", value="List all your saved templates.", inline=False)
            embed.add_field(name="/tpl del", value="Delete a template by name.", inline=False)
            embed.add_field(
                name="/tpl from",
                value=(
                    "Create a template from an existing scheduled message.\n"
                    "• `message_id` *(required)*: Queue position of the source message\n"
                    "• `name` *(required)*: Name for the new template"
                ),
                inline=False,
            )
            embed.add_field(
                name="Examples",
                value=(
                    '`/tpl save name:standup message:"Daily stand-up!" destinations:"#general"`\n'
                    '`/tpl use name:standup time:"tomorrow 9am" repeat:Daily`\n'
                    "`/tpl from message_id:0 name:standup`\n"
                    "`/tpl ls`\n`/tpl del name:standup`"
                ),
                inline=False,
            )

        else:
            # Overview (no command specified)
            embed = discord.Embed(
                title="📅 Scheduler Bot - Help",
                description="Schedule and manage messages to be sent at a later time.\nUse `/help command:<name>` for detailed help on any command.",
                color=discord.Color.blue(),
            )
            embed.add_field(name="/sch",     value="Schedule a message (time, destinations, optional repeat + embed)", inline=False)
            embed.add_field(name="/ls",      value="List pending messages with urgency colours and Edit/Pause/Delete buttons", inline=False)
            embed.add_field(name="/del",     value="Delete a pending message by queue position", inline=False)
            embed.add_field(name="/mv",      value="Update a field of a pending message (content, destinations, time, day)", inline=False)
            embed.add_field(name="/dup",     value="Clone a pending message with a new delivery time", inline=False)
            embed.add_field(name="/pause",   value="Suspend a message without deleting it", inline=False)
            embed.add_field(name="/resume",  value="Re-activate a paused message", inline=False)
            embed.add_field(name="/tpl",     value="Save and reuse message templates (`/tpl save`, `/tpl use`, `/tpl list`, `/tpl delete`)", inline=False)
            embed.add_field(name="/history", value="View previously delivered messages", inline=False)
            embed.add_field(name="/tz",      value="Set or view your personal timezone (`/tz set`, `/tz get`)", inline=False)
            embed.set_footer(text="Scheduler Bot - Discord Application Commands")

        await interaction.followup.send(embed=embed)

    # ======================== /sch Command ========================
    @app_commands.command(name="sch", description="Schedule a message for delivery at a specific time")
    @app_commands.describe(
        message="Message content to send (STRING)",
        destinations="User/channel mentions, space-separated (STRING)",
        time="Delivery time: HH:MM or natural language (e.g. tomorrow 3pm, next Friday, in 2 hours)",
        date="Optional: delivery date in DD/MM or DD/MM/YYYY format (STRING)",
        repeat="Optional: repeat interval for recurring messages",
        attachment="Optional: file to attach to the delivered message",
    )
    @app_commands.choices(repeat=REPEAT_CHOICES)
    async def schedule_message(
        self,
        interaction: discord.Interaction,
        message: str,
        destinations: str,
        time: str,
        date: Optional[str] = None,
        repeat: Optional[app_commands.Choice[str]] = None,
        attachment: Optional[discord.Attachment] = None,
    ) -> None:
        # Validate everything before sending any response
        try:
            validate_message_content(message)
            dests = parse_destinations(destinations)
            user_tz = await self._get_user_tz(str(interaction.user.id))
            expr = f"{date} {time}".strip() if date else time
            hour, minute, day, month, year = parse_time_expression(expr, user_tz)
        except ValidationError as e:
            await interaction.response.send_message(
                embed=discord.Embed(title="❌ Error", description=str(e), color=discord.Color.red()),
                ephemeral=True,
            )
            return
        except Exception as e:
            await interaction.response.send_message(
                embed=discord.Embed(title="❌ Unexpected Error", description=str(e), color=discord.Color.red()),
                ephemeral=True,
            )
            return

        repeat_interval = None if (repeat is None or repeat.value == "none") else repeat.value
        delivery_str = format_delivery_time(day, month, year, hour, minute, user_tz)
        rel_str = get_relative_time_str(day, month, year, hour, minute)
        attachment_url = attachment.url if attachment else None

        # Show preview and wait for confirm/cancel
        preview = discord.Embed(title="📋 Confirm scheduled message", description=message[:1024], color=discord.Color.gold())
        preview.add_field(name="⏰ Delivery", value=f"{delivery_str}\n`{rel_str}`", inline=True)

        # Format destinations with actual usernames
        dest_display = await format_destinations_with_names(self.bot, dests)
        preview.add_field(name="📬 Destinations", value=dest_display, inline=True)

        if repeat_interval:
            preview.add_field(name="🔁 Repeat", value=repeat_interval.capitalize(), inline=True)
        if attachment:
            preview.add_field(name="📎 Attachment", value=attachment.filename, inline=True)
        if user_tz != "UTC":
            preview.add_field(name="🌍 Timezone", value=user_tz, inline=True)
        preview.set_footer(text="You have 60 seconds to confirm or cancel.")

        view = ConfirmScheduleView(str(interaction.user.id))
        await interaction.response.send_message(embed=preview, view=view)
        await view.wait()

        if view.confirmed is None:
            await interaction.edit_original_response(
                embed=discord.Embed(title="⏰ Timed out", description="No response within 60 s — scheduling cancelled.", color=discord.Color.greyple()),
                view=None,
            )
            return

        if not view.confirmed:
            await interaction.edit_original_response(
                embed=discord.Embed(title="❌ Cancelled", description="Message scheduling cancelled.", color=discord.Color.red()),
                view=None,
            )
            return

        try:
            msg = await self.db.create_message(
                user_id=str(interaction.user.id),
                content=message,
                destinations=dests,
                day=day, month=month, year=year,
                hour=hour, minute=minute,
                repeat_interval=repeat_interval,
                attachment_url=attachment_url,
            )
            all_messages = await self.db.get_user_messages(str(interaction.user.id), include_delivered=False)
            position = get_queue_position(all_messages, msg["id"])

            confirmed_embed = discord.Embed(title="✅ Message Scheduled", color=discord.Color.green())
            confirmed_embed.add_field(name="Message ID", value=str(position), inline=True)
            confirmed_embed.add_field(name="Content", value=message[:100], inline=False)
            confirmed_embed.add_field(name="Delivery Time", value=f"{delivery_str}\n`{rel_str}`", inline=True)

            # Show usernames in confirmed message too
            dest_display_confirmed = await format_destinations_with_names(self.bot, dests)
            confirmed_embed.add_field(name="📬 Destinations", value=dest_display_confirmed, inline=True)

            if repeat_interval:
                confirmed_embed.add_field(name="🔁 Repeat", value=repeat_interval.capitalize(), inline=True)
            await interaction.edit_original_response(embed=confirmed_embed, view=None)

        except Exception as e:
            await interaction.edit_original_response(
                embed=discord.Embed(title="❌ Failed to save", description=str(e), color=discord.Color.red()),
                view=None,
            )

    # ======================== /ls Command ========================
    @app_commands.command(name="ls", description="List all your pending scheduled messages")
    async def list_messages(self, interaction: discord.Interaction) -> None:
        """
        List all pending scheduled messages.

        CHAT_INPUT command with no parameters.
        """
        await interaction.response.defer()

        try:
            user_tz = await self._get_user_tz(str(interaction.user.id))
            messages = await self.db.get_user_messages(str(interaction.user.id), include_delivered=False)

            if not messages:
                embed = discord.Embed(
                    title="📅 Your Scheduled Messages",
                    description="You have no pending scheduled messages",
                    color=discord.Color.blue(),
                )
                await interaction.followup.send(embed=embed)
                return

            embed = discord.Embed(
                title=f"📅 Your Pending Scheduled Messages",
                description=f"Total: {len(messages)} message(s). Use buttons or `/mv`, `/pause`, `/del`.",
                color=discord.Color.blue()
            )

            for idx, msg in enumerate(messages):
                d = msg.get("delivery_day")
                mo = msg.get("delivery_month")
                y = msg.get("delivery_year")
                h = msg["delivery_hour"]
                m = msg["delivery_minute"]

                delivery_time = format_delivery_time(d, mo, y, h, m, user_tz)
                rel_str = get_relative_time_str(d, mo, y, h, m)
                color = get_urgency_color(d, mo, y, h, m)
                dot = "🔴" if color == discord.Color.red() else "🟠" if color == discord.Color.orange() else "🟢"

                content_preview = msg["message_content"][:50]
                if len(msg["message_content"]) > 50:
                    content_preview += "..."

                repeat_tag = f"  🔁 {msg['repeat_interval'].capitalize()}" if msg.get("repeat_interval") else ""
                paused_tag = "  ⏸️ Paused" if msg.get("paused") else ""

                # Format destinations with actual usernames
                dest_display = await format_destinations_with_names(self.bot, msg["destinations"], max_names=3)

                field_value = (
                    f"{dot} {delivery_time} — `{rel_str}`{repeat_tag}{paused_tag}\n"
                    f"Content: {content_preview}\n"
                    f"Dest: {dest_display}\n"
                    f"Attachment: {msg.get('attachment_url', '-')}"
                )
                embed.add_field(name=f"[{idx}]", value=field_value, inline=False)

            embed.set_footer(text=f"Legend: 🔴 <1h | 🟠 <24h | 🟢 24h+")
            view = QueueView(messages, self.db, user_tz, str(interaction.user.id))
            await interaction.followup.send(embed=embed, view=view)

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
        self, interaction: discord.Interaction, message_id: str, field: str, new_value: str
    ) -> None:
        """
        Update a pending scheduled message field.

        CHAT_INPUT command with 3 required options:
        - message_id (STRING): Position in queue
        - field (STRING): Which field to update
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


    # ======================== /history Command ========================
    @app_commands.command(name="history", description="View your recently delivered messages")
    @app_commands.describe(limit="Number of messages to show (default 10, max 25)")
    async def history(self, interaction: discord.Interaction, limit: Optional[int] = 10) -> None:
        await interaction.response.defer()
        try:
            limit = max(1, min(limit or 10, 25))
            user_tz = await self._get_user_tz(str(interaction.user.id))
            messages = await self.db.get_delivered_messages(str(interaction.user.id), limit=limit)

            if not messages:
                embed = discord.Embed(title="📜 Delivery History", description="No delivered messages yet.", color=discord.Color.blue())
                await interaction.followup.send(embed=embed)
                return

            embed = discord.Embed(title="📜 Delivery History", description=f"Last {len(messages)} delivered message(s)", color=discord.Color.blue())
            for msg in messages:
                sent_at = msg["delivered_at"]
                sent_str = sent_at.strftime("%Y-%m-%d %H:%M UTC") if sent_at else "unknown"
                preview = msg["message_content"][:80] + ("..." if len(msg["message_content"]) > 80 else "")
                repeat_tag = f" · 🔁 {msg['repeat_interval'].capitalize()}" if msg.get("repeat_interval") else ""

                # Format destinations with usernames
                dest_display = await format_destinations_with_names(self.bot, msg["destinations"], max_names=3)

                field_value = f"**Sent:** {sent_str}{repeat_tag}\n**To:** {dest_display}\n> {preview}"
                embed.add_field(name="\u200b", value=field_value, inline=False)

            embed.set_footer(text=f"Showing {len(messages)} most recent deliveries.")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            embed = discord.Embed(title="❌ Error", description=str(e), color=discord.Color.red())
            await interaction.followup.send(embed=embed)

    # ======================== /tz Commands ========================
    tz_group = app_commands.Group(name="tz", description="Manage your personal timezone")

    @tz_group.command(name="set", description="Set your timezone by city name or IANA timezone")
    @app_commands.describe(city="City name (e.g., Tokyo, London, New York) or IANA timezone name")
    async def tz_set(self, interaction: discord.Interaction, city: str) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            # Resolve timezone from either city name or IANA name
            resolved_tz = resolve_timezone(city)
            await self.db.set_user_timezone(str(interaction.user.id), resolved_tz)
            from datetime import datetime as _dt
            from zoneinfo import ZoneInfo

            sample = _dt.now(ZoneInfo(resolved_tz)).strftime("%H:%M on %A, %d %b %Y")
            embed = discord.Embed(
                title="🌍 Timezone Updated",
                description=f"Your timezone is now **{resolved_tz}**.\nYour local time: `{sample}`\n\nAll future `/sch` times will be interpreted in this timezone.",
                color=discord.Color.green(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except ValidationError as e:
            embed = discord.Embed(title="❌ Error", description=str(e), color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)

    @tz_group.command(name="get", description="Show your current timezone setting")
    async def tz_get(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        record = await self.db.get_user_timezone(str(interaction.user.id))
        if record:
            from zoneinfo import ZoneInfo
            from datetime import datetime as _dt
            tz_name = record["timezone"]
            sample = _dt.now(ZoneInfo(tz_name)).strftime("%H:%M on %A, %d %b %Y")
            embed = discord.Embed(title="🌍 Your Timezone", description=f"**{tz_name}**\nLocal time: `{sample}`", color=discord.Color.blue())
        else:
            embed = discord.Embed(title="🌍 No Timezone Set", description="You are using **UTC** (default).\nRun `/tz set <timezone>` to change it.", color=discord.Color.blue())
        await interaction.followup.send(embed=embed, ephemeral=True)


    # ======================== /dup Command ========================
    @app_commands.command(name="dup", description="Clone a pending message with a new delivery time")
    @app_commands.describe(
        message_id="Queue position to clone (0 = next to send)",
        time="New delivery time: HH:MM or natural language",
        date="Optional: new delivery date in DD/MM or DD/MM/YYYY",
    )
    async def dup_message(self, interaction: discord.Interaction, message_id: str, time: str, date: Optional[str] = None) -> None:
        await interaction.response.defer()
        try:
            messages = await self.db.get_user_messages(str(interaction.user.id), include_delivered=False)
            try:
                pos = int(message_id)
                if not 0 <= pos < len(messages):
                    raise ValidationError(f"Position {pos} out of range (0–{len(messages) - 1}).")
                source = messages[pos]
            except ValueError:
                source = await self.db.get_message(message_id, str(interaction.user.id))
                if not source:
                    raise ValidationError("Message not found.")

            user_tz = await self._get_user_tz(str(interaction.user.id))
            expr = f"{date} {time}".strip() if date else time
            h, m, d, mo, y = parse_time_expression(expr, user_tz)

            new_msg = await self.db.create_message(
                user_id=str(interaction.user.id),
                content=source["message_content"],
                destinations=source["destinations"],
                day=d, month=mo, year=y,
                hour=h, minute=m,
                repeat_interval=source.get("repeat_interval"),
                embed_data=source.get("embed_data"),
            )
            all_messages = await self.db.get_user_messages(str(interaction.user.id), include_delivered=False)
            new_pos = get_queue_position(all_messages, new_msg["id"])
            delivery_str = format_delivery_time(d, mo, y, h, m, user_tz)

            embed = discord.Embed(title="📋 Message Duplicated", color=discord.Color.green())
            embed.add_field(name="Cloned from", value=f"#{pos if message_id.isdigit() else 'ID'}", inline=True)
            embed.add_field(name="New position", value=f"#{new_pos}", inline=True)
            embed.add_field(name="Delivery time", value=f"{delivery_str}\n`{get_relative_time_str(d, mo, y, h, m)}`", inline=False)
            embed.add_field(name="Content", value=source["message_content"][:100], inline=False)
            await interaction.followup.send(embed=embed)

        except ValidationError as e:
            await interaction.followup.send(embed=discord.Embed(title="❌ Error", description=str(e), color=discord.Color.red()))

    # ======================== /pause Command ========================
    @app_commands.command(name="pause", description="Pause a pending message without deleting it")
    @app_commands.describe(message_id="Queue position to pause (0 = next to send)")
    async def pause_message(self, interaction: discord.Interaction, message_id: str) -> None:
        await interaction.response.defer()
        try:
            messages = await self.db.get_user_messages(str(interaction.user.id), include_delivered=False)
            try:
                pos = int(message_id)
                if not 0 <= pos < len(messages):
                    raise ValidationError(f"Position {pos} out of range (0–{len(messages) - 1}).")
                actual_id = messages[pos]["id"]
            except ValueError:
                actual_id = message_id

            result = await self.db.pause_message(actual_id, str(interaction.user.id))
            if not result:
                raise ValidationError("Message not found.")

            embed = discord.Embed(title="⏸️ Message Paused", description=f"Message **#{message_id}** will be skipped until resumed.", color=discord.Color.orange())
            await interaction.followup.send(embed=embed)

        except ValidationError as e:
            await interaction.followup.send(embed=discord.Embed(title="❌ Error", description=str(e), color=discord.Color.red()))

    # ======================== /resume Command ========================
    @app_commands.command(name="resume", description="Resume a paused scheduled message")
    @app_commands.describe(message_id="Queue position to resume")
    async def resume_message(self, interaction: discord.Interaction, message_id: str) -> None:
        await interaction.response.defer()
        try:
            messages = await self.db.get_user_messages(str(interaction.user.id), include_delivered=False)
            try:
                pos = int(message_id)
                if not 0 <= pos < len(messages):
                    raise ValidationError(f"Position {pos} out of range (0–{len(messages) - 1}).")
                actual_id = messages[pos]["id"]
            except ValueError:
                actual_id = message_id

            result = await self.db.resume_message(actual_id, str(interaction.user.id))
            if not result:
                raise ValidationError("Message not found.")

            embed = discord.Embed(title="▶️ Message Resumed", description=f"Message **#{message_id}** is active again.", color=discord.Color.green())
            await interaction.followup.send(embed=embed)

        except ValidationError as e:
            await interaction.followup.send(embed=discord.Embed(title="❌ Error", description=str(e), color=discord.Color.red()))

    # ======================== /tpl Commands ========================
    tpl_group = app_commands.Group(name="tpl", description="Save and reuse message templates")

    @tpl_group.command(name="save", description="Save a reusable message template")
    @app_commands.describe(
        name="Template name (no spaces)",
        message="Message content",
        destinations="Space-separated user/channel mentions or IDs",
    )
    async def tpl_save(self, interaction: discord.Interaction, name: str, message: str, destinations: str) -> None:
        await interaction.response.defer()
        try:
            validate_message_content(message)
            dests = parse_destinations(destinations)
            await self.db.save_template(str(interaction.user.id), name, message, dests)
            embed = discord.Embed(title="📁 Template Saved", color=discord.Color.green())
            embed.add_field(name="Name", value=f"`{name}`", inline=True)
            embed.add_field(name="Destinations", value=f"{len(dests)} recipient(s)", inline=True)
            embed.add_field(name="Content", value=message[:100], inline=False)
            embed.set_footer(text=f"Use /tpl use name:{name} time:<time> to schedule it.")
            await interaction.followup.send(embed=embed)
        except ValidationError as e:
            await interaction.followup.send(embed=discord.Embed(title="❌ Error", description=str(e), color=discord.Color.red()))

    @tpl_group.command(name="use", description="Schedule a message from a saved template")
    @app_commands.describe(
        name="Template name",
        time="Delivery time: HH:MM or natural language",
        date="Optional: delivery date in DD/MM or DD/MM/YYYY",
        repeat="Optional: repeat interval",
    )
    @app_commands.choices(repeat=REPEAT_CHOICES)
    async def tpl_use(self, interaction: discord.Interaction, name: str, time: str, date: Optional[str] = None, repeat: Optional[app_commands.Choice[str]] = None) -> None:
        try:
            tpl = await self.db.get_template(str(interaction.user.id), name)
            if not tpl:
                await interaction.response.send_message(
                    embed=discord.Embed(title="❌ Error", description=f"No template named `{name}`. Use `/tpl list` to see your templates.", color=discord.Color.red()),
                    ephemeral=True,
                )
                return

            user_tz = await self._get_user_tz(str(interaction.user.id))
            expr = f"{date} {time}".strip() if date else time
            h, m, d, mo, y = parse_time_expression(expr, user_tz)
        except ValidationError as e:
            await interaction.response.send_message(
                embed=discord.Embed(title="❌ Error", description=str(e), color=discord.Color.red()), ephemeral=True
            )
            return

        repeat_interval = None if (repeat is None or repeat.value == "none") else repeat.value
        delivery_str = format_delivery_time(d, mo, y, h, m, user_tz)
        rel_str = get_relative_time_str(d, mo, y, h, m)

        preview = discord.Embed(title=f"📁 Confirm template: `{name}`", description=tpl["message_content"][:1024], color=discord.Color.gold())
        preview.add_field(name="⏰ Delivery", value=f"{delivery_str}\n`{rel_str}`", inline=True)
        preview.add_field(name="📬 Destinations", value=f"{len(tpl['destinations'])} recipient(s)", inline=True)
        if repeat_interval:
            preview.add_field(name="🔁 Repeat", value=repeat_interval.capitalize(), inline=True)
        preview.set_footer(text="You have 60 seconds to confirm or cancel.")

        view = ConfirmScheduleView(str(interaction.user.id))
        await interaction.response.send_message(embed=preview, view=view)
        await view.wait()

        if not view.confirmed:
            label = "⏰ Timed out" if view.confirmed is None else "❌ Cancelled"
            desc = "No response within 60 s — scheduling cancelled." if view.confirmed is None else "Scheduling cancelled."
            await interaction.edit_original_response(
                embed=discord.Embed(title=label, description=desc, color=discord.Color.greyple()), view=None
            )
            return

        try:
            msg = await self.db.create_message(
                user_id=str(interaction.user.id),
                content=tpl["message_content"],
                destinations=tpl["destinations"],
                day=d, month=mo, year=y,
                hour=h, minute=m,
                repeat_interval=repeat_interval,
            )
            all_messages = await self.db.get_user_messages(str(interaction.user.id), include_delivered=False)
            position = get_queue_position(all_messages, msg["id"])

            confirmed = discord.Embed(title="✅ Scheduled from Template", color=discord.Color.green())
            confirmed.add_field(name="Template", value=f"`{name}`", inline=True)
            confirmed.add_field(name="Queue position", value=f"#{position}", inline=True)
            confirmed.add_field(name="⏰ Delivery", value=f"{delivery_str}\n`{rel_str}`", inline=False)
            if repeat_interval:
                confirmed.add_field(name="🔁 Repeat", value=repeat_interval.capitalize(), inline=True)
            await interaction.edit_original_response(embed=confirmed, view=None)

        except Exception as e:
            await interaction.edit_original_response(
                embed=discord.Embed(title="❌ Failed to save", description=str(e), color=discord.Color.red()), view=None
            )

    @tpl_group.command(name="ls", description="List all your saved templates")
    async def tpl_ls(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        templates = await self.db.list_templates(str(interaction.user.id))
        if not templates:
            await interaction.followup.send(embed=discord.Embed(title="📁 Templates", description="You have no saved templates. Use `/tpl save` to create one.", color=discord.Color.blue()))
            return
        embed = discord.Embed(title="📁 Your Templates", description=f"{len(templates)} saved template(s)", color=discord.Color.blue())
        for tpl in templates:
            preview = tpl["message_content"][:60] + ("..." if len(tpl["message_content"]) > 60 else "")

            # Format destinations with usernames
            dest_display = await format_destinations_with_names(self.bot, tpl["destinations"], max_names=3)

            embed.add_field(name=f"`{tpl['name']}`", value=f"Dest: {dest_display}\n> {preview}", inline=False)
        embed.set_footer(text="Use /tpl use name:<name> time:<time> to schedule a template.")
        await interaction.followup.send(embed=embed)

    @tpl_group.command(name="del", description="Delete a saved template")
    @app_commands.describe(name="Template name to delete")
    async def tpl_del(self, interaction: discord.Interaction, name: str) -> None:
        await interaction.response.defer()
        deleted = await self.db.delete_template(str(interaction.user.id), name)
        if deleted:
            await interaction.followup.send(embed=discord.Embed(title="🗑️ Template Deleted", description=f"Template `{name}` removed.", color=discord.Color.green()))
        else:
            await interaction.followup.send(embed=discord.Embed(title="❌ Not Found", description=f"No template named `{name}`.", color=discord.Color.red()))

    @tpl_group.command(name="from", description="Create a template from an existing scheduled message")
    @app_commands.describe(
        message_id="Queue position of the source message (0 = next to send)",
        name="Name for the new template",
    )
    async def tpl_from(self, interaction: discord.Interaction, message_id: str, name: str) -> None:
        await interaction.response.defer()
        try:
            messages = await self.db.get_user_messages(str(interaction.user.id), include_delivered=False)
            try:
                pos = int(message_id)
                if not 0 <= pos < len(messages):
                    raise ValidationError(f"Position {pos} out of range (0-{len(messages) - 1}).")
                source = messages[pos]
            except ValueError:
                source = await self.db.get_message(message_id, str(interaction.user.id))
                if not source:
                    raise ValidationError("Message not found.")

            await self.db.save_template(
                str(interaction.user.id), name, source["message_content"], source["destinations"]
            )

            dest_display = await format_destinations_with_names(self.bot, source["destinations"])
            embed = discord.Embed(title="📁 Template Created", color=discord.Color.green())
            embed.add_field(name="Name", value=f"`{name}`", inline=True)
            embed.add_field(name="Source", value=f"Message #{message_id}", inline=True)
            embed.add_field(name="Destinations", value=dest_display, inline=True)
            embed.add_field(name="Content", value=source["message_content"][:100], inline=False)
            embed.set_footer(text=f"Use /tpl use name:{name} time:<time> to schedule it.")
            await interaction.followup.send(embed=embed)

        except ValidationError as e:
            await interaction.followup.send(embed=discord.Embed(title="❌ Error", description=str(e), color=discord.Color.red()))


async def setup(bot: commands.Bot) -> None:
    """Load the SchedulerCommands cog"""
    cog = SchedulerCommands(bot, bot.db)
    await bot.add_cog(cog)
    bot.tree.add_command(cog.tz_group)
    bot.tree.add_command(cog.tpl_group)
