from __future__ import annotations

import logging
from typing import Any

import requests
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# The gateway URL is set at bot startup via set_gateway_url()
_gateway_url: str = "http://127.0.0.1:8000"

# Per-user session tracking (chat_id -> session_id)
_sessions: dict[int, int] = {}


def set_gateway_url(url: str):
    global _gateway_url
    _gateway_url = url.rstrip("/")


def _query_agent(text: str, chat_id: int) -> dict[str, Any]:
    """Send a query to the agent gateway and return the result."""
    payload: dict[str, Any] = {"query": text}
    sid = _sessions.get(chat_id)
    if sid:
        payload["session_id"] = sid

    resp = requests.post(f"{_gateway_url}/api/query", json=payload, timeout=180)
    resp.raise_for_status()
    data = resp.json()

    # Track session for this user
    _sessions[chat_id] = data.get("session_id")
    return data


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    _sessions.pop(chat_id, None)
    await update.message.reply_text(
        "Hello! I'm the OmegaGrid Agent bot.\n\n"
        "Just send me any message and I'll process it through the agent.\n\n"
        "Commands:\n"
        "/start - Reset session & show this help\n"
        "/ask <question> - Ask the agent explicitly\n"
        "/new - Start a new session\n"
        "/skills - List available skills"
    )


async def ask_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args).strip() if context.args else ""
    if not text:
        await update.message.reply_text("Usage: /ask <your question>")
        return

    chat_id = update.effective_chat.id
    await update.message.reply_text("Thinking...")
    try:
        result = _query_agent(text, chat_id)
        answer = result.get("answer", "(no answer)")
        model = result.get("meta", {}).get("model", "?")
        steps = result.get("meta", {}).get("step_count", "?")
        await update.message.reply_text(
            f"{answer}\n\n_model: {model} | steps: {steps}_",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.exception("Agent query failed")
        await update.message.reply_text(f"Error: {e}")


async def new_session_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    _sessions.pop(chat_id, None)
    await update.message.reply_text("Session reset. Next message starts a fresh conversation.")


async def skills_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        resp = requests.get(f"{_gateway_url}/api/skills", timeout=10)
        resp.raise_for_status()
        skills = resp.json().get("skills", [])
        if not skills:
            await update.message.reply_text("No skills loaded.")
            return
        lines = ["Available skills:"]
        for s in skills:
            lines.append(f"- *{s['name']}*: {s['description']}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Error listing skills: {e}")


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle plain text messages - route them to the agent."""
    text = (update.message.text or "").strip()
    if not text:
        return

    chat_id = update.effective_chat.id
    try:
        result = _query_agent(text, chat_id)
        answer = result.get("answer", "(no answer)")
        await update.message.reply_text(answer)
    except Exception as e:
        logger.exception("Agent query failed")
        await update.message.reply_text(f"Error: {e}")
