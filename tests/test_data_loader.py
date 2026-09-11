"""Регрессия: вложенные ретраи не множатся."""
from core.data_loader import DataLoader


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


def test_single_retry_layer():
    loader = _CountingLoader()
    loader.config.MAX_RETRIES = 3
    result = loader.load_school_data({'name': 'X', 'check_url': 'u', 'base_url': 'b'})
    assert result is None
    # ровно MAX_RETRIES попыток, а не MAX_RETRIES²
    assert loader.filename_calls == 3
