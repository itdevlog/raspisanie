# services/text_utils.py
"""Общие текстовые хелперы."""


def escape_markdown(text: str) -> str:
    """Экранирует спецсимволы legacy Markdown (Telegram parse_mode='Markdown').

    Экранируем `*`, `_`, `` ` `` и `[ ] ( )` — без последних сообщение с
    такими символами падает с «Can't parse entities».
    """
    if not text:
        return text
    for ch in ('_', '*', '[', ']', '(', ')', '`'):
        text = text.replace(ch, '\\' + ch)
    return text
