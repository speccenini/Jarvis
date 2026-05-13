"""
User Authorization Module
Handles user authentication and permission checks.
"""

import logging
from typing import List

logger = logging.getLogger(__name__)


class UserAuthenticator:
    """Manages user authorization for Jarvis."""

    def __init__(self, authorized_ids: List[int]):
        """
        Initialize authenticator with list of authorized user IDs.

        Args:
            authorized_ids: List of Telegram user IDs that are allowed to use Jarvis
        """
        self.authorized_ids = set(authorized_ids)
        logger.info(f"UserAuthenticator initialized with {len(self.authorized_ids)} authorized user(s)")

    def is_authorized(self, user_id: int) -> bool:
        """
        Check if a user is authorized to use Jarvis.

        Args:
            user_id: Telegram user ID

        Returns:
            True if user is authorized, False otherwise
        """
        return user_id in self.authorized_ids

    def add_authorized_user(self, user_id: int):
        """Add a user to the authorized list."""
        self.authorized_ids.add(user_id)
        logger.info(f"Added authorized user: {user_id}")

    def remove_authorized_user(self, user_id: int):
        """Remove a user from the authorized list."""
        if user_id in self.authorized_ids:
            self.authorized_ids.discard(user_id)
            logger.info(f"Removed authorized user: {user_id}")

    def list_authorized_users(self) -> List[int]:
        """Get list of all authorized user IDs."""
        return sorted(list(self.authorized_ids))
