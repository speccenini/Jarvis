"""
Jarvis Core Backend - Main orchestrator
Always-running component that handles Telegram messages and routes to tools.
"""

import logging
import threading
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

from config import Config
from audit_logger import AuditLogger
from user_auth import UserAuthenticator
from tools_registry import ToolsRegistry
from codex_bridge import run_codex, CodexError
from browser_tool import BrowserTool
from calendar_tool import AppleCalendarTool, CalendarError, CalendarEvent
from web_interface import JarvisWebServer

# Validate configuration on startup
Config.validate()

# Setup logging
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Initialize core components
audit_logger = AuditLogger(log_dir=Config.LOG_DIR)
authenticator = UserAuthenticator(authorized_ids=Config.authorized_telegram_user_ids())
tools_registry = ToolsRegistry()


class JarvisCore:
    """Main orchestrator for Jarvis backend."""

    def __init__(self, web_port: int = 8000):
        self.audit_logger = audit_logger
        self.authenticator = authenticator
        self.tools_registry = tools_registry
        self.browser_tool = BrowserTool()
        self.calendar_tool = AppleCalendarTool(timeout_seconds=Config.TOOL_TIMEOUT_DEFAULT)
        self.web_server = JarvisWebServer(port=web_port)
        self.web_server.set_browser_tool(self.browser_tool)
        self.web_server.set_codex_handler(run_codex)
        self.web_server.set_calendar_tool(self.calendar_tool)
        logger.info("Jarvis Core initialized")

    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user_id = update.effective_user.id
        username = update.effective_user.username or "unknown"

        if not self.authenticator.is_authorized(user_id):
            self.audit_logger.log_unauthorized_access(user_id, username, "/start")
            await update.message.reply_text("Access denied.")
            return

        self.audit_logger.log_action(
            user_id=user_id,
            username=username,
            action="command_start",
            details={"command": "/start"},
        )
        await update.message.reply_text("Jarvis online. Ready to assist.")

    async def handle_health(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle health check."""
        user_id = update.effective_user.id
        username = update.effective_user.username or "unknown"

        if not self.authenticator.is_authorized(user_id):
            self.audit_logger.log_unauthorized_access(user_id, username, "health")
            await update.message.reply_text("Access denied.")
            return

        self.audit_logger.log_action(
            user_id=user_id,
            username=username,
            action="health_check",
            details={},
        )
        await update.message.reply_text("Jarvis backend is running.")

    async def handle_tools_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /tools command to list available tools."""
        user_id = update.effective_user.id
        username = update.effective_user.username or "unknown"

        if not self.authenticator.is_authorized(user_id):
            self.audit_logger.log_unauthorized_access(user_id, username, "/tools")
            await update.message.reply_text("Access denied.")
            return

        tools_text = (
            "Available tools:\n\n"
            "• cerca <query> - Search on Google\n"
            "• codex <prompt> - Query Codex CLI\n"
            "• calendar oggi|domani|settimana - Read Apple Calendar\n"
            "• health - Check backend status\n"
            "• web - Open web interface\n\n"
            "More tools coming soon!"
        )

        self.audit_logger.log_action(
            user_id=user_id,
            username=username,
            action="list_tools",
            details={},
        )
        await update.message.reply_text(tools_text)

    async def handle_codex(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /codex command."""
        user_id = update.effective_user.id
        username = update.effective_user.username or "unknown"

        if not self.authenticator.is_authorized(user_id):
            self.audit_logger.log_unauthorized_access(user_id, username, "/codex")
            await update.message.reply_text("Access denied.")
            return

        prompt = update.message.text[len("/codex ") :].strip()

        if not prompt:
            await update.message.reply_text("Please provide a prompt after /codex.")
            return

        await update.message.reply_text("Calling Codex...")

        try:
            result = await run_codex(prompt)
            self.audit_logger.log_action(
                user_id=user_id,
                username=username,
                action="tool_codex",
                details={"prompt_length": len(prompt), "status": "success"},
            )
            await update.message.reply_text(result[:4000])
        except CodexError as e:
            error_msg = f"Codex error: {e}"
            self.audit_logger.log_action(
                user_id=user_id,
                username=username,
                action="tool_codex",
                details={"prompt_length": len(prompt), "status": "error", "error": str(e)},
            )
            await update.message.reply_text(error_msg)

    async def handle_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cerca command for Google search."""
        user_id = update.effective_user.id
        username = update.effective_user.username or "unknown"

        if not self.authenticator.is_authorized(user_id):
            self.audit_logger.log_unauthorized_access(user_id, username, "/cerca")
            await update.message.reply_text("Access denied.")
            return

        query = update.message.text[len("/cerca ") :].strip()

        if not query:
            await update.message.reply_text("Please provide a search query after /cerca.")
            return

        result = self.browser_tool.google_search(query)

        self.audit_logger.log_action(
            user_id=user_id,
            username=username,
            action="tool_browser_search",
            details={"query": query, "type": "google"},
        )

        await update.message.reply_text(result)

    async def handle_web(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /web command to get web interface URL."""
        user_id = update.effective_user.id
        username = update.effective_user.username or "unknown"

        if not self.authenticator.is_authorized(user_id):
            self.audit_logger.log_unauthorized_access(user_id, username, "/web")
            await update.message.reply_text("Access denied.")
            return

        web_url = self.web_server.get_url()
        self.audit_logger.log_action(
            user_id=user_id,
            username=username,
            action="web_interface_link",
            details={"url": web_url},
        )

        await update.message.reply_text(f"Web interface: {web_url}")

    async def handle_calendar(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /calendar command."""
        user_id = update.effective_user.id
        username = update.effective_user.username or "unknown"

        if not self.authenticator.is_authorized(user_id):
            self.audit_logger.log_unauthorized_access(user_id, username, "/calendar")
            await update.message.reply_text("Access denied.")
            return

        text = update.message.text.strip()
        period = self._detect_calendar_period(text)

        if not period:
            await update.message.reply_text(
                "Uso: /calendar oggi, /calendar domani, oppure /calendar settimana."
            )
            return

        await self._reply_with_calendar(update, user_id, username, period)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle generic messages."""
        user_id = update.effective_user.id
        username = update.effective_user.username or "unknown"

        if not self.authenticator.is_authorized(user_id):
            self.audit_logger.log_unauthorized_access(user_id, username, update.message.text)
            await update.message.reply_text("Access denied.")
            return

        text = update.message.text.strip()

        # Quick commands
        if text.lower() == "ping":
            self.audit_logger.log_action(
                user_id=user_id,
                username=username,
                action="ping",
                details={},
            )
            await update.message.reply_text("Pong!")
            return

        calendar_period = self._detect_calendar_period(text)
        if calendar_period and self._looks_like_calendar_request(text):
            await self._reply_with_calendar(update, user_id, username, calendar_period)
            return

        # For now, echo the message
        self.audit_logger.log_action(
            user_id=user_id,
            username=username,
            action="message_received",
            details={"message": text[:100]},
        )
        await update.message.reply_text(f"Message received: {text}\n\n(More intelligence coming soon)")

    def build_telegram_app(self):
        """Build and configure Telegram bot application."""
        app = ApplicationBuilder().token(Config.TELEGRAM_BOT_TOKEN).build()

        # Command handlers
        app.add_handler(CommandHandler("start", self.handle_start))
        app.add_handler(CommandHandler("health", self.handle_health))
        app.add_handler(CommandHandler("tools", self.handle_tools_list))
        app.add_handler(CommandHandler("codex", self.handle_codex))
        app.add_handler(CommandHandler("cerca", self.handle_search))
        app.add_handler(CommandHandler("web", self.handle_web))
        app.add_handler(CommandHandler("calendar", self.handle_calendar))

        # Message handler (must be last)
        app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

        return app

    def run(self):
        """Start the Jarvis backend."""
        if not Config.TELEGRAM_BOT_TOKEN:
            raise RuntimeError("Missing TELEGRAM_BOT_TOKEN in .env")

        logger.info("Starting Jarvis backend...")
        logger.info(Config.summary())

        # Start web server in background thread
        web_thread = threading.Thread(target=self._run_web_server, daemon=True)
        web_thread.start()
        logger.info(f"Web interface started at {self.web_server.get_url()}")

        # Start Telegram bot
        app = self.build_telegram_app()
        logger.info("Jarvis backend is now running (polling mode)...")
        logger.info("Waiting for messages on Telegram...")
        app.run_polling()

    def _run_web_server(self):
        """Run the web server in a separate thread."""
        import uvicorn

        try:
            uvicorn.run(
                self.web_server.get_app(),
                host="127.0.0.1",
                port=self.web_server.port,
                log_level="warning",
            )
        except Exception as e:
            logger.error(f"Web server error: {e}")

    async def _reply_with_calendar(
        self,
        update: Update,
        user_id: int,
        username: str,
        period: str,
    ):
        try:
            if period == "today":
                events = await self.calendar_tool.events_for_today()
                label = "oggi"
            elif period == "tomorrow":
                events = await self.calendar_tool.events_for_tomorrow()
                label = "domani"
            elif period == "week":
                events = await self.calendar_tool.events_for_week()
                label = "i prossimi 7 giorni"
            else:
                await update.message.reply_text("Periodo calendario non riconosciuto.")
                return

            self.audit_logger.log_action(
                user_id=user_id,
                username=username,
                action="tool_calendar",
                details={"period": period, "event_count": len(events)},
            )
            await update.message.reply_text(self._format_calendar_events(events, label))
        except CalendarError as e:
            self.audit_logger.log_action(
                user_id=user_id,
                username=username,
                action="tool_calendar",
                details={"period": period, "status": "error", "error": str(e)},
            )
            await update.message.reply_text(f"Errore Calendar: {e}")

    @staticmethod
    def _detect_calendar_period(text: str) -> str | None:
        normalized = text.lower()

        if any(word in normalized for word in ("domani", "tomorrow")):
            return "tomorrow"

        if any(
            phrase in normalized
            for phrase in (
                "settimana",
                "questa week",
                "this week",
                "prossimi 7",
                "prossimi sette",
                "week",
            )
        ):
            return "week"

        if any(word in normalized for word in ("oggi", "today")):
            return "today"

        return None

    @staticmethod
    def _looks_like_calendar_request(text: str) -> bool:
        normalized = text.lower()
        return any(
            word in normalized
            for word in (
                "appuntamenti",
                "agenda",
                "calendario",
                "calendar",
                "meeting",
                "riunioni",
                "eventi",
            )
        )

    @staticmethod
    def _format_calendar_events(events: list[CalendarEvent], label: str) -> str:
        if not events:
            return f"Non hai appuntamenti per {label}."

        lines = [f"Appuntamenti per {label}:"]
        for event in events[:20]:
            lines.append(f"- {JarvisCore._format_calendar_event(event)}")

        if len(events) > 20:
            lines.append(f"... altri {len(events) - 20} eventi non mostrati.")

        return "\n".join(lines)

    @staticmethod
    def _format_calendar_event(event: CalendarEvent) -> str:
        title = event.title or "Untitled"
        calendar = event.calendar or "Calendar"
        location = f" @ {event.location}" if event.location else ""

        if event.all_day:
            return f"Tutto il giorno - {title} ({calendar}){location}"

        start = JarvisCore._format_event_time(event.start)
        end = JarvisCore._format_event_time(event.end)

        if start and end:
            return f"{start}-{end} - {title} ({calendar}){location}"
        if start:
            return f"{start} - {title} ({calendar}){location}"
        return f"{title} ({calendar}){location}"

    @staticmethod
    def _format_event_time(value: str) -> str:
        if not value:
            return ""

        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return ""

        return parsed.astimezone().strftime("%H:%M")


if __name__ == "__main__":
    core = JarvisCore()
    core.run()
