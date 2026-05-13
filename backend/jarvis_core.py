"""
Jarvis Core Backend - Main orchestrator
Always-running component that handles Telegram messages and routes to tools.
"""

import logging
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

from config import Config
from audit_logger import AuditLogger
from user_auth import UserAuthenticator
from tools_registry import ToolsRegistry
from codex_bridge import run_codex, CodexError
from browser_tool import BrowserTool
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
authenticator = UserAuthenticator(authorized_ids=[Config.AUTHORIZED_TELEGRAM_USER_ID])
tools_registry = ToolsRegistry()


class JarvisCore:
    """Main orchestrator for Jarvis backend."""

    def __init__(self, web_port: int = 8000):
        self.audit_logger = audit_logger
        self.authenticator = authenticator
        self.tools_registry = tools_registry
        self.browser_tool = BrowserTool()
        self.web_server = JarvisWebServer(port=web_port)
        self.web_server.set_browser_tool(self.browser_tool)
        self.web_server.set_codex_handler(run_codex)
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


if __name__ == "__main__":
    core = JarvisCore()
    core.run()
