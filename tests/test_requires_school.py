# tests/test_requires_school.py
"""Юнит-тесты декоратора @requires_school."""
import asyncio
from types import SimpleNamespace

from handlers.common.requires_school import requires_school

pytest_plugins = []


class FakeUserService:
    def __init__(self, school_id):
        self.school_id = school_id

    def get_user_school(self, uid):
        return self.school_id


def _update(query=None, msg=None):
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=1),
        callback_query=query,
        effective_message=msg,
    )


def _context(has_user_service=True, schools=None, school_id="school_133"):
    bot_data = {}
    if has_user_service:
        bot_data['user_service'] = FakeUserService(school_id)
        # None -> default present school; {} -> explicitly empty (no schools)
        bot_data['schools_data'] = {'school_133': {'X': 1}} if schools is None else schools
    return SimpleNamespace(bot_data=bot_data, user_data={})


async def _run(handler, update, context, *args):
    return await handler(update, context, *args)


def test_no_user_service_returns_none():
    calls = []

    @requires_school
    async def h(update, ctx, **kw):
        calls.append(1)
        return 'ok'

    r = asyncio.run(_run(h, _update(), _context(has_user_service=False)))
    assert r is None
    assert calls == []


def test_no_school_data_returns_none():
    calls = []

    @requires_school
    async def h(update, ctx, **kw):
        calls.append(1)
        return 'ok'

    r = asyncio.run(_run(h, _update(), _context(schools={})))
    assert r is None
    assert calls == []


def test_happy_path_injects_context():
    seen = {}

    @requires_school
    async def h(update, ctx, custom=None):
        seen['school_data'] = ctx.school_data
        seen['current_school_id'] = ctx.current_school_id
        seen['custom'] = custom
        return 'ok'

    r = asyncio.run(h(_update(), _context(), custom='abc'))
    assert r == 'ok'
    assert seen['school_data'] == {'X': 1}
    assert seen['current_school_id'] == 'school_133'
    assert seen['custom'] == 'abc'
