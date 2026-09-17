# handlers/common/messaging.py
"""Разбивка длинных сообщений (в основном недельное расписание) по лимиту Telegram 4096.

Сообщения режутся по границам строк, чтобы не ломать разметку Markdown
(пары `*...*`, `` `...` `` и т.п. не рвутся посередине).
"""
import logging
import time

import telegram.error
from telegram import CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4096
MAX_COPY_TEXT_LENGTH = 256

# Сколько секунд «ждём текст поиска» после нажатия «Поиск». Если пользователь
# открыл ввод и ушёл, старый флаг не должен через неделю трактовать любой текст
# как поиск.
SEARCH_FLAG_TTL = 1800
_SEARCH_KINDS = ('teacher', 'room')

GENERIC_ERROR_MSG = "❌ Произошла непредвиденная ошибка. Попробуйте позже."


def log_user_error(message: str, exc: Exception) -> str:
    """Логирует реальное исключение и возвращает безопасный текст для пользователя.

    Раньше пользователю показывали `str(e)` (утекли внутренности, e.g. пути к БД).
    Теперь в лог идёт реальная причина, а в чат — общее сообщение.
    """
    logger.error(f"{message} - {exc}", exc_info=exc)
    return GENERIC_ERROR_MSG


async def safe_edit_message(query, text: str, reply_markup=None,
                            parse_mode: str | None = 'Markdown') -> None:
    """Редактирует сообщение, тихо игнорируя «message is not modified».

    Повторное нажатие «Обновить»/«Назад» на уже показанное сообщение даёт
    BadRequest «Message is not modified» — раньше это улетало в error handler
    как «непредвиденная ошибка». Здесь оно проглатывается.
    """
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except telegram.error.BadRequest as e:
        if "not modified" not in str(e).lower():
            raise


def split_long_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Разбивает текст на части не длиннее max_length по границам строк.

    Разбивка без потерь: `''.join(chunks) == text`. Режем по границам строк,
    перебирая строки и склеивая их, пока они помещаются в лимит, чтобы не рвать
    пары `*...*`/`` `...` `` разметки Markdown. Если отдельная строка длиннее
    лимита (нет переноса внутри), режем её жёстко — иначе сообщение не уйдёт.
    """
    if not text:
        return []

    chunks: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        if len(current) + len(line) <= max_length:
            current += line
            continue

        # Текущая строка не помещается: выгружаем накопленное
        if current:
            chunks.append(current)
            current = ""

        # Сама строка может быть длиннее лимита — режем её на куски
        if len(line) > max_length:
            while len(line) > max_length:
                chunks.append(line[:max_length])
                line = line[max_length:]
            current = line
        else:
            current = line

    if current:
        chunks.append(current)

    return chunks


def _mark_chunk(chunk: str, i: int, total: int) -> str:
    """Добавляет маркер продолжения, если это не последняя часть."""
    if i < total:
        return f"{chunk}\n\n*(… продолжение: {i}/{total})*"
    return chunk


def reset_user_flow(context) -> None:
    """Полностью сбрасывает временное состояние пользователя (флаги поиска, цифра класса, запросы)."""
    for key in (
        'waiting_for_teacher_search', 'waiting_for_room_search',
        'waiting_for_teacher_search_at', 'waiting_for_room_search_at',
        'class_digit', 'teacher_search_query', 'room_search_query',
    ):
        context.user_data.pop(key, None)


def clear_search_flags(context) -> None:
    """Сбрасывает все «залипающие» флаги ожидания поиска (и их timestamp'ы).

    Флаги `waiting_for_*` в user_data ставятся при открытии ввода поиска
    преподавателя/кабинета и сбрасываются в class_schedule только когда
    пользователь что-то напечатал. Если же он вышел в меню кнопкой, флаг
    остаётся, и любой следующий текст интерпретируется как поиск. Вызов
    этого хелпера в точках входа в меню устраняет залипание.
    """
    for kind in _SEARCH_KINDS:
        context.user_data.pop(f'waiting_for_{kind}_search', None)
        context.user_data.pop(f'waiting_for_{kind}_search_at', None)


def set_search_flag(user_data: dict, kind: str) -> None:
    """Ставит флаг ожидания поиска `kind`, сбрасывая все sibling-флаги.

    Переключение teacher↔room не должно оставлять активным второй флаг:
    иначе следующее текстовое сообщение уйдёт не в тот поиск. Рядом с флагом
    кладём timestamp для проверки TTL.
    """
    for other in _SEARCH_KINDS:
        user_data.pop(f'waiting_for_{other}_search', None)
        user_data.pop(f'waiting_for_{other}_search_at', None)
    user_data[f'waiting_for_{kind}_search'] = True
    user_data[f'waiting_for_{kind}_search_at'] = time.time()


def search_flag_active(user_data: dict, kind: str, ttl: int = SEARCH_FLAG_TTL) -> bool:
    """True, если флаг поиска `kind` стоит и не устарел.

    Обратная совместимость: если timestamp отсутствует (старые сессии или
    тесты, выставляющие только флаг), считаем флаг активным. Устаревший флаг
    снимается здесь же — текст пойдёт по обычной ветке класса.
    """
    flag = f'waiting_for_{kind}_search'
    if not user_data.get(flag):
        return False

    ts_key = f'waiting_for_{kind}_search_at'
    ts = user_data.get(ts_key)
    if ts is not None and time.time() - ts > ttl:
        user_data.pop(flag, None)
        user_data.pop(ts_key, None)
        return False
    return True


def paginate(items: list[str], page: int, per_page: int = 30) -> tuple:
    """Разбивает список на страницы; возвращает (страница, список_на_странице).

    Нормализует page в допустимые границы (0..total_pages-1), чтобы избежать
    пустых/несуществующих страниц.
    """
    total = len(items)
    total_pages = (total + per_page - 1) // per_page if total else 1

    if page < 0:
        page = 0
    elif total_pages > 0 and page >= total_pages:
        page = max(total_pages - 1, 0)

    start = page * per_page
    end = min(start + per_page, total)
    return page, items[start:end]


async def edit_long_message(
    update, context, query, text: str,
    reply_markup=None, parse_mode: str | None = 'Markdown',
):
    """Редактирует сообщение по callback_query, разбивая длинный текст.

    Первая часть редактирует исходное сообщение (с reply_markup), остальные
    отправляются reply-сообщениями в тот же чат.
    """
    chunks = split_long_message(text)
    if not chunks:
        return

    if len(chunks) == 1:
        await safe_edit_message(query, chunks[0], reply_markup=reply_markup, parse_mode=parse_mode)
        return

    await safe_edit_message(query, _mark_chunk(chunks[0], 1, len(chunks)),
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
    update, context, text: str, parse_mode: str | None = 'Markdown',
    copy_text: str | None = None,
):
    """Отправляет длинное сообщение reply-сообщениями, разбивая по лимиту.

    copy_text: если задано и ≤256 символов — к первому сообщению добавляется
    кнопка «📋 Скопировать» (CopyTextButton, Bot API 7.4+).
    """
    chunks = split_long_message(text)
    if not chunks:
        return

    reply_markup = None
    if copy_text and len(copy_text) <= MAX_COPY_TEXT_LENGTH:
        reply_markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("📋 Скопировать", copy_text=CopyTextButton(text=copy_text))
        ]])

    for i, chunk in enumerate(chunks, start=1):
        markup = reply_markup if i == 1 else None
        await update.message.reply_text(
            _mark_chunk(chunk, i, len(chunks)),
            parse_mode=parse_mode,
            reply_markup=markup,
            disable_web_page_preview=True,
        )
