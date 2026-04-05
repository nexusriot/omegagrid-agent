from __future__ import annotations

import logging
import re
from typing import Any

import requests
from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


def _escape_markdown_v2(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!\\])", r"\\\1", text)


async def _safe_reply(message, text: str, parse_mode=None):
    """Send a message, falling back to plain text if Markdown parsing fails."""
    try:
        await message.reply_text(text, parse_mode=parse_mode)
    except BadRequest as e:
        if "parse entities" in str(e).lower() or "can't find end" in str(e).lower():
            logger.warning("Markdown parse failed, retrying as plain text: %s", e)
            await message.reply_text(text, parse_mode=None)
        else:
            raise

# The gateway URL is set at bot startup via set_gateway_url()
_gateway_url: str = "http://127.0.0.1:8000"

# Per-user session tracking (chat_id -> session_id)
_sessions: dict[int, int] = {}


def set_gateway_url(url: str):
    global _gateway_url
    _gateway_url = url.rstrip("/")


def _get_auth_store(context: ContextTypes.DEFAULT_TYPE):
    return context.application.bot_data.get("auth_store")


async def _ensure_authorized(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    store = _get_auth_store(context)
    if not store:
        return True

    chat_id = update.effective_chat.id
    if not store.is_authorized(chat_id):
        await update.message.reply_text("Access denied. Ask the bot admin to allow your Telegram ID.")
        return False

    store.touch(chat_id)
    return True


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

    store = _get_auth_store(context)
    auth_extra = ""
    if store and store.is_enabled():
        auth_extra = f"\n\nYour Telegram ID: `{chat_id}`"

    await _safe_reply(
        update.message,
        "Hello! I'm the OmegaGrid Agent bot.\n\n"
        "Just send me any message and I'll process it through the agent.\n\n"
        "Commands:\n"
        "/start - Reset session & show this help\n"
        "/ask <question> - Ask the agent explicitly\n"
        "/new - Start a new session\n"
        "/skills - List available skills\n"
        "/auth_add <telegram_id> - Admin only, allow a user\n"
        "/auth_list - Admin only, list allowed users"
        f"{auth_extra}",
        parse_mode=ParseMode.MARKDOWN,
    )


async def ask_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _ensure_authorized(update, context):
        return

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
        await _safe_reply(
            update.message,
            f"{answer}\n\n_model: {model} | steps: {steps}_",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        logger.exception("Agent query failed")
        await update.message.reply_text(f"Error: {e}")


async def new_session_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _ensure_authorized(update, context):
        return
    chat_id = update.effective_chat.id
    _sessions.pop(chat_id, None)
    await update.message.reply_text("Session reset. Next message starts a fresh conversation.")


async def skills_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _ensure_authorized(update, context):
        return
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
        await _safe_reply(update.message, "\n".join(lines), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"Error listing skills: {e}")


async def auth_add_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    store = _get_auth_store(context)
    chat_id = update.effective_chat.id
    if not store or not store.is_enabled():
        await update.message.reply_text("Auth is disabled.")
        return
    if not store.is_admin(chat_id):
        await update.message.reply_text("Only the admin can add users.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /auth_add <telegram_id>")
        return
    try:
        new_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("telegram_id must be an integer.")
        return
    store.add_user(new_id)
    await update.message.reply_text(f"Authorized Telegram ID: {new_id}")


async def auth_list_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    store = _get_auth_store(context)
    chat_id = update.effective_chat.id
    if not store or not store.is_enabled():
        await update.message.reply_text("Auth is disabled.")
        return
    if not store.is_admin(chat_id):
        await update.message.reply_text("Only the admin can list users.")
        return

    users = store.list_users(limit=100)
    lines = [f"Admin: `{store.admin_id}`"]
    if not users:
        lines.append("No authorized users yet.")
    else:
        lines.append("Authorized users:")
        for user in users:
            lines.append(f"- `{user.telegram_id}` | created={user.created_at} | last={user.last_activity}")
    await _safe_reply(update.message, "\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle plain text messages - route them to the agent."""
    if not await _ensure_authorized(update, context):
        return

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
