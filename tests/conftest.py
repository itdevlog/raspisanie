import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

# PTB рекомендует заранее перейти на timedelta-семантику `RetryAfter.retry_after`.
# Без этого флага даже корректное `RetryAfter(timedelta(...))` вызывает
# PTBDeprecationWarning из самого конструктора (он читает свойство retry_after).
os.environ.setdefault('PTB_TIMEDELTA', '1')

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TZ_NAME = 'Asia/Yekaterinburg'


@pytest.fixture
def tz() -> ZoneInfo:
    """Часовой пояс, используемый в тестах расписаний."""
    return ZoneInfo(TZ_NAME)


@pytest.fixture
def make_db(tmp_path):
    """Фабрика временных FileDB в tmp_path с инициализированными коллекциями."""
    from database.file_db import FileDB
    from services.user_service import UserService

    counter = {'n': 0}

    def _make() -> FileDB:
        counter['n'] += 1
        db = FileDB(str(tmp_path / f'database_{counter["n"]}.json'))
        UserService(db)  # ensure collections
        return db

    return _make
