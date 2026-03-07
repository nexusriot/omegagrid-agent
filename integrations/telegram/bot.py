from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from integrations.telegram.handlers import start_handler, ask_handler, text_handler

def build_bot(token: str):
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("ask", ask_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    return app
