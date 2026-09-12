# tests/test_messaging.py
"""Юнит-тесты для handlers/common/messaging.py — чистые функции разбивки сообщений."""

from typing import cast

from handlers.common.messaging import MAX_MESSAGE_LENGTH, paginate, split_long_message


def test_split_short_message():
    assert split_long_message("short") == ["short"]
    assert split_long_message("") == []


def test_split_keeps_together_below_limit():
    text = "\n".join(["x" * 1000] * 3)  # 3003 bytes + newlines < 4096
    chunks = split_long_message(text)
    assert chunks == [text]


def test_split_respects_line_boundaries():
    lines = ["y" * 1000] * 10  # total > 4096
    text = "\n".join(lines)
    for chunk in split_long_message(text):
        assert len(chunk) <= MAX_MESSAGE_LENGTH
        assert not chunk.startswith("\n")
    # Склейка не должна потерять/дублировать символы
    assert "".join(split_long_message(text)) == text


def test_split_single_long_line_with_spaces():
    text = " ".join(["word" * 100] * 50)
    for chunk in split_long_message(text, max_length=1000):
        assert len(chunk) <= 1000


def test_split_single_long_token_hard_cut():
    text = "a" * 5000
    chunks = split_long_message(text, max_length=1000)
    assert all(len(c) <= 1000 for c in chunks)
    assert "".join(chunks) == text


# --- paginate ---

def test_paginate_zero_one_many():
    assert paginate([], 0, 30) == (0, [])
    assert paginate(cast(list[str], list(range(1))), 0, 30)[1] == [0]
    assert paginate(cast(list[str], list(range(30))), 0, 30)[1] == list(range(30))
    assert paginate(cast(list[str], list(range(31))), 0, 30)[1] == list(range(30))
    assert paginate(cast(list[str], list(range(31))), 1, 30)[1] == [30]


def test_paginate_page_bounds():
    items = cast(list[str], list(range(100)))
    # page=-1 -> 0
    assert paginate(items, -1, 30)[0] == 0
    # page=total -> последняя валидная
    p, _ = paginate(items, 999, 30)
    assert p == 3  # 100/30 -> 4 страницы (0..3)
    assert paginate(items, 999, 30)[1] == list(range(90, 100))
