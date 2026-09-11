# tests/test_entity_menu.py
"""Юнит-тесты общих хелперов EntityMenuHandler (пагинация, resolve source)."""

from handlers.common.entity_menu import EntityConfig, EntityMenuHandler


def _make_handler():
    return EntityMenuHandler(EntityConfig(
        entity='entity',
        label_singular='item',
        label_plural='items',
        icon='📛',
        menu_title='Menu',
        search_input_hint='hint',
        search_example='eg',
        empty_data_msg='empty',
        button_truncate=10,
        state_full_key='full',
        state_search_key='search',
        search_query_key='search_query',
    ))


class FakeState:
    def __init__(self, search=None, full=None):
        self.store = {'search': search, 'full': full}

    def get_user_list(self, user_id, key):
        return self.store.get(key)


def test_resolve_source_prefers_search():
    h = _make_handler()
    st = FakeState(search=['a', 'b'], full=['x', 'y', 'a'])
    assert h._resolve_source(1, 'a', st) == ('search', 0)


def test_resolve_source_falls_back_to_full():
    h = _make_handler()
    st = FakeState(search=None, full=['x', 'a'])
    assert h._resolve_source(1, 'a', st) == ('full', 1)


def test_resolve_source_missing():
    h = _make_handler()
    st = FakeState(search=['a'], full=['b'])
    assert h._resolve_source(1, 'zzz', st) == ('full', None)
