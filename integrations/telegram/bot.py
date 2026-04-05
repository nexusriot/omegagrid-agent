from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from integrations.telegram.auth import UserStore
from integrations.telegram.handlers import (
    start_handler,
    ask_handler,
    new_session_handler,
    skills_handler,
    auth_add_handler,
    auth_list_handler,
    text_handler,
    set_gateway_url,
)


def build_bot(token: str, gateway_url: str = "http://127.0.0.1:8000"):
    """Build and return a configured Telegram bot application."""
    set_gateway_url(gateway_url)

    app = ApplicationBuilder().token(token).build()
    app.bot_data["auth_store"] = UserStore.from_env()
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("ask", ask_handler))
    app.add_handler(CommandHandler("new", new_session_handler))
    app.add_handler(CommandHandler("skills", skills_handler))
    app.add_handler(CommandHandler("auth_add", auth_add_handler))
    app.add_handler(CommandHandler("auth_list", auth_list_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    return app
