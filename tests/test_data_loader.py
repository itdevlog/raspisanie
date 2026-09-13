"""Регрессия: вложенные ретраи не множатся."""
import logging

import httpx

from core.data_loader import DataLoader


class _FakeResponse:
    def __init__(self, text='', status_code=200):
        self.text = text
        self.status_code = status_code

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

    def get(self, url, timeout=None):
        self.calls.append((url, timeout))
        return _FakeResponse(self.text, self.status)

    def close(self):
        pass

    headers: dict = {}


class _CountingLoader(DataLoader):
    def __init__(self):
        super().__init__()
        self.filename_calls = 0

    def get_current_filename(self, check_url, max_retries=None):
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
