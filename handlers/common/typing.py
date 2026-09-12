"""Хелперы типизации для сужения Optional-полей PTB (mypy)."""
from telegram import CallbackQuery, Message, Update, User


def require_user(update: Update) -> User:
    """Возвращает update.effective_user (не None для user-апдейтов)."""
    user = update.effective_user
    assert user is not None
    return user


def require_message(update: Update) -> Message:
    """Возвращает update.effective_message (не None для message-апдейтов)."""
    message = update.effective_message
    assert message is not None
    return message


def require_query(update: Update) -> CallbackQuery:
    """Возвращает update.callback_query (не None для callback-апдейтов)."""
    query = update.callback_query
    assert query is not None
    return query


def require_user_data(context) -> dict:
    """Возвращает context.user_data как обычный dict (не None)."""
    data = context.user_data
    assert data is not None
    return data
