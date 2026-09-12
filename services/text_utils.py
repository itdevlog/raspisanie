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


def short_name(full_name: str) -> str:
    """«Фамилия Имя Отчество» → «Фамилия И.О.» (неизменное — как есть).

    Несколько преподавателей через запятую сокращаются по отдельности.
    Скрывает обрезанные на стороне Nikasoft ФИО («Александровн...»).
    """
    if not full_name:
        return full_name
    parts = [p.strip() for p in full_name.split(',')]
    result = []
    for part in parts:
        words = part.split()
        if len(words) >= 3:
            initials = ''.join(f"{w[0]}." for w in words[1:])
            result.append(f"{words[0]} {initials}")
        else:
            result.append(part)
    return ', '.join(result)
