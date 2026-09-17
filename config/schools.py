import json
import logging
import os
from pathlib import Path
from typing import Any, Mapping, cast

logger = logging.getLogger(__name__)

# Встроенная конфигурация поддерживаемых школ. Может быть дополнена/переопределена
# необязательным внешним JSON-файлом (env SCHOOLS_CONFIG_FILE).
_BUILTIN_SCHOOLS_CONFIG: dict[str, dict] = {
    "school_133": {
        "id": "school_133",
        "name": "МАОУ СОШ №133",
        "city": "Екатеринбург",
        "check_url": "https://raspisanie.nikasoft.ru/check/55812556.html",
        "base_url": "https://raspisanie.nikasoft.ru/static/public/",
        "active": True
    },
    "school_181": {
        "id": "school_181",
        "name": "МАОУ СОШ №181",
        "city": "Екатеринбург",
        "check_url": "https://raspisanie.nikasoft.ru/check/32911315.html",
        "base_url": "https://raspisanie.nikasoft.ru/static/public/",
        "active": True
    }
}

# Школа по умолчанию
DEFAULT_SCHOOL_ID = "school_133"


def _load_schools_config(config_path: str | None = None) -> dict[str, dict]:
    """Возвращает конфиг школ: встроенный + необязательный внешний JSON.

    Если задан `config_path` (или env `SCHOOLS_CONFIG_FILE`), файл читается как
    JSON-объект `{school_id: {...}}`. Внешние записи переопределяют одноимённые
    встроенные, остальные встроенные сохраняются. Любая ошибка (файл отсутствует,
    невалидный JSON, не объект) — warning и тихий откат к встроенному конфигу,
    чтобы опечатка в пути не роняла бота.

    Относительный путь резолвится от текущего рабочего каталога — так же, как
    DB_PATH/CACHE_PATH/LOG_FILE в config/config.py.
    """
    merged = {school_id: dict(data) for school_id, data in _BUILTIN_SCHOOLS_CONFIG.items()}

    raw = os.getenv('SCHOOLS_CONFIG_FILE', '') if config_path is None else config_path
    raw = (raw or '').strip()
    if not raw:
        return merged

    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path

    if not path.is_file():
        logger.warning(
            "SCHOOLS_CONFIG_FILE=%s не найден — используется встроенный конфиг школ", raw
        )
        return merged

    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        logger.warning(
            "SCHOOLS_CONFIG_FILE=%s не читается (%s) — используется встроенный конфиг школ",
            raw,
            exc,
        )
        return merged

    if not isinstance(data, dict):
        logger.warning(
            "SCHOOLS_CONFIG_FILE=%s должен содержать JSON-объект — используется встроенный конфиг школ",
            raw,
        )
        return merged

    for school_id, school_data in data.items():
        if isinstance(school_data, dict):
            merged[str(school_id)] = school_data
        else:
            logger.warning(
                "SCHOOLS_CONFIG_FILE=%s: запись %r пропущена (ожидался объект)", raw, school_id
            )
    return merged


# Итоговый конфиг школ (возможно, расширенный внешним файлом).
SCHOOLS_CONFIG: dict[str, dict] = _load_schools_config()


def get_display_name(school_id: str, school_data: Mapping[str, Any]) -> str:
    """Возвращает отображаемое имя школы.

    Использует переданный school_data['SCHOOL_NAME'], но устойчив к пустой строке
    (в выгрузке Nikasoft у школы 181 ключ есть, а значение — ''). В этом случае
    падает на имя из конфигурации, а при отсутствии школы — на school_id.
    """
    raw_name = (school_data or {}).get('SCHOOL_NAME')
    if raw_name:
        return raw_name
    config_name = (SCHOOLS_CONFIG.get(school_id) or {}).get('name')
    return cast(str, config_name) if config_name else school_id


def get_school_by_id(school_id: str) -> dict:
    """Возвращает конфиг школы по id или {} — единая точка поиска школы.

    Раньше поиск по SCHOOLS_CONFIG в ручную дублировался в ~6 местах.
    """
    return SCHOOLS_CONFIG.get(school_id, {})
