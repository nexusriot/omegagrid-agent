"""Standalone entry point to run the Telegram bot.

Usage:
    python -m integrations.telegram.run

Requires TELEGRAM_BOT_TOKEN and optionally GATEWAY_URL in environment.
"""
import os
import sys
import logging

from integrations.telegram.bot import build_bot

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("telegram_bot")


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN is not set. Cannot start bot.")
        sys.exit(1)

    gateway_url = os.environ.get("GATEWAY_URL", "http://127.0.0.1:8000")
    logger.info("Starting Telegram bot (gateway: %s)", gateway_url)


    app = build_bot(token=token, gateway_url=gateway_url)
    app.run_polling()


if __name__ == "__main__":
    main()
