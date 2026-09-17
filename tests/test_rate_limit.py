"""Тесты in-memory rate limiter-а и middleware Mini App."""
from fastapi.testclient import TestClient

from web.api import create_app
from web.rate_limit import RateLimiter


def test_allows_up_to_limit_then_blocks():
    limiter = RateLimiter(max_requests=3, window_seconds=60.0)
    assert limiter.allow('ip', now=0.0) is True
    assert limiter.allow('ip', now=1.0) is True
    assert limiter.allow('ip', now=2.0) is True
    assert limiter.allow('ip', now=3.0) is False


def test_window_slides_with_time():
    limiter = RateLimiter(max_requests=2, window_seconds=10.0)
    assert limiter.allow('ip', now=0.0) is True
    assert limiter.allow('ip', now=1.0) is True
    assert limiter.allow('ip', now=2.0) is False
    assert limiter.allow('ip', now=11.0) is True


def test_keys_are_independent():
    limiter = RateLimiter(max_requests=1, window_seconds=60.0)
    assert limiter.allow('a', now=0.0) is True
    assert limiter.allow('b', now=0.0) is True
    assert limiter.allow('a', now=1.0) is False
    assert limiter.allow('b', now=1.0) is False


def test_disabled_when_limit_is_zero():
    limiter = RateLimiter(max_requests=0, window_seconds=60.0)
    for i in range(1000):
        assert limiter.allow('ip', now=float(i)) is True


def test_cleanup_removes_empty_keys():
    limiter = RateLimiter(max_requests=1, window_seconds=10.0)
    assert limiter.allow('a', now=0.0) is True
    assert limiter.allow('b', now=0.0) is True
    assert set(limiter._hits) == {'a', 'b'}
    limiter.cleanup(now=0.5)
    assert set(limiter._hits) == {'a', 'b'}
    limiter.cleanup(now=100.0)
    assert limiter._hits == {}


def test_allow_evicts_stale_keys_without_external_cleanup():
    limiter = RateLimiter(max_requests=1, window_seconds=10.0)
    limiter._sweep_every = 3
    assert limiter.allow('old1', now=0.0) is True
    assert limiter.allow('old2', now=0.0) is True
    assert limiter.allow('new', now=100.0) is True
    assert set(limiter._hits) == {'new'}


def _school():
    return {'SCHOOL_NAME': 'Тест', 'CLASSES': {}, 'SUBJECTS': {}, 'PERIODS': {}}


def _client(**kwargs):
    bot_data = {'schools_data': {'school_133': _school()}}
    return TestClient(create_app({'bot_data': bot_data}, **kwargs))


def test_api_returns_429_above_limit():
    client = _client(rate_limit=3, widget_rate_limit=3, window_seconds=60.0)
    for _ in range(3):
        assert client.get('/api/schools').status_code == 200
    r = client.get('/api/schools')
    assert r.status_code == 429
    assert r.json() == {'detail': 'Слишком много запросов'}


def test_healthz_is_not_limited():
    client = _client(rate_limit=2, widget_rate_limit=2, window_seconds=60.0)
    for _ in range(20):
        assert client.get('/healthz').status_code == 200


def test_widget_has_separate_stricter_limit():
    client = _client(rate_limit=10, widget_rate_limit=2, window_seconds=60.0)
    assert client.get('/api/schools').status_code == 200
    assert client.get('/api/schools').status_code == 200
    assert client.get('/api/schools').status_code == 200
    assert client.get('/api/widget/1').status_code in (403, 200)
    assert client.get('/api/widget/1').status_code in (403, 200)
    assert client.get('/api/widget/1').status_code == 429
