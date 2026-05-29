"""
Database manager for Scheduler Bot
Handles all database operations with Prisma
"""

import os
import subprocess
from typing import List, Optional, Dict
from datetime import datetime
from pathlib import Path
from prisma import Prisma
from .utils import serialize_destinations, deserialize_destinations


class DatabaseManager:
    """Manages all database operations"""

    def __init__(self):
        # Set DATABASE_URL for Prisma 7 if not already set
        if "DATABASE_URL" not in os.environ:
            # Get the path to the database file relative to the project root
            db_path = Path(__file__).parent.parent.parent / "db" / "database.db"
            os.environ["DATABASE_URL"] = f"file:{db_path.absolute()}"

        # Initialize Prisma client
        self.client = Prisma()
        self._initialized = False

    async def _initialize_database(self):
        """Initialize database schema if not already done"""
        if self._initialized:
            return

        try:
            # Get the project root and schema path
            project_root = Path(__file__).parent.parent
            schema_path = project_root / "prisma" / "schema.prisma"
            db_path = Path(os.getenv("DATABASE_URL").replace("file:", ""))

            # Ensure db directory exists
            db_path.parent.mkdir(parents=True, exist_ok=True)

            # Always push schema to ensure new tables/columns are created
            result = subprocess.run(
                    ["python", "-m", "prisma", "db", "push", "--skip-generate", "--accept-data-loss", "--schema", str(schema_path)],
                    cwd=str(project_root),
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

            if result.returncode != 0:
                raise RuntimeError(f"Prisma db push failed: {result.stderr}")

            self._initialized = True
        except subprocess.TimeoutExpired:
            raise RuntimeError("Prisma initialization timed out")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize database: {e}")

    async def connect(self):
        """Connect to the database"""
        # Initialize database schema first if needed
        await self._initialize_database()
        # Now connect the Prisma client
        await self.client.connect()

    async def disconnect(self):
        """Disconnect from the database"""
        await self.client.disconnect()

    async def create_message(
        self,
        user_id: str,
        content: str,
        destinations: List[str],
        day: Optional[int],
        month: Optional[int],
        year: Optional[int],
        hour: int,
        minute: int,
        repeat_interval: Optional[str] = None,
    ) -> Dict:
        """
        Create a new scheduled message

        Args:
            user_id: Discord user ID
            content: Message content
            destinations: List of destination IDs
            day, month, year: Delivery date (optional)
            hour, minute: Delivery time

        Returns:
            Created message dict
        """
        message = await self.client.scheduledmessage.create(
            data={
                "user_id": str(user_id),
                "message_content": content,
                "destinations": serialize_destinations(destinations),
                "delivery_day": day,
                "delivery_month": month,
                "delivery_year": year,
                "delivery_hour": hour,
                "delivery_minute": minute,
                "repeat_interval": repeat_interval,
                "delivered_at": None,
                "failed": False,
            }
        )

        return self._format_message(message)

    async def get_user_messages(self, user_id: str, include_delivered: bool = False) -> List[Dict]:
        """
        Get all messages for a user, sorted by delivery time

        Args:
            user_id: Discord user ID
            include_delivered: If False, only returns pending messages

        Returns:
            List of messages sorted by delivery time
        """
        where_clause = {"user_id": str(user_id)}

        if not include_delivered:
            where_clause["delivered_at"] = None

        messages = await self.client.scheduledmessage.find_many(where=where_clause)

        # Sort by delivery time
        formatted = [self._format_message(m) for m in messages]
        formatted.sort(
            key=lambda x: (
                x.get("delivery_year") or datetime.now().year,
                x.get("delivery_month") or datetime.now().month,
                x.get("delivery_day") or datetime.now().day,
                x["delivery_hour"],
                x["delivery_minute"],
            )
        )

        return formatted

    async def get_message(self, message_id: str, user_id: str) -> Optional[Dict]:
        """
        Get a specific message

        Args:
            message_id: Message ID
            user_id: Discord user ID (for security)

        Returns:
            Message dict or None if not found
        """
        message = await self.client.scheduledmessage.find_first(where={"id": message_id, "user_id": str(user_id)})

        return self._format_message(message) if message else None

    async def get_pending_messages(self) -> List[Dict]:
        """
        Get all pending messages that haven't been delivered

        Args:

        Returns:
            List of undelivered messages
        """
        messages = await self.client.scheduledmessage.find_many(where={"delivered_at": None, "failed": False})

        formatted = [self._format_message(m) for m in messages]

        # Sort by delivery time for processing order
        formatted.sort(
            key=lambda x: (
                x.get("delivery_year") or datetime.now().year,
                x.get("delivery_month") or datetime.now().month,
                x.get("delivery_day") or datetime.now().day,
                x["delivery_hour"],
                x["delivery_minute"],
            )
        )

        return formatted

    async def update_message(self, message_id: str, user_id: str, **kwargs) -> Optional[Dict]:
        """
        Update a scheduled message

        Args:
            message_id: Message ID
            user_id: Discord user ID (for security)
            **kwargs: Fields to update

        Returns:
            Updated message dict or None if not found
        """
        # Verify ownership
        message = await self.get_message(message_id, user_id)
        if not message:
            return None

        # Prepare update data
        update_data = {}
        if "message_content" in kwargs:
            update_data["message_content"] = kwargs["message_content"]
        if "destinations" in kwargs:
            update_data["destinations"] = serialize_destinations(kwargs["destinations"])
        if "delivery_day" in kwargs:
            update_data["delivery_day"] = kwargs["delivery_day"]
        if "delivery_month" in kwargs:
            update_data["delivery_month"] = kwargs["delivery_month"]
        if "delivery_year" in kwargs:
            update_data["delivery_year"] = kwargs["delivery_year"]
        if "delivery_hour" in kwargs:
            update_data["delivery_hour"] = kwargs["delivery_hour"]
        if "delivery_minute" in kwargs:
            update_data["delivery_minute"] = kwargs["delivery_minute"]

        if not update_data:
            return message

        updated = await self.client.scheduledmessage.update(where={"id": message_id}, data=update_data)

        return self._format_message(updated)

    async def mark_delivered(self, message_id: str, success: bool = True, failure_reason: str = None) -> Optional[Dict]:
        """
        Mark a message as delivered or failed

        Args:
            message_id: Message ID
            success: True if successfully delivered, False if failed
            failure_reason: Reason for failure if applicable

        Returns:
            Updated message dict
        """
        update_data = {
            "delivered_at": datetime.now() if success else None,
            "failed": not success,
            "failure_reason": failure_reason if not success else None,
        }

        updated = await self.client.scheduledmessage.update(where={"id": message_id}, data=update_data)

        return self._format_message(updated)

    async def delete_message(self, message_id: str, user_id: str) -> bool:
        """
        Delete a scheduled message

        Args:
            message_id: Message ID
            user_id: Discord user ID (for security)

        Returns:
            True if deleted, False if not found
        """
        # Verify ownership
        message = await self.get_message(message_id, user_id)
        if not message:
            return False

        await self.client.scheduledmessage.delete(where={"id": message_id})
        return True

    def _format_message(self, message) -> Dict:
        """Format a Prisma message object to dict"""
        if message is None:
            return None

        return {
            "id": message.id,
            "user_id": message.user_id,
            "message_content": message.message_content,
            "destinations": deserialize_destinations(message.destinations),
            "delivery_day": message.delivery_day,
            "delivery_month": message.delivery_month,
            "delivery_year": message.delivery_year,
            "delivery_hour": message.delivery_hour,
            "delivery_minute": message.delivery_minute,
            "repeat_interval": message.repeat_interval,
            "created_at": message.created_at,
            "updated_at": message.updated_at,
            "delivered_at": message.delivered_at,
            "failed": message.failed,
            "failure_reason": message.failure_reason,
        }

    async def get_delivered_messages(self, user_id: str, limit: int = 10) -> List[Dict]:
        """Get the most recently delivered messages for a user."""
        messages = await self.client.scheduledmessage.find_many(
            where={"user_id": str(user_id), "delivered_at": {"not": None}},
            order={"delivered_at": "desc"},
            take=limit,
        )
        return [self._format_message(m) for m in messages]

    async def get_user_timezone(self, user_id: str) -> Optional[Dict]:
        """Get the stored timezone for a user, or None if not set."""
        record = await self.client.usertimezone.find_unique(where={"user_id": str(user_id)})
        return {"user_id": record.user_id, "timezone": record.timezone} if record else None

    async def set_user_timezone(self, user_id: str, timezone: str) -> Dict:
        """Create or update the timezone for a user."""
        record = await self.client.usertimezone.upsert(
            where={"user_id": str(user_id)},
            data={
                "create": {"user_id": str(user_id), "timezone": timezone},
                "update": {"timezone": timezone},
            },
        )
        return {"user_id": record.user_id, "timezone": record.timezone}
