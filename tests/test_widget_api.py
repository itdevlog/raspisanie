# tests/test_widget_api.py
"""Тесты API виджета PWA."""
from fastapi.testclient import TestClient


def test_widget_endpoint_requires_valid_user_id():
    """Widget endpoint требует валидный user_id (int)."""
    from web.api import create_app

    class FakeUserService:
        def get_user_school(self, uid): return 'school_133'
        def get_user_class(self, uid, sid): return '9А'

    services = {
        'bot_data': {
            'user_service': FakeUserService(),
            'schools_data': {}
        }
    }
    app = create_app(services)
    client = TestClient(app)

    # Невалидный user_id (строка вместо int) — 422
    response = client.get('/api/widget/abc')
    assert response.status_code == 422


def test_widget_returns_schedule_structure():
    """Widget возвращает правильную структуру."""
    from web.api import create_app

    class FakeUserService:
        def get_user_school(self, uid): return 'school_133'
        def get_user_class(self, uid, sid): return '5А'

    services = {
        'bot_data': {
            'user_service': FakeUserService(),
            'schools_data': {
                'school_133': {
                    'CLASSES': {'c1': '5А'},
                    'TEACHERS': {'t1': 'Иванов'},
                    'ROOMS': {'r1': '101'},
                    'SUBJECTS': {'s1': 'Математика'},
                    'PERIODS': {'p1': {'b': '01.09.2026', 'e': '31.05.2027'}},
                    'LESSON_TIMES': {'1': ['08:00', '08:45'], '2': ['09:00', '09:45']},
                    'LESSONSINDAY': 6,
                    'CLASS_SCHEDULE': {
                        'p1': {'c1': {
                            '101': {'s': ['s1'], 't': ['t1'], 'r': ['r1']},
                            '102': {'s': ['s1'], 't': ['t1'], 'r': ['r1']}
                        }}
                    },
                    'CLASS_EXCHANGE': {},
                }
            }
        }
    }

    app = create_app(services)
    client = TestClient(app)

    response = client.get('/api/widget/123456')
    assert response.status_code == 200

    data = response.json()
    assert 'class' in data
    assert data['class'] == '5А'
    assert 'lessons' in data
    assert isinstance(data['lessons'], list)
    assert 'date' in data
    assert 'exchanges_count' in data


def test_widget_user_not_found():
    """Widget возвращает 404 для неизвестного пользователя."""
    from web.api import create_app

    class FakeUserService:
        def get_user_school(self, uid): return None
        def get_user_class(self, uid, sid): return None

    services = {
        'bot_data': {
            'user_service': FakeUserService()
        }
    }

    app = create_app(services)
    client = TestClient(app)

    response = client.get('/api/widget/999999')
    assert response.status_code == 404
