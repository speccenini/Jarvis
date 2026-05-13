"""
Configuration Module
Central place for all Jarvis configuration settings.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Jarvis configuration."""

    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    AUTHORIZED_TELEGRAM_USER_ID = int(os.getenv("AUTHORIZED_TELEGRAM_USER_ID", "0"))

    # Workspace
    JARVIS_WORKSPACE = Path(os.getenv("JARVIS_WORKSPACE", "~/JarvisWorkspace")).expanduser()

    # Codex
    CODEX_TIMEOUT_SECONDS = int(os.getenv("CODEX_TIMEOUT_SECONDS", "180"))

    # Logging
    LOG_DIR = JARVIS_WORKSPACE / "logs"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # Tool defaults
    TOOL_TIMEOUT_DEFAULT = 30  # seconds
    TOOL_MAX_OUTPUT_LENGTH = 4000  # characters

    @classmethod
    def validate(cls):
        """Validate critical configuration values."""
        errors = []

        if not cls.TELEGRAM_BOT_TOKEN:
            errors.append("Missing TELEGRAM_BOT_TOKEN")

        if cls.AUTHORIZED_TELEGRAM_USER_ID == 0:
            errors.append("Missing or invalid AUTHORIZED_TELEGRAM_USER_ID")

        if not cls.JARVIS_WORKSPACE.exists():
            errors.append(f"JARVIS_WORKSPACE does not exist: {cls.JARVIS_WORKSPACE}")

        if errors:
            raise ValueError(f"Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))

        return True

    @classmethod
    def summary(cls) -> str:
        """Return a summary of current configuration (without secrets)."""
        return f"""
        Jarvis Configuration:
        - Workspace: {cls.JARVIS_WORKSPACE}
        - Authorized User: {cls.AUTHORIZED_TELEGRAM_USER_ID}
        - Codex Timeout: {cls.CODEX_TIMEOUT_SECONDS}s
        - Log Level: {cls.LOG_LEVEL}
        - Log Directory: {cls.LOG_DIR}
        """
