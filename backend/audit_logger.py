"""
Audit Logger Module
Logs all actions for security and debugging purposes.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class AuditLogger:
    """Logs all Jarvis actions for audit trail."""

    def __init__(self, log_dir: Path):
        """
        Initialize the audit logger.

        Args:
            log_dir: Directory where audit logs will be stored
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create separate log files
        self.audit_file = self.log_dir / "audit.log"
        self.error_file = self.log_dir / "errors.log"
        self.unauthorized_file = self.log_dir / "unauthorized.log"

        logger.info(f"AuditLogger initialized. Log directory: {self.log_dir}")

    def _write_log(self, log_file: Path, entry: Dict[str, Any]):
        """Write a log entry to a file."""
        try:
            with open(log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to write to {log_file}: {e}")

    def log_action(
        self,
        user_id: int,
        username: str,
        action: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Log a user action.

        Args:
            user_id: Telegram user ID
            username: Telegram username
            action: Action name (e.g., "tool_codex", "command_start")
            details: Additional details about the action
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "username": username,
            "action": action,
            "details": details or {},
        }
        self._write_log(self.audit_file, entry)
        logger.debug(f"Action logged: {action} by user {user_id}")

    def log_unauthorized_access(self, user_id: int, username: str, attempted_action: str):
        """
        Log unauthorized access attempts.

        Args:
            user_id: Telegram user ID
            username: Telegram username
            attempted_action: What the user tried to do
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "username": username,
            "attempted_action": attempted_action,
        }
        self._write_log(self.unauthorized_file, entry)
        logger.warning(f"Unauthorized access attempt by user {user_id}: {attempted_action}")

    def log_error(self, user_id: int, action: str, error: str, details: Optional[Dict[str, Any]] = None):
        """
        Log an error during tool execution.

        Args:
            user_id: Telegram user ID
            action: Action that failed
            error: Error message
            details: Additional error details
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "action": action,
            "error": error,
            "details": details or {},
        }
        self._write_log(self.error_file, entry)
        logger.error(f"Error in {action} for user {user_id}: {error}")

    def get_user_action_history(self, user_id: int, limit: int = 50) -> list:
        """
        Get action history for a specific user.

        Args:
            user_id: Telegram user ID
            limit: Maximum number of recent actions to return

        Returns:
            List of action entries
        """
        history = []
        try:
            with open(self.audit_file, "r") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        if entry.get("user_id") == user_id:
                            history.append(entry)
                    except json.JSONDecodeError:
                        pass
        except FileNotFoundError:
            pass

        return history[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        """Get overall statistics from the audit logs."""
        total_actions = 0
        total_unauthorized = 0
        total_errors = 0
        unique_users = set()

        try:
            with open(self.audit_file, "r") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        total_actions += 1
                        unique_users.add(entry.get("user_id"))
                    except json.JSONDecodeError:
                        pass

            with open(self.unauthorized_file, "r") as f:
                total_unauthorized = sum(1 for _ in f)

            with open(self.error_file, "r") as f:
                total_errors = sum(1 for _ in f)
        except FileNotFoundError:
            pass

        return {
            "total_actions": total_actions,
            "unique_users": len(unique_users),
            "unauthorized_attempts": total_unauthorized,
            "errors": total_errors,
        }
