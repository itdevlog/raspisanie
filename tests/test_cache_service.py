# tests/test_cache_service.py
"""Юнит-тесты CacheService: потокобезопасность, TTL, лимит размера."""
import time

from services.cache_service import CacheService


def test_get_set_delete():
    c = CacheService(ttl=300)
    c.set('a', 1)
    assert c.get('a') == 1
    assert c.delete('a') is True
    assert c.get('a') is None


def test_ttl_expiry():
    c = CacheService(ttl=1)
    c.set('a', 1)
    time.sleep(1.05)
    assert c.get('a') is None


def test_max_entries_eviction():
    c = CacheService(ttl=300, max_entries=2)
    c.set('a', 1)
    c.set('b', 2)
    c.set('c', 3)  # превышаем лимит -> вытесняется самая старая
    assert len(c.cache) <= 2
    # 'a' удалена (самая старая)
    assert c.get('a') is None


def test_delete_prefix():
    c = CacheService(ttl=300)
    c.set('user_1_x', 1)
    c.set('user_1_y', 2)
    c.set('user_2_x', 3)
    c.delete_prefix('user_1_')
    assert c.get('user_1_x') is None
    assert c.get('user_1_y') is None
    assert c.get('user_2_x') == 3


def test_thread_safety():
    import threading
    c = CacheService(ttl=300)
    errors = []

    def worker(base):
        try:
            for i in range(200):
                c.set(f"{base}_{i}", i)
                c.get(f"{base}_{i}")
                c.delete_prefix(f"{base}_")
        except Exception as e:  # pragma: no cover
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
