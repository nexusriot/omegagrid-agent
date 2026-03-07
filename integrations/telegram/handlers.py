async def start_handler(update, context):
    await update.message.reply_text("Agent bot skeleton is alive.")

async def ask_handler(update, context):
    text = " ".join(context.args).strip()
    await update.message.reply_text(f"Stub /ask: {text}")

async def text_handler(update, context):
    await update.message.reply_text("Use /ask <question>.")
