"""
Configuration Module
Central place for all Jarvis configuration settings.
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Jarvis configuration."""

    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    AUTHORIZED_TELEGRAM_USER_ID = int(os.getenv("AUTHORIZED_TELEGRAM_USER_ID", "0"))
    TELEGRAM_WHITELIST_FILE = Path(
        os.getenv(
            "TELEGRAM_WHITELIST_FILE",
            Path(__file__).with_name("telegram_whitelist.json"),
        )
    ).expanduser()

    # Workspace
    JARVIS_WORKSPACE = Path(os.getenv("JARVIS_WORKSPACE", "~/JarvisWorkspace")).expanduser()
    CODEX_GUIDE_FILE = Path(
        os.getenv(
            "CODEX_GUIDE_FILE",
            JARVIS_WORKSPACE / "documents" / "codex_guidance.md",
        )
    ).expanduser()
    FILESYSTEM_ALLOWLIST_FILE = Path(
        os.getenv(
            "FILESYSTEM_ALLOWLIST_FILE",
            Path(__file__).with_name("filesystem_allowlist.json"),
        )
    ).expanduser()

    # Codex
    CODEX_TIMEOUT_SECONDS = int(os.getenv("CODEX_TIMEOUT_SECONDS", "180"))

    # Home / HomeKit
    HOME_PROVIDER = os.getenv("HOME_PROVIDER", "disabled").lower()
    HOME_ASSISTANT_URL = os.getenv("HOME_ASSISTANT_URL", "").rstrip("/")
    HOME_ASSISTANT_TOKEN = os.getenv("HOME_ASSISTANT_TOKEN", "")
    HOMEKIT_STATUS_SHORTCUT = os.getenv("HOMEKIT_STATUS_SHORTCUT", "Jarvis Home Status")
    HOME_TIMEOUT_SECONDS = int(os.getenv("HOME_TIMEOUT_SECONDS", "20"))

    # Logging
    LOG_DIR = JARVIS_WORKSPACE / "logs"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # Tool defaults
    TOOL_TIMEOUT_DEFAULT = 30  # seconds
    TOOL_MAX_OUTPUT_LENGTH = 4000  # characters

    @classmethod
    def authorized_telegram_user_ids(cls) -> list[int]:
        """Load authorized Telegram user IDs from file, with .env fallback."""
        user_ids = set()

        if cls.TELEGRAM_WHITELIST_FILE.exists():
            with open(cls.TELEGRAM_WHITELIST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            raw_user_ids = data.get("authorized_user_ids", [])
            if not isinstance(raw_user_ids, list):
                raise ValueError(
                    f"authorized_user_ids must be a list in {cls.TELEGRAM_WHITELIST_FILE}"
                )

            for raw_user_id in raw_user_ids:
                try:
                    user_ids.add(int(raw_user_id))
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"Invalid Telegram user ID in {cls.TELEGRAM_WHITELIST_FILE}: {raw_user_id}"
                    ) from exc

        if cls.AUTHORIZED_TELEGRAM_USER_ID:
            user_ids.add(cls.AUTHORIZED_TELEGRAM_USER_ID)

        return sorted(user_ids)

    @classmethod
    def allowed_filesystem_roots(cls, access: str = "read") -> list[Path]:
        """Load local filesystem roots Jarvis may access."""
        if access not in {"read", "write"}:
            raise ValueError("access must be 'read' or 'write'")

        if not cls.FILESYSTEM_ALLOWLIST_FILE.exists():
            return [cls.JARVIS_WORKSPACE.resolve()]

        with open(cls.FILESYSTEM_ALLOWLIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        raw_roots = data.get("allowed_roots", [])
        if not isinstance(raw_roots, list):
            raise ValueError(
                f"allowed_roots must be a list in {cls.FILESYSTEM_ALLOWLIST_FILE}"
            )

        roots = []
        for raw_root in raw_roots:
            if isinstance(raw_root, str):
                path = raw_root
                is_allowed = access == "read"
            elif isinstance(raw_root, dict):
                path = raw_root.get("path")
                is_allowed = bool(raw_root.get(access, False))
            else:
                raise ValueError(
                    f"Invalid filesystem allowlist entry in {cls.FILESYSTEM_ALLOWLIST_FILE}: {raw_root}"
                )

            if not path:
                raise ValueError(
                    f"Filesystem allowlist entry is missing path in {cls.FILESYSTEM_ALLOWLIST_FILE}"
                )

            if is_allowed:
                roots.append(Path(path).expanduser().resolve())

        return sorted(set(roots))

    @classmethod
    def is_filesystem_path_allowed(cls, path: str | Path, access: str = "read") -> bool:
        """Return True if path is under an allowlisted root."""
        target = Path(path).expanduser().resolve()

        for root in cls.allowed_filesystem_roots(access=access):
            try:
                target.relative_to(root)
                return True
            except ValueError:
                continue

        return False

    @classmethod
    def validate(cls):
        """Validate critical configuration values."""
        errors = []

        if not cls.TELEGRAM_BOT_TOKEN:
            errors.append("Missing TELEGRAM_BOT_TOKEN")

        try:
            authorized_user_ids = cls.authorized_telegram_user_ids()
        except ValueError as e:
            errors.append(str(e))
            authorized_user_ids = []

        if not authorized_user_ids:
            errors.append(
                "Missing authorized Telegram users. Add users to "
                f"{cls.TELEGRAM_WHITELIST_FILE} or set AUTHORIZED_TELEGRAM_USER_ID."
            )

        if not cls.JARVIS_WORKSPACE.exists():
            errors.append(f"JARVIS_WORKSPACE does not exist: {cls.JARVIS_WORKSPACE}")

        guide_parent = cls.CODEX_GUIDE_FILE.parent
        if not guide_parent.exists():
            try:
                guide_parent.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                errors.append(f"Cannot create Codex guide directory {guide_parent}: {e}")

        try:
            allowed_roots = cls.allowed_filesystem_roots()
        except ValueError as e:
            errors.append(str(e))
            allowed_roots = []

        for root in allowed_roots:
            if not root.exists():
                errors.append(f"Allowed filesystem root does not exist: {root}")

        if errors:
            raise ValueError(f"Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))

        return True

    @classmethod
    def summary(cls) -> str:
        """Return a summary of current configuration (without secrets)."""
        return f"""
        Jarvis Configuration:
        - Workspace: {cls.JARVIS_WORKSPACE}
        - Authorized Telegram Users: {len(cls.authorized_telegram_user_ids())}
        - Telegram Whitelist: {cls.TELEGRAM_WHITELIST_FILE}
        - Filesystem Allowlist: {cls.FILESYSTEM_ALLOWLIST_FILE}
        - Allowed Filesystem Roots: {len(cls.allowed_filesystem_roots())}
        - Codex Guide: {cls.CODEX_GUIDE_FILE}
        - Codex Timeout: {cls.CODEX_TIMEOUT_SECONDS}s
        - Home Provider: {cls.HOME_PROVIDER}
        - Log Level: {cls.LOG_LEVEL}
        - Log Directory: {cls.LOG_DIR}
        """
