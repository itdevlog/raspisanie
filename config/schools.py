# Конфигурация поддерживаемых школ
SCHOOLS_CONFIG = {
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


def get_display_name(school_id: str, school_data: dict) -> str:
    """Возвращает отображаемое имя школы.

    Использует переданный school_data['SCHOOL_NAME'], но устойчив к пустой строке
    (в выгрузке Nikasoft у школы 181 ключ есть, а значение — ''). В этом случае
    падает на имя из конфигурации, а при отсутствии школы — на school_id.
    """
    raw_name = (school_data or {}).get('SCHOOL_NAME')
    if raw_name:
        return raw_name
    config_name = (SCHOOLS_CONFIG.get(school_id) or {}).get('name')
    return config_name or school_id


def get_school_by_id(school_id: str) -> dict:
    """Возвращает конфиг школы по id или {} — единая точка поиска школы.

    Раньше поиск по SCHOOLS_CONFIG в ручную дублировался в ~6 местах.
    """
    return SCHOOLS_CONFIG.get(school_id, {})