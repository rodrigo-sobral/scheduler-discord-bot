"""
Message Delivery Service
Handles sending scheduled messages to Discord users and channels
"""

import logging
from typing import List, Dict, Optional
import discord
from discord.ext import commands
from .utils import compute_next_recurrence

logger = logging.getLogger(__name__)


class MessageDeliveryService:
    """Service for delivering scheduled messages to Discord"""

    def __init__(self, bot: commands.Bot, db=None):
        self.bot = bot
        self.db = db

    async def deliver_message(self, message: Dict) -> tuple[bool, Optional[str]]:
        """
        Deliver a scheduled message to its destinations and notify the creator

        Args:
            message: Message dict with all scheduled message data

        Returns:
            Tuple of (success: bool, failure_reason: Optional[str])
            - If success is True, failure_reason is None
            - If success is False, failure_reason explains what went wrong
        """
        try:
            destinations = message.get("destinations", [])
            content = message.get("message_content", "")
            creator_id = message.get("user_id")
            message_id = message.get("id")

            if not destinations:
                return False, "No destinations configured"

            if not content:
                return False, "Message content is empty"

            # Track delivery status
            failed_destinations = []
            successful_destinations = []

            # Send to each destination
            for dest_id in destinations:
                success = await self._send_to_destination(dest_id, content, creator_id)

                if success:
                    successful_destinations.append(dest_id)
                else:
                    failed_destinations.append(dest_id)

            # Send confirmation to creator
            if creator_id:
                await self._send_confirmation_to_creator(
                    creator_id, content, successful_destinations, failed_destinations, message_id
                )

            # Reschedule recurring messages on at least partial success
            if successful_destinations and message.get("repeat_interval") and self.db:
                await self._reschedule_recurring(message)

            # Determine overall success
            if len(successful_destinations) == 0:
                failure_reason = f"Failed to deliver to all {len(destinations)} destination(s)"
                return False, failure_reason
            elif len(failed_destinations) > 0:
                failure_reason = f"Partial delivery: {len(successful_destinations)}/{len(destinations)} succeeded"
                logger.warning(f"Message {message_id} {failure_reason}")
                # Consider partial delivery as success
                return True, None
            else:
                return True, None

        except Exception as e:
            error_msg = f"Delivery error: {str(e)}"
            logger.error(f"Message {message.get('id')}: {error_msg}", exc_info=e)
            return False, error_msg

    async def _send_to_destination(self, dest_id: str, content: str, creator_id: str) -> bool:
        """
        Send a message to a single destination (user or channel)

        Args:
            dest_id: Discord user or channel ID
            content: Message content
            creator_id: ID of the user who created the message

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Try to get user first
            try:
                user = await self.bot.fetch_user(int(dest_id))
                await self._send_message(user, content, creator_id, is_dm=True)
                logger.info(f"Message delivered to user {dest_id}")
                return True
            except (discord.NotFound, discord.Forbidden, ValueError):
                # If not a user, try as a channel
                try:
                    channel = self.bot.get_channel(int(dest_id))
                    if channel is None:
                        channel = await self.bot.fetch_channel(int(dest_id))

                    if channel is None:
                        logger.warning(f"Channel {dest_id} not found")
                        return False

                    await self._send_message(channel, content, creator_id, is_dm=False)
                    logger.info(f"Message delivered to channel {dest_id}")
                    return True
                except (discord.NotFound, discord.Forbidden, ValueError):
                    logger.warning(f"Could not find user or channel {dest_id}")
                    return False

        except discord.Forbidden:
            logger.warning(f"No permission to send message to {dest_id}")
            return False
        except discord.HTTPException as e:
            logger.warning(f"HTTP error sending to {dest_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending to {dest_id}: {e}", exc_info=e)
            return False

    async def _send_message(
        self, destination, content: str, creator_id: Optional[str] = None, is_dm: bool = False
    ) -> None:
        """
        Send a message to a user or channel with creator mention

        Args:
            destination: Discord user or channel object
            content: Message content
            creator_id: ID of the message creator (for mentioning)
            is_dm: Whether this is a DM to avoid mentioning in channels

        Raises:
            discord.Forbidden: If no permission to send
            discord.HTTPException: If sending failed
        """
        # Build the message with creator mention
        creator_mention = "A user"
        if creator_id:
            try:
                # Try to fetch the creator to get their actual username
                creator_user = await self.bot.fetch_user(int(creator_id))
                # Use mention format for proper tagging: <@userid>
                creator_mention = creator_user.mention
            except (discord.NotFound, discord.HTTPException, ValueError):
                # Fallback to mention format if fetch fails
                creator_mention = f"<@{creator_id}>"

        # Create embed with creator mention
        embed = discord.Embed(
            title=f"📨 Message from {creator_mention}", description=content, color=discord.Color.blurple()
        )

        # Send the message
        if isinstance(destination, discord.TextChannel):
            await destination.send(embed=embed)
        elif isinstance(destination, discord.User) or isinstance(destination, discord.Member):
            await destination.send(embed=embed)
        else:
            # Fallback for any other sendable type
            await destination.send(embed=embed)

    async def _send_confirmation_to_creator(
        self, creator_id: str, content: str, successful_dests: List[str], failed_dests: List[str], message_id: str
    ) -> None:
        """
        Send a confirmation message to the creator of the scheduled message

        Args:
            creator_id: ID of the message creator
            content: Original message content
            successful_dests: List of destination IDs where delivery succeeded
            failed_dests: List of destination IDs where delivery failed
            message_id: ID of the scheduled message
        """
        try:
            creator = await self.bot.fetch_user(int(creator_id))

            # Build confirmation embed
            embed = discord.Embed(
                title="✅ Message Delivery Confirmation",
                description="Your scheduled message has been delivered!",
                color=discord.Color.green(),
            )

            # Add original message preview
            embed.add_field(
                name="Your Message", value=content[:256] + ("..." if len(content) > 256 else ""), inline=False
            )

            # Add delivery status
            total_destinations = len(successful_dests) + len(failed_dests)
            embed.add_field(
                name="Delivery Status",
                value=f"✅ **Delivered to {len(successful_dests)}/{total_destinations} destination(s)**",
                inline=False,
            )

            # Add successful deliveries with user mentions
            if successful_dests:
                success_mentions = []
                for dest_id in successful_dests:
                    try:
                        user = await self.bot.fetch_user(int(dest_id))
                        success_mentions.append(f"• {user.mention}")
                    except (discord.NotFound, discord.HTTPException, ValueError):
                        # Fallback to ID if user not found
                        success_mentions.append(f"• <@{dest_id}>")

                success_list = "\n".join(success_mentions)
                embed.add_field(name="✅ Successful Deliveries", value=success_list, inline=False)

            # Add failed deliveries if any with user mentions
            if failed_dests:
                failed_mentions = []
                for dest_id in failed_dests:
                    try:
                        user = await self.bot.fetch_user(int(dest_id))
                        failed_mentions.append(f"• {user.mention}")
                    except (discord.NotFound, discord.HTTPException, ValueError):
                        # Fallback to ID if user not found
                        failed_mentions.append(f"• <@{dest_id}>")

                failed_list = "\n".join(failed_mentions)
                embed.add_field(name="❌ Failed Deliveries", value=failed_list, inline=False)

            embed.set_footer(text=f"Message ID: {message_id}")

            await creator.send(embed=embed)
            logger.info(f"Delivery confirmation sent to creator {creator_id}")

        except Exception as e:
            logger.warning(f"Could not send confirmation to creator {creator_id}: {e}")

    async def _reschedule_recurring(self, message: Dict) -> None:
        """Create the next occurrence of a recurring message."""
        next_time = compute_next_recurrence(message)
        if next_time is None:
            return
        h, m, d, mo, y = next_time
        try:
            await self.db.create_message(
                user_id=message["user_id"],
                content=message["message_content"],
                destinations=message["destinations"],
                day=d, month=mo, year=y,
                hour=h, minute=m,
                repeat_interval=message["repeat_interval"],
            )
            logger.info(f"Recurring message {message['id']} rescheduled for {y:04d}-{mo:02d}-{d:02d} {h:02d}:{m:02d}")
        except Exception as e:
            logger.error(f"Failed to reschedule message {message['id']}: {e}")
