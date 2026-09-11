# Конфигурация поддерживаемых школ
SCHOOLS_CONFIG = {
    "school_133": {
        "id": "school_133",
        "name": "МАОУ СОШ №133",
        "city": "Екатеринбург",
        "check_url": "https://raspisanie.nikasoft.ru/check/55812556.html",
        "base_url": "https://raspisanie.nikasoft.ru/static/public/",
        "active": True,
        "order": 1
    },
    "school_181": {
        "id": "school_181", 
        "name": "МАОУ СОШ №181",
        "city": "Екатеринбург",
        "check_url": "https://raspisanie.nikasoft.ru/check/32911315.html",
        "base_url": "https://raspisanie.nikasoft.ru/static/public/",
        "active": True,
        "order": 2
    }
}

# Школа по умолчанию
DEFAULT_SCHOOL_ID = "school_133"