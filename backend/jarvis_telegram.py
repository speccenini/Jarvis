import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from codex_bridge import run_codex, CodexError

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AUTHORIZED_USER_ID = int(os.getenv("AUTHORIZED_TELEGRAM_USER_ID"))

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id != AUTHORIZED_USER_ID:
        await update.message.reply_text("Access denied.")
        return

    await update.message.reply_text("Jarvis online.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id != AUTHORIZED_USER_ID:
        await update.message.reply_text("Access denied.")
        return

    text = update.message.text.strip()

    if text.lower() in ["ping", "health"]:
        await update.message.reply_text("Jarvis backend is running.")
        return

    if text.lower().startswith("/codex "):
        prompt = text[len("/codex "):].strip()

        if not prompt:
            await update.message.reply_text("Scrivi un prompt dopo /codex.")
            return

        try:
            result = await run_codex(prompt)
            await update.message.reply_text(result[:4000])
        except CodexError as e:
            await update.message.reply_text(f"Errore Codex: {e}")

        return

    await update.message.reply_text(f"Ricevuto: {text}")

def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == "__main__":
    main()