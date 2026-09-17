# tests/test_common_handlers.py
"""Тесты мелких common-хендлеров и гвардов typing."""
from types import SimpleNamespace

import pytest

from handlers.common import school_info, status
from handlers.common.typing import (
    require_message,
    require_query,
    require_text,
    require_user,
    require_user_data,
    school_context,
)


class FakeMessage:
    def __init__(self, text='hi'):
        self.replies = []
        self.text = text

    async def reply_text(self, text, **kwargs):
        self.replies.append((text, kwargs))
        return self


class FakeQuery:
    def __init__(self):
        self.edits = []

    async def edit_message_text(self, text, **kwargs):
        self.edits.append((text, kwargs))


def _update(message=None, query=None):
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=1),
        effective_message=message,
        effective_chat=SimpleNamespace(id=100),
        callback_query=query,
    )


SCHOOL_DATA = {
    'SCHOOL_NAME': 'МАОУ СОШ №133',
    'CITY_NAME': 'Екатеринбург',
    'EXPORT_DATE': '01.09.2026',
    'EXPORT_TIME': '08:00:00',
    'HOMEPAGE_URL': 'https://example.org',
    'CLASSES': {'c1': '5а'},
    'TEACHERS': {'t1': 'Иванов'},
    'SUBJECTS': {'s1': 'Математика'},
    'ROOMS': {'r1': '101'},
}


def _school_context(school_data=None):
    return SimpleNamespace(
        bot_data={
            'user_service': SimpleNamespace(get_user_school=lambda uid: 'school_133'),
            'schools_data': {'school_133': school_data or SCHOOL_DATA},
        },
        user_data={},
    )


async def test_school_info_reply():
    msg = FakeMessage()
    await school_info.school_info_handler(_update(message=msg), _school_context())
    assert msg.replies
    text, kwargs = msg.replies[-1]
    assert 'МАОУ СОШ №133' in text
    assert 'Классов: 1' in text
    assert kwargs.get('parse_mode') == 'Markdown'


async def test_school_info_callback_edits_with_menu_button():
    q = FakeQuery()
    await school_info.school_info_handler(_update(query=q), _school_context())
    assert q.edits
    _text, kwargs = q.edits[-1]
    assert kwargs.get('reply_markup') is not None
    labels = [b.text for row in kwargs['reply_markup'].inline_keyboard for b in row]
    assert any('Главное меню' in label for label in labels)


async def test_status_no_schools():
    msg = FakeMessage()
    ctx = SimpleNamespace(bot_data={}, user_data={})
    await status.status_handler(_update(message=msg), ctx)  # type: ignore[arg-type]
    assert 'Нет загруженных данных школ' in msg.replies[-1][0]


async def test_status_with_school_details():
    msg = FakeMessage()
    ctx = SimpleNamespace(
        bot_data={'schools_data': {'school_133': SCHOOL_DATA}},
        user_data={},
    )
    await status.status_handler(_update(message=msg), ctx)  # type: ignore[arg-type]
    text = msg.replies[-1][0]
    assert 'Школы:' in text
    assert 'МАОУ СОШ №133' in text


def test_require_user_ok_and_missing():
    assert require_user(_update()).id == 1
    with pytest.raises(AssertionError):
        require_user(SimpleNamespace(effective_user=None))  # type: ignore[arg-type]


def test_require_message_ok_and_missing():
    msg = FakeMessage()
    assert require_message(_update(message=msg)) is msg
    with pytest.raises(AssertionError):
        require_message(_update(message=None))


def test_require_query_ok_and_missing():
    q = FakeQuery()
    assert require_query(_update(query=q)) is q
    with pytest.raises(AssertionError):
        require_query(_update(query=None))


def test_require_text_ok_and_missing():
    assert require_text(FakeMessage(text='abc')) == 'abc'  # type: ignore[arg-type]
    with pytest.raises(AssertionError):
        require_text(FakeMessage(text=None))  # type: ignore[arg-type]


def test_require_user_data_asserts():
    ctx = SimpleNamespace(user_data={'a': 1})
    assert require_user_data(ctx) == {'a': 1}
    with pytest.raises(AssertionError):
        require_user_data(SimpleNamespace(user_data=None))


def test_school_context_reads_injected_fields():
    ctx = SimpleNamespace(user_service='us', current_school_id='sid', school_data='sd')
    assert school_context(ctx) == ('us', 'sid', 'sd')  # type: ignore[arg-type]
