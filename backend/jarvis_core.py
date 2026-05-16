"""
Jarvis Core Backend - Main orchestrator
Always-running component that handles Telegram messages and routes to tools.
"""

import logging
import threading
from datetime import datetime
from telegram import BotCommand, Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

from config import Config
from audit_logger import AuditLogger
from user_auth import UserAuthenticator
from tools_registry import ToolsRegistry
from codex_bridge import run_codex, CodexError
from browser_tool import BrowserTool
from calendar_tool import AppleCalendarTool, CalendarError, CalendarEvent
from home_tool import HomeError, HomeTool
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
        self.home_tool = HomeTool(
            provider=Config.HOME_PROVIDER,
            timeout_seconds=Config.HOME_TIMEOUT_SECONDS,
            home_assistant_url=Config.HOME_ASSISTANT_URL,
            home_assistant_token=Config.HOME_ASSISTANT_TOKEN,
            shortcut_name=Config.HOMEKIT_STATUS_SHORTCUT,
        )
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

    async def handle_pexhelp(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pexhelp and /pexhelp <tool>."""
        user_id = update.effective_user.id
        username = update.effective_user.username or "unknown"

        if not self.authenticator.is_authorized(user_id):
            self.audit_logger.log_unauthorized_access(user_id, username, "/pexhelp")
            await update.message.reply_text("Access denied.")
            return

        text = update.message.text.strip()
        parts = text.split(maxsplit=1)
        tool_name = parts[1].strip().lower().lstrip("/") if len(parts) > 1 else ""

        self.audit_logger.log_action(
            user_id=user_id,
            username=username,
            action="pexhelp",
            details={"tool": tool_name or "all"},
        )
        try:
            await update.message.reply_text(self._format_pexhelp(tool_name)[:4000])
        except Exception as e:
            logger.exception("Pexhelp command failed")
            self.audit_logger.log_action(
                user_id=user_id,
                username=username,
                action="pexhelp",
                details={"tool": tool_name or "all", "status": "error", "error": str(e)},
            )
            await update.message.reply_text(f"Errore pexhelp: {e}")

    async def handle_tools_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /tools command to list available tools."""
        user_id = update.effective_user.id
        username = update.effective_user.username or "unknown"

        if not self.authenticator.is_authorized(user_id):
            self.audit_logger.log_unauthorized_access(user_id, username, "/tools")
            await update.message.reply_text("Access denied.")
            return

        self.audit_logger.log_action(
            user_id=user_id,
            username=username,
            action="list_tools",
            details={},
        )
        await update.message.reply_text(self._format_tools_list())

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

    async def handle_guide(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /guide command to persist Codex working instructions."""
        user_id = update.effective_user.id
        username = update.effective_user.username or "unknown"

        if not self.authenticator.is_authorized(user_id):
            self.audit_logger.log_unauthorized_access(user_id, username, "/guide")
            await update.message.reply_text("Access denied.")
            return

        instruction = update.message.text[len("/guide") :].strip()

        if not instruction:
            await update.message.reply_text(
                "Uso: /guide <istruzione per Codex>\n"
                f"File guida: {Config.CODEX_GUIDE_FILE}"
            )
            return

        try:
            guide_file = Config.CODEX_GUIDE_FILE
            guide_file.parent.mkdir(parents=True, exist_ok=True)

            if not guide_file.exists() or not guide_file.read_text(encoding="utf-8").strip():
                guide_file.write_text(
                    "# Codex Working Guide\n\n"
                    "Istruzioni persistenti per Codex quando lavora sulle cartelle allowlistate.\n\n",
                    encoding="utf-8",
                )

            timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
            with open(guide_file, "a", encoding="utf-8") as f:
                f.write(f"- {timestamp}: {instruction}\n")

            self.audit_logger.log_action(
                user_id=user_id,
                username=username,
                action="guide_update",
                details={"instruction_length": len(instruction), "guide_file": str(guide_file)},
            )
            await update.message.reply_text(f"Guida aggiornata: {guide_file}")
        except OSError as e:
            self.audit_logger.log_action(
                user_id=user_id,
                username=username,
                action="guide_update",
                details={"status": "error", "error": str(e)},
            )
            await update.message.reply_text(f"Errore aggiornando la guida: {e}")

    async def handle_home(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /home command."""
        user_id = update.effective_user.id
        username = update.effective_user.username or "unknown"

        if not self.authenticator.is_authorized(user_id):
            self.audit_logger.log_unauthorized_access(user_id, username, "/home")
            await update.message.reply_text("Access denied.")
            return

        text = update.message.text.strip().lower()
        mode = "status"
        if "devices" in text or "device" in text or "dispositivi" in text or "entita" in text:
            mode = "devices"

        try:
            if mode == "devices":
                result = await self.home_tool.devices()
            else:
                result = await self.home_tool.status()

            self.audit_logger.log_action(
                user_id=user_id,
                username=username,
                action="tool_home",
                details={"mode": mode, "provider": Config.HOME_PROVIDER, "status": "success"},
            )
            await update.message.reply_text(result[:4000])
        except HomeError as e:
            self.audit_logger.log_action(
                user_id=user_id,
                username=username,
                action="tool_home",
                details={
                    "mode": mode,
                    "provider": Config.HOME_PROVIDER,
                    "status": "error",
                    "error": str(e),
                },
            )
            await update.message.reply_text(f"Errore Home: {e}")

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
        app = (
            ApplicationBuilder()
            .token(Config.TELEGRAM_BOT_TOKEN)
            .post_init(self._sync_telegram_command_menu)
            .build()
        )

        # Command handlers
        app.add_handler(CommandHandler("start", self.handle_start))
        app.add_handler(CommandHandler("pexhelp", self.handle_pexhelp))
        app.add_handler(CommandHandler("health", self.handle_health))
        app.add_handler(CommandHandler("tools", self.handle_tools_list))
        app.add_handler(CommandHandler("codex", self.handle_codex))
        app.add_handler(CommandHandler("cerca", self.handle_search))
        app.add_handler(CommandHandler("web", self.handle_web))
        app.add_handler(CommandHandler("calendar", self.handle_calendar))
        app.add_handler(CommandHandler("guide", self.handle_guide))
        app.add_handler(CommandHandler("home", self.handle_home))

        # Message handler (must be last)
        app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

        return app

    async def _sync_telegram_command_menu(self, app):
        """Publish the current slash-command menu to Telegram."""
        await app.bot.set_my_commands(self._telegram_commands())
        logger.info("Telegram command menu synchronized")

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

    def _format_tools_list(self) -> str:
        home_status = "configured" if Config.HOME_PROVIDER != "disabled" else "not configured"
        return "\n".join(
            [
                "Available tools:",
                "",
                "/start - Initialize Telegram connection",
                "/pexhelp [tool] - Show help for one tool",
                "/pexhelp tools - Explain the tool list command",
                "/health - Check backend status",
                "/tools - Show this tool list",
                "/web - Get local web interface URL",
                "/cerca <query> - Open a Google search on this Mac",
                "/codex <prompt> - Run Codex CLI with read-only filesystem access",
                "/guide <instruction> - Add persistent instructions for Codex",
                "/calendar oggi - Show today's Apple Calendar events",
                "/calendar domani - Show tomorrow's Apple Calendar events",
                "/calendar settimana - Show Apple Calendar events for the next 7 days",
                f"/home status - Read smart-home status ({home_status})",
                f"/home devices - List smart-home entities ({home_status})",
                "",
                "Natural language routes:",
                "- Calendar: 'Che appuntamenti ho domani?'",
                "",
                "Local HTTP API:",
                "- GET /api/status",
                "- POST /api/search",
                "- POST /api/codex",
                "- GET /api/calendar/today",
                "- GET /api/calendar/tomorrow",
                "- GET /api/calendar/week",
                "- GET /api/calendar/events?start=YYYY-MM-DD&end=YYYY-MM-DD",
                "",
                "Use /pexhelp <tool> for details, for example /pexhelp codex.",
            ]
        )

    def _telegram_commands(self) -> list[BotCommand]:
        return [
            BotCommand("start", "Initialize Telegram connection"),
            BotCommand("pexhelp", "Show help for one tool"),
            BotCommand("health", "Check backend status"),
            BotCommand("tools", "Show available tools"),
            BotCommand("web", "Get local web interface URL"),
            BotCommand("cerca", "Open a Google search on this Mac"),
            BotCommand("codex", "Run Codex CLI"),
            BotCommand("guide", "Add persistent Codex instructions"),
            BotCommand("calendar", "Read Apple Calendar"),
            BotCommand("home", "Read smart-home status"),
        ]

    def _format_pexhelp(self, tool_name: str = "") -> str:
        help_items = self._pexhelp_items()

        if not tool_name:
            tools = ", ".join(f"/{name}" for name in help_items)
            return (
                "Uso: /pexhelp <tool>\n\n"
                f"Tool disponibili: {tools}\n\n"
                "Esempi:\n"
                "/pexhelp codex\n"
                "/pexhelp calendar\n"
                "/pexhelp home"
            )

        aliases = {
            "cerca": "cerca",
            "search": "cerca",
            "calendario": "calendar",
            "agenda": "calendar",
            "casa": "home",
            "homekit": "home",
            "ai": "codex",
            "pexmag": "codex",
        }
        normalized = aliases.get(tool_name, tool_name)

        item = help_items.get(normalized)
        if not item:
            return (
                f"Tool non riconosciuto: {tool_name}\n"
                "Usa /tools per la lista o /pexhelp senza argomenti."
            )

        lines = [
            f"/{normalized}",
            item["description"],
            "",
            "Uso:",
            *[f"- {usage}" for usage in item["usage"]],
        ]

        examples = item.get("examples", [])
        if examples:
            lines.extend(["", "Esempi:", *[f"- {example}" for example in examples]])

        notes = item.get("notes", [])
        if notes:
            lines.extend(["", "Note:", *[f"- {note}" for note in notes]])

        return "\n".join(lines)

    def _pexhelp_items(self) -> dict[str, dict[str, list[str] | str]]:
        home_status = "configurato" if Config.HOME_PROVIDER != "disabled" else "non configurato"
        return {
            "start": {
                "description": "Inizializza la connessione Telegram con Jarvis.",
                "usage": ["/start"],
                "examples": ["/start"],
            },
            "pexhelp": {
                "description": "Mostra istruzioni d'uso generali o per un tool specifico.",
                "usage": ["/pexhelp", "/pexhelp <tool>"],
                "examples": ["/pexhelp codex", "/pexhelp calendar", "/pexhelp home"],
            },
            "health": {
                "description": "Controlla se il backend Jarvis e' in esecuzione.",
                "usage": ["/health"],
                "examples": ["/health"],
            },
            "tools": {
                "description": "Mostra la lista attuale di comandi e API disponibili.",
                "usage": ["/tools", "/pexhelp tools"],
                "examples": ["/tools", "/pexhelp tools"],
                "notes": [
                    "La lista include comandi Telegram, route naturali e API HTTP locali.",
                    "Per i dettagli di un singolo tool usa /pexhelp <tool>, per esempio /pexhelp codex.",
                ],
            },
            "web": {
                "description": "Restituisce l'URL della web interface locale.",
                "usage": ["/web"],
                "examples": ["/web"],
            },
            "cerca": {
                "description": "Apre una ricerca Google nel browser del Mac.",
                "usage": ["/cerca <query>"],
                "examples": ["/cerca python fastapi tutorial"],
                "notes": ["Apre il browser localmente sul Mac dove gira Jarvis."],
            },
            "codex": {
                "description": "Esegue Codex CLI in modalita read-only sulle cartelle allowlistate.",
                "usage": ["/codex <richiesta>"],
                "examples": [
                    "/codex guarda in tasse/2025 e dimmi quali file trovi",
                    "/codex riassumi i documenti nella cartella casa/2026",
                ],
                "notes": [
                    "Le cartelle accessibili sono definite in backend/filesystem_allowlist.json.",
                    "Le istruzioni persistenti sono in data/documents/codex_guidance.md.",
                ],
            },
            "guide": {
                "description": "Aggiunge istruzioni persistenti che Codex riceve a ogni richiesta.",
                "usage": ["/guide <istruzione>"],
                "examples": [
                    "/guide Quando chiedo le tasse, controlla prima Steuererklärung*.pdf"
                ],
                "notes": [f"File guida: {Config.CODEX_GUIDE_FILE}"],
            },
            "calendar": {
                "description": "Legge Apple Calendar in sola lettura.",
                "usage": ["/calendar oggi", "/calendar domani", "/calendar settimana"],
                "examples": [
                    "/calendar domani",
                    "Che appuntamenti ho domani?",
                    "Che riunioni ho questa settimana?",
                ],
                "notes": [
                    "La prima chiamata puo' richiedere permessi macOS per Calendar/Automation."
                ],
            },
            "home": {
                "description": "Interroga lo stato smart-home in sola lettura.",
                "usage": ["/home status", "/home devices"],
                "examples": ["/home status", "/home devices"],
                "notes": [
                    f"Provider Home: {home_status}.",
                    "Configura HOME_PROVIDER=shortcut oppure HOME_PROVIDER=homeassistant in backend/.env.",
                    "Non sono implementati comandi per accendere o spegnere dispositivi.",
                ],
            },
        }

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
