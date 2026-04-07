from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any

import requests
from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, TimedOut, RetryAfter
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
    payload: dict[str, Any] = {
        "query": text,
        "telegram_chat_id": chat_id,
    }
    sid = _sessions.get(chat_id)
    if sid:
        payload["session_id"] = sid

    resp = requests.post(f"{_gateway_url}/api/query", json=payload, timeout=180)
    resp.raise_for_status()
    data = resp.json()

    # Track session for this user
    _sessions[chat_id] = data.get("session_id")
    return data


_EDIT_INTERVAL_S = 1.5

# Status emoji mapping
_STEP_ICONS = {
    "thinking": "\u2699\ufe0f",     # gear
    "tool_call": "\ud83d\udee0\ufe0f",  # wrench
    "tool_result": "\u2705",          # check
}


def _render_status(events: list[dict]) -> str:
    """Build a compact multi-line status text from accumulated events."""
    lines: list[str] = []
    for ev in events:
        t = ev.get("event")
        if t == "thinking":
            lines.append(f"{_STEP_ICONS['thinking']} Thinking (step {ev.get('step', '?')})...")
        elif t == "tool_call":
            tool = ev.get("tool", "?")
            why = ev.get("why", "")
            brief = f" — {why}" if why else ""
            lines.append(f"{_STEP_ICONS['tool_call']} Calling {tool}{brief}")
        elif t == "tool_result":
            tool = ev.get("tool", "?")
            elapsed = ev.get("elapsed_s", 0)
            lines.append(f"{_STEP_ICONS['tool_result']} {tool} done ({elapsed:.1f}s)")
    return "\n".join(lines) if lines else "Processing..."


async def _safe_edit(message, text: str):
    """Edit a message, ignoring common transient errors."""
    try:
        await message.edit_text(text)
    except BadRequest as e:
        if "message is not modified" in str(e).lower():
            pass  # identical text, ignore
        else:
            logger.warning("edit_text BadRequest: %s", e)
    except (TimedOut, RetryAfter):
        pass  # transient, skip this edit cycle
    except Exception:
        logger.debug("edit_text failed", exc_info=True)


async def _stream_to_message(message, text: str, chat_id: int):
    """Consume SSE from /api/query/stream and progressively edit *message*."""
    payload: dict[str, Any] = {
        "query": text,
        "telegram_chat_id": chat_id,
    }
    sid = _sessions.get(chat_id)
    if sid:
        payload["session_id"] = sid

    accumulated: list[dict] = []
    last_edit = 0.0
    final_answer: str | None = None
    final_meta: dict = {}

    try:
        resp = requests.post(
            f"{_gateway_url}/api/query/stream",
            json=payload,
            stream=True,
            timeout=300,
        )
        resp.raise_for_status()

        event_type = ""
        data_buf = ""
        for raw_line in resp.iter_lines(decode_unicode=True):
            if raw_line is None:
                continue
            line = raw_line  # already decoded
            if line.startswith("event:"):
                event_type = line[len("event:"):].strip()
                continue
            if line.startswith("data:"):
                data_buf = line[len("data:"):].strip()
                # Process complete event
                try:
                    ev = json.loads(data_buf)
                except json.JSONDecodeError:
                    continue

                ev_type = ev.get("event", event_type)

                if ev_type == "final":
                    final_answer = ev.get("answer", "(no answer)")
                    final_meta = ev.get("meta", {})
                    _sessions[chat_id] = ev.get("session_id")
                    break
                elif ev_type == "error":
                    final_answer = f"Error: {ev.get('error', 'unknown')}"
                    break

                # Intermediate event — accumulate and edit
                accumulated.append(ev)
                now = time.monotonic()
                if now - last_edit >= _EDIT_INTERVAL_S:
                    status_text = _render_status(accumulated)
                    await _safe_edit(message, status_text)
                    last_edit = now
                    # yield back to event loop
                    await asyncio.sleep(0)

                data_buf = ""
                event_type = ""
                continue
            # empty line = end of event (already handled above)

    except requests.RequestException as e:
        logger.exception("Stream request failed, falling back to sync")
        # Fallback to non-streaming
        try:
            result = _query_agent(text, chat_id)
            final_answer = result.get("answer", "(no answer)")
            final_meta = result.get("meta", {})
        except Exception as e2:
            final_answer = f"Error: {e2}"

    return final_answer, final_meta


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
    status_msg = await update.message.reply_text("\u2699\ufe0f Processing...")
    try:
        answer, meta = await _stream_to_message(status_msg, text, chat_id)
        model = meta.get("model", "?")
        steps = meta.get("step_count", "?")
        final_text = f"{answer}\n\n_model: {model} | steps: {steps}_"
        try:
            await status_msg.edit_text(final_text, parse_mode=ParseMode.MARKDOWN)
        except BadRequest:
            await status_msg.edit_text(final_text)
    except Exception as e:
        logger.exception("Agent query failed")
        await _safe_edit(status_msg, f"Error: {e}")


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
    """Handle plain text messages - route them to the agent with streaming."""
    if not await _ensure_authorized(update, context):
        return

    text = (update.message.text or "").strip()
    if not text:
        return

    chat_id = update.effective_chat.id
    status_msg = await update.message.reply_text("\u2699\ufe0f Processing...")
    try:
        answer, meta = await _stream_to_message(status_msg, text, chat_id)
        try:
            await status_msg.edit_text(answer, parse_mode=ParseMode.MARKDOWN)
        except BadRequest:
            await status_msg.edit_text(answer)
    except Exception as e:
        logger.exception("Agent query failed")
        await _safe_edit(status_msg, f"Error: {e}")
