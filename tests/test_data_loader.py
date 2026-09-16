"""Регрессия: вложенные ретраи не множатся."""
import logging

import httpx

from core.data_loader import DataLoader


class _FakeResponse:
    def __init__(self, text='', status_code=200, headers=None):
        self.text = text
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                'err',
                request=httpx.Request('GET', 'https://b/'),
                response=httpx.Response(self.status_code),
            )


class _FakeClient:
    def __init__(self, text='var NIKA={}', status=200):
        self.text = text
        self.status = status
        self.calls = []

    def get(self, url, timeout=None, headers=None):
        self.calls.append((url, timeout, headers))
        return _FakeResponse(self.text, self.status)

    def close(self):
        pass

    headers: dict = {}


class _CountingLoader(DataLoader):
    def __init__(self):
        super().__init__()
        self.filename_calls = 0

    def get_current_filename(self, check_url, max_retries=None, client=None):
        # Эмулируем внутренний слой ретраев реального метода: он делает
        # max_retries попыток. Так видно, что вложенные ретраи множатся,
        # если внешний цикл не ограничивает внутренние вызовы.
        if max_retries is None:
            max_retries = self.config.MAX_RETRIES
        for _ in range(max_retries):
            self.filename_calls += 1
        return None  # всегда неудача


def _bare_loader():
    loader = DataLoader.__new__(DataLoader)
    loader.logger = logging.getLogger('t')
    return loader


def test_single_retry_layer():
    loader = _CountingLoader()
    loader.config.MAX_RETRIES = 3
    result = loader.load_school_data({'name': 'X', 'check_url': 'u', 'base_url': 'b'})
    assert result is None
    # ровно MAX_RETRIES попыток, а не MAX_RETRIES²
    assert loader.filename_calls == 3


def test_download_parses_nika_var():
    loader = _bare_loader()
    loader.session = _FakeClient(text='var NIKA={"SCHOOL_NAME": "X"};')
    data = loader.download_schedule_data('https://b/', 'f.js', max_retries=1)
    assert data == {'SCHOOL_NAME': 'X'}


def test_download_retries_on_http_error(monkeypatch):
    loader = _bare_loader()
    loader.session = _FakeClient(text='err', status=500)
    loader.config = type('C', (), {'MAX_RETRIES': 2})()
    monkeypatch.setattr('core.data_loader.time.sleep', lambda s: None)
    result = loader.download_schedule_data('https://b/', 'f.js', max_retries=1)
    assert result is None


class _EtagClient:
    """Отдаёт 200 с ETag, затем 304 при совпадении If-None-Match."""

    def __init__(self):
        self.etag = '"v1"'
        self.calls = []
        self.headers: dict = {}

    def get(self, url, timeout=None, headers=None):
        headers = headers or {}
        self.calls.append(headers.get('If-None-Match'))
        if headers.get('If-None-Match') == self.etag:
            return _FakeResponse('', status_code=304)
        return _FakeResponse('var NIKA={"a": 1};', status_code=200,
                             headers={'etag': self.etag})

    def close(self):
        pass


def test_download_uses_etag_and_returns_cached_on_304():
    loader = _bare_loader()
    loader.session = _EtagClient()
    first = loader.download_schedule_data('https://b/', 'f.js', max_retries=1)
    assert first == {'a': 1}
    second = loader.download_schedule_data('https://b/', 'f.js', max_retries=1)
    assert second == {'a': 1}
    # второе тело не скачивалось — вернулись из кэша по 304
    assert loader.session.calls == [None, '"v1"']


def test_cached_data_is_deep_copied():
    loader = _bare_loader()
    loader.session = _EtagClient()
    first = loader.download_schedule_data('https://b/', 'f.js', max_retries=1)
    first['a'] = 999
    second = loader.download_schedule_data('https://b/', 'f.js', max_retries=1)
    assert second == {'a': 1}


def test_parse_filename_variants():
    assert DataLoader._parse_filename('<a href="20261013_12345.js">') == '20261013_12345.js'
    assert DataLoader._parse_filename('<pre>20261013_999.js</pre>') == '20261013_999.js'
    assert DataLoader._parse_filename('no file here') is None


def test_load_all_schools_parallel(monkeypatch):
    """Все активные школы загружаются параллельно, неактивные пропускаются."""
    import core.data_loader as dl

    schools = {
        's1': {'name': 'Школа1', 'check_url': 'u1', 'base_url': 'b1', 'active': True},
        's2': {'name': 'Школа2', 'check_url': 'u2', 'base_url': 'b2', 'active': True},
        's3': {'name': 'Школа3', 'check_url': 'u3', 'base_url': 'b3', 'active': False},
    }
    monkeypatch.setattr(dl, 'SCHOOLS_CONFIG', schools)

    loader = DataLoader.__new__(DataLoader)
    loader.logger = logging.getLogger('t')
    loader.config = type('C', (), {'MAX_RETRIES': 1, 'MAX_PARALLEL_SCHOOLS': 4})()
    loader.session = _FakeClient()  # type: ignore[assignment]
    loader._ensure_cache()

    calls = []

    def fake_load(cfg, max_retries=None, client=None):
        calls.append(cfg['name'])
        return {'SCHOOL_NAME': cfg['name']}

    loader.load_school_data = fake_load  # type: ignore[method-assign]
    result = loader.load_all_schools_data()
    assert set(result) == {'s1', 's2'}
    assert sorted(calls) == ['Школа1', 'Школа2']  # s3 (inactive) не загружается


def test_load_all_schools_sequential(monkeypatch):
    """max_workers=1 — последовательная ветка тоже работает."""
    import core.data_loader as dl

    schools = {
        's1': {'name': 'Школа1', 'check_url': 'u1', 'base_url': 'b1', 'active': True},
        's2': {'name': 'Школа2', 'check_url': 'u2', 'base_url': 'b2', 'active': True},
    }
    monkeypatch.setattr(dl, 'SCHOOLS_CONFIG', schools)

    loader = DataLoader.__new__(DataLoader)
    loader.logger = logging.getLogger('t')
    loader.config = type('C', (), {'MAX_RETRIES': 1, 'MAX_PARALLEL_SCHOOLS': 1})()
    loader.session = _FakeClient()  # type: ignore[assignment]
    loader._ensure_cache()

    loader.load_school_data = lambda cfg, max_retries=None, client=None: {'name': cfg['name']}  # type: ignore[assignment]
    result = loader.load_all_schools_data()
    assert set(result) == {'s1', 's2'}
