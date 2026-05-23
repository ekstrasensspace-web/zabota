"""
Telegram AI Curator Bot
Stack: python-telegram-bot v21+ (async) + Anthropic Claude + BM25 RAG

Responds when:
  • Bot is @mentioned in group chat
  • User replies to a bot message
  • Message contains ? or starts with a question word
  • Commands: /start  /спросить <вопрос>  /ask <question>
"""

import logging
import re

import anthropic
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import (
    ANTHROPIC_API_KEY,
    CLAUDE_MODEL,
    MAX_TOKENS,
    TELEGRAM_TOKEN,
    TRIGGER_QUESTION_MARK,
    TRIGGER_QUESTION_WORDS,
)
from prompts import START_MESSAGE, SYSTEM_PROMPT
from rag import build_index, query_knowledge

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Russian + English question starters
_QUESTION_WORDS = {
    "как", "что", "когда", "где", "почему", "зачем", "кто", "чем",
    "какой", "какая", "какое", "какие", "можно", "нужно", "стоит",
    "объясни", "расскажи", "помоги", "подскажи", "скажи",
    "how", "what", "when", "where", "why", "who", "which",
}


def _is_question(text: str) -> bool:
    if TRIGGER_QUESTION_MARK and "?" in text:
        return True
    if TRIGGER_QUESTION_WORDS and text.strip().split():
        first = re.sub(r"^[^а-яёa-z]+", "", text.strip().lower().split()[0])
        if first in _QUESTION_WORDS:
            return True
    return False


# ---------------------------------------------------------------------------
# Core answer logic
# ---------------------------------------------------------------------------

async def _answer(update: Update, question: str) -> None:
    if not question or len(question.strip()) < 3:
        return

    chat_id = update.effective_chat.id
    message = update.effective_message

    # Show typing indicator
    await update.effective_chat.send_action(ChatAction.TYPING)

    try:
        chunks = query_knowledge(question)
        context = "\n\n---\n\n".join(chunks) if chunks else "Релевантные материалы не найдены."
        system = SYSTEM_PROMPT.format(context=context)

        resp = claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": question}],
        )
        answer = resp.content[0].text
        await message.reply_text(answer, parse_mode="Markdown")

    except anthropic.APIError as exc:
        logger.error("Anthropic API error: %s", exc)
        await message.reply_text("⚠️ Временная ошибка API. Попробуй через минуту.")
    except Exception as exc:
        logger.error("Unexpected error: %s", exc, exc_info=True)
        await message.reply_text("⚠️ Что-то пошло не так. Обратись к куратору напрямую.")


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(START_MESSAGE)


async def cmd_ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    parts = (update.message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await update.message.reply_text(
            "Напиши вопрос после команды.\n"
            "Например: /спросить как запустить вихрь?"
        )
        return
    await _answer(update, parts[1].strip())


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    text = message.text or ""
    if not text.strip():
        return

    bot_username = f"@{context.bot.username}".lower()
    is_mentioned = bot_username in text.lower()
    is_reply_to_bot = bool(
        message.reply_to_message
        and message.reply_to_message.from_user
        and message.reply_to_message.from_user.id == context.bot.id
    )

    clean = re.sub(re.escape(bot_username), "", text, flags=re.IGNORECASE).strip()

    if is_mentioned or is_reply_to_bot:
        await _answer(update, clean or text)
    elif _is_question(text):
        await _answer(update, text)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    logger.info("Building knowledge index…")
    build_index()
    logger.info("Starting bot…")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler(["start", "help"], cmd_start))
    app.add_handler(CommandHandler(["спросить", "ask", "q"], cmd_ask))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is polling")
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
