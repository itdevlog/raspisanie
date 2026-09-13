# web/api.py
"""REST API Mini App: читает живые bot_data (один процесс с ботом)."""
import os
from datetime import datetime

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from config.config import Config, get_timezone
from config.schools import SCHOOLS_CONFIG
from services.room_service import RoomService
from services.schedule_exceptions import EntityNotFoundError, PeriodNotFoundError
from services.schedule_service import ScheduleService
from services.teacher_service import TeacherService

from .auth import get_user_from_init_data


def _school_or_404(services: dict, school_id: str) -> dict:
    schools_data = services['bot_data'].get('schools_data', {})
    school_data = schools_data.get(school_id)
    if not school_data:
        raise HTTPException(404, f"Школа '{school_id}' не найдена")
    return school_data


def _service_for(kind: str, school_data: dict):
    if kind == 'class':
        return ScheduleService(school_data)
    if kind == 'teacher':
        return TeacherService(school_data)
    if kind == 'room':
        return RoomService(school_data)
    raise HTTPException(404, f"Неизвестный тип расписания '{kind}'")


def _now() -> datetime:
    return datetime.now(get_timezone())


def _parse_date_or_none(date_str: str | None) -> datetime:
    if not date_str:
        return _now()
    try:
        return datetime.strptime(date_str, '%d.%m.%Y').replace(tzinfo=get_timezone())
    except ValueError:
        raise HTTPException(422, "Некорректная дата; ожидается dd.mm.YYYY") from None


def create_app(services: dict) -> FastAPI:
    app = FastAPI(title="Schedule Bot Mini App API", docs_url=None, redoc_url=None)

    @app.get('/healthz')
    async def healthz():
        return {'status': 'ok'}

    @app.get('/api/schools')
    async def schools():
        schools_data = services['bot_data'].get('schools_data', {})
        return {'schools': [
            {'id': sid, 'name': cfg.get('name'), 'loaded': sid in schools_data}
            for sid, cfg in SCHOOLS_CONFIG.items() if cfg.get('active', True)
        ]}

    @app.get('/api/{school_id}/classes')
    async def classes(school_id: str):
        svc = ScheduleService(_school_or_404(services, school_id))
        return {'classes': await run_in_threadpool(svc.get_available_classes)}

    @app.get('/api/{school_id}/teachers')
    async def teachers(school_id: str):
        svc = TeacherService(_school_or_404(services, school_id))
        return {'teachers': await run_in_threadpool(svc.get_available_teachers)}

    @app.get('/api/{school_id}/rooms')
    async def rooms(school_id: str):
        svc = RoomService(_school_or_404(services, school_id))
        return {'rooms': await run_in_threadpool(svc.get_available_rooms)}

    @app.get('/api/{school_id}/schedule/{kind}/{name}')
    async def schedule_day(school_id: str, kind: str, name: str, date: str | None = None):
        svc = _service_for(kind, _school_or_404(services, school_id))
        try:
            return await run_in_threadpool(svc.get_day, name, _parse_date_or_none(date))
        except EntityNotFoundError as e:
            raise HTTPException(404, e.message) from e
        except PeriodNotFoundError as e:
            raise HTTPException(422, e.message) from e

    @app.get('/api/{school_id}/schedule/{kind}/{name}/week')
    async def schedule_week(school_id: str, kind: str, name: str, offset: int = Query(0, ge=-2, le=2)):
        svc = _service_for(kind, _school_or_404(services, school_id))
        try:
            return {'days': await run_in_threadpool(svc.get_week, name, offset)}
        except EntityNotFoundError as e:
            raise HTTPException(404, e.message) from e

    @app.get('/api/{school_id}/search')
    async def search(school_id: str, q: str = Query(..., min_length=1, max_length=80)):
        school_data = _school_or_404(services, school_id)
        return {
            'teachers': await run_in_threadpool(TeacherService(school_data).search_teachers, q),
            'rooms': await run_in_threadpool(RoomService(school_data).search_rooms, q),
        }

    @app.get('/api/{school_id}/free-rooms')
    async def free_rooms(school_id: str, date: str | None = None,
                         lesson: int = Query(..., ge=1, le=12)):
        school_data = _school_or_404(services, school_id)
        svc = RoomService(school_data)
        return {'free_rooms': await run_in_threadpool(svc.get_free_rooms, _parse_date_or_none(date), lesson)}

    @app.get('/api/me')
    async def me(x_telegram_init_data: str | None = Header(None)):
        token = (services.get('config') or Config()).TELEGRAM_TOKEN or ''
        user = get_user_from_init_data(x_telegram_init_data, token) if x_telegram_init_data else None
        user_service = services['bot_data'].get('user_service')
        school_id = user_service.get_user_school(user['id']) if user and user_service else None
        class_name = user_service.get_user_class(user['id'], school_id) if user and user_service else None
        return {'user': user, 'school_id': school_id, 'class_name': class_name}

    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    if os.path.isdir(static_dir):
        app.mount('/', StaticFiles(directory=static_dir, html=True), name='static')

    return app
