# handlers/common/messaging.py
"""Разбивка длинных сообщений (в основном недельное расписание) по лимиту Telegram 4096.

Сообщения режутся по границам строк, чтобы не ломать разметку Markdown
(пары `*...*`, `` `...` `` и т.п. не рвутся посередине).
"""
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4096


def split_long_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> List[str]:
    """Разбивает текст на части не длиннее max_length по границам строк.

    Если отдельная строка всё равно длиннее лимита (в ней нет переноса до
    max_length), она режется жёстко — иначе сообщение не уйдёт вовсе.
    """
    if not text:
        return []

    chunks: List[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break

        # Ищем границу строки в пределах лимита, чтобы не разрывать строку
        cut = remaining.rfind('\n', 0, max_length + 1)
        if cut == -1:
            # Длинная строка без переноса — ищем пробел, иначе режем жёстко
            space_cut = remaining.rfind(' ', 0, max_length + 1)
            cut = space_cut if space_cut > 0 else max_length

        chunks.append(remaining[:cut])
        # Потребляем символ переноса, если он был на границе
        next_i = cut + 1 if cut < len(remaining) and remaining[cut] == '\n' else cut
        remaining = remaining[next_i:]

    return chunks


def _mark_chunk(chunk: str, i: int, total: int) -> str:
    """Добавляет маркер продолжения, если это не последняя часть."""
    if i < total:
        return f"{chunk}\n\n*(… продолжение: {i}/{total})*"
    return chunk


async def edit_long_message(
    update, context, query, text: str,
    reply_markup=None, parse_mode: Optional[str] = 'Markdown',
):
    """Редактирует сообщение по callback_query, разбивая длинный текст.

    Первая часть редактирует исходное сообщение (с reply_markup), остальные
    отправляются reply-сообщениями в тот же чат.
    """
    chunks = split_long_message(text)
    if not chunks:
        return

    if len(chunks) == 1:
        await query.edit_message_text(chunks[0], reply_markup=reply_markup, parse_mode=parse_mode)
        return

    await query.edit_message_text(_mark_chunk(chunks[0], 1, len(chunks)),
                                  reply_markup=reply_markup, parse_mode=parse_mode)

    chat_id = update.effective_chat.id if update.effective_chat else None
    if chat_id is None:
        logger.error("Cannot send continuation: no chat id in update")
        return

    for i, chunk in enumerate(chunks[1:], start=2):
        await context.bot.send_message(
            chat_id=chat_id,
            text=_mark_chunk(chunk, i, len(chunks)),
            parse_mode=parse_mode,
            disable_web_page_preview=True,
        )


async def reply_long_message(
    update, context, text: str, parse_mode: Optional[str] = 'Markdown',
):
    """Отправляет длинное сообщение reply-сообщениями, разбивая по лимиту."""
    chunks = split_long_message(text)
    if not chunks:
        return

    for i, chunk in enumerate(chunks, start=1):
        await update.message.reply_text(
            _mark_chunk(chunk, i, len(chunks)),
            parse_mode=parse_mode,
            disable_web_page_preview=True,
        )
