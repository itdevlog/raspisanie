import copy
import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

from config.config import Config
from config.schools import SCHOOLS_CONFIG  # Добавить импорт
from services.school_types import SchoolData


class DataLoader:
    def __init__(self):
        self.config = Config()
        self.session = httpx.Client(headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.logger = logging.getLogger(__name__)
        # Условное кэширование HTTP: url -> {'etag', 'last_modified', 'data'}
        self._http_cache: dict[str, dict] = {}
        self._cache_lock = threading.Lock()

    def close(self):
        """Закрывает HTTP-сессию (держит пул соединений)."""
        try:
            self.session.close()
        except Exception as e:
            self.logger.error(f"Ошибка закрытия сессии: {e}")

    def _ensure_cache(self) -> None:
        """Ленивая инициализация кэша (устойчиво к __new__ без __init__)."""
        if not hasattr(self, '_http_cache'):
            self._http_cache = {}
        if not hasattr(self, '_cache_lock'):
            self._cache_lock = threading.Lock()

    def _conditional_headers(self, url: str) -> dict[str, str]:
        """Заголовки условного запроса (If-None-Match/If-Modified-Since) из кэша."""
        self._ensure_cache()
        with self._cache_lock:
            cached = self._http_cache.get(url)
        if not cached:
            return {}
        headers: dict[str, str] = {}
        if cached.get('etag'):
            headers['If-None-Match'] = cached['etag']
        if cached.get('last_modified'):
            headers['If-Modified-Since'] = cached['last_modified']
        return headers

    def _store_cache_headers(self, url: str, response) -> None:
        """Сохраняет ETag/Last-Modified ответа для последующих условных запросов."""
        headers = getattr(response, 'headers', None) or {}
        etag = headers.get('etag') if hasattr(headers, 'get') else None
        last_modified = headers.get('last-modified') if hasattr(headers, 'get') else None
        if not etag and not last_modified:
            return
        self._ensure_cache()
        with self._cache_lock:
            entry = self._http_cache.setdefault(url, {})
            if etag:
                entry['etag'] = etag
            if last_modified:
                entry['last_modified'] = last_modified

    def get_current_filename(self, check_url: str, max_retries: int | None = None,
                             client: httpx.Client | None = None) -> str | None:
        """Получает актуальное имя файла из check страницы с повторными попытками.

        Использует условные запросы (ETag/If-Modified-Since): если файл не
        изменился и пришёл 304, возвращается закэшированное имя файла.
        `client` позволяет передать общий потокобезопасный httpx.Client при
        параллельной загрузке школ.
        """
        if max_retries is None:
            max_retries = self.config.MAX_RETRIES
        session = client or self.session
        for attempt in range(max_retries):
            try:
                response = session.get(check_url, timeout=10,
                                       headers=self._conditional_headers(check_url))
                if getattr(response, 'status_code', 200) == 304:
                    with self._cache_lock:
                        cached = self._http_cache.get(check_url)
                        return cached.get('filename') if cached else None
                response.raise_for_status()

                filename = self._parse_filename(response.text)
                if filename:
                    self._store_cache_headers(check_url, response)
                    with self._cache_lock:
                        self._http_cache.setdefault(check_url, {})['filename'] = filename
                return filename

            except Exception as e:
                self.logger.warning(f"⚠️ Попытка {attempt + 1} не удалась для {check_url}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    return None
        return None

    @staticmethod
    def _parse_filename(text: str) -> str | None:
        """Извлекает имя JS-файла расписания из HTML check-страницы."""
        pattern = r'(\d+_\d+\.js)'
        match = re.search(pattern, text)
        if match:
            return match.group(1)

        # Альтернативный поиск в <pre> теге
        pre_match = re.search(r'<pre[^>]*>(.*?)</pre>', text, re.DOTALL)
        if pre_match:
            pre_content = pre_match.group(1).strip()
            file_match = re.search(pattern, pre_content)
            if file_match:
                return file_match.group(1)
        return None

    def download_schedule_data(self, base_url: str, filename: str, max_retries: int | None = None,
                               client: httpx.Client | None = None) -> SchoolData | None:
        """Скачивает и парсит данные расписания с повторными попытками.

        Если сервер ответил 304 Not Modified, возвращается копия ранее
        загруженных данных (если она есть в кэше). `client` позволяет передать
        общий потокобезопасный httpx.Client при параллельной загрузке школ.
        """
        if max_retries is None:
            max_retries = self.config.MAX_RETRIES
        session = client or self.session
        url = f"{base_url}{filename}"
        for attempt in range(max_retries):
            try:
                response = session.get(url, timeout=10,
                                       headers=self._conditional_headers(url))
                if getattr(response, 'status_code', 200) == 304:
                    with self._cache_lock:
                        cached = self._http_cache.get(url)
                        data = cached.get('data') if cached else None
                    if data is not None:
                        self.logger.info(f"ℹ️ Данные не изменились (304): {filename}")
                        return copy.deepcopy(data)
                    # Нет тела в кэше — повторяем без условных заголовков
                    response = session.get(url, timeout=10)
                response.raise_for_status()

                js_content = response.text
                if 'var NIKA=' not in js_content:
                    return None

                json_str = js_content.split('var NIKA=', 1)[1].strip()
                # Убираем возможную точку с запятой в конце
                if json_str.endswith(';'):
                    json_str = json_str[:-1]

                try:
                    data = json.loads(json_str)
                except json.JSONDecodeError as e:
                    # Искажённые данные — повторные запросы не помогут, выходим сразу
                    self.logger.error(f"Некорректный JSON в {url}: {e}")
                    return None

                self._store_cache_headers(url, response)
                with self._cache_lock:
                    self._http_cache.setdefault(url, {})['data'] = copy.deepcopy(data)
                return data

            except Exception as e:
                self.logger.warning(f"⚠️ Попытка {attempt + 1} не удалась для {filename}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    return None
        return None

    def load_school_data(self, school_config: dict, max_retries: int | None = None,
                         client: httpx.Client | None = None) -> SchoolData | None:
        """Полная загрузка данных для школы с повторными попытками"""
        if max_retries is None:
            max_retries = self.config.MAX_RETRIES
        school_name = school_config['name']
        started = time.time()

        for attempt in range(max_retries):
            self.logger.info(f"Попытка {attempt + 1} загрузки данных для {school_name}...")

            filename = self.get_current_filename(school_config['check_url'], max_retries=1,
                                                 client=client)
            if not filename:
                self.logger.warning(f"Не удалось получить имя файла для {school_name}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                else:
                    return None

            data = self.download_schedule_data(school_config['base_url'], filename,
                                               max_retries=1, client=client)
            if data:
                self.logger.info(
                    f"Данные для {school_name} успешно загружены за {time.time() - started:.1f}с")
                return data
            else:
                self.logger.warning(f"Не удалось загрузить данные для {school_name}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)

        return None

    def load_all_schools_data(self, max_workers: int | None = None) -> dict[str, SchoolData]:
        """Загружает данные всех активных школ.

        Школы загружаются параллельно через ThreadPoolExecutor (по умолчанию
        `MAX_PARALLEL_SCHOOLS`, 1 — последовательно). Один общий httpx.Client
        потокобезопасен и переиспользует пул соединений; каждый `load_school_data`
        изолирован (свой ключ кэша по URL), поэтому параллельный запуск безопасен.
        """
        if max_workers is None:
            max_workers = self.config.MAX_PARALLEL_SCHOOLS
        schools_data = {}
        failed_schools: list[str] = []
        active_schools = [
            (school_id, cfg) for school_id, cfg in SCHOOLS_CONFIG.items()
            if cfg.get('active', True)
        ]

        client = httpx.Client(headers=dict(self.session.headers))
        try:
            if max_workers <= 1 or len(active_schools) <= 1:
                results = [
                    (school_id, cfg, self.load_school_data(cfg, client=client))
                    for school_id, cfg in active_schools
                ]
            else:
                with ThreadPoolExecutor(max_workers=min(max_workers, len(active_schools))) as pool:
                    futures = [
                        (school_id, cfg,
                         pool.submit(self.load_school_data, cfg, None, client))
                        for school_id, cfg in active_schools
                    ]
                    results = []
                    for school_id, cfg, future in futures:
                        try:
                            results.append((school_id, cfg, future.result()))
                        except Exception as e:
                            self.logger.error(f"Ошибка загрузки школы {cfg['name']}: {e}")
                            results.append((school_id, cfg, None))

            for school_id, school_config, school_data in results:
                if school_data:
                    schools_data[school_id] = school_data
                    self.logger.info(f"✅ Данные для {school_config['name']} загружены")
                else:
                    self.logger.warning(f"❌ Не удалось загрузить данные для {school_config['name']}")
                    failed_schools.append(school_config['name'])
        finally:
            try:
                client.close()
            except Exception:
                pass

        if failed_schools:
            self.logger.warning(f"⚠️ Не удалось загрузить данные для {len(failed_schools)} школ: "
                                f"{', '.join(failed_schools)}")

        return schools_data
