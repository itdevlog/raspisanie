import json
import logging
import os
import threading
import tempfile
import shutil
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class FileDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.RLock()
        self.data = self._load_data()

    def _load_data(self) -> Dict:
        """Загружает данные из файла; при битом файле сохраняет копию .corrupt и возвращает {}"""
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f"Error loading database: {e}")
                self._backup_corrupt()
                return {}
        return {}

    def _backup_corrupt(self):
        """Перед перезаписью повреждённого файла сохраняет его копию, чтобы не потерять данные.

        По умолчанию имя бэкапа — '<db_path>.corrupt'. Если такой файл уже существует,
        сдвигаем его в '<db_path>.corrupt.1', '.corrupt.2', … , чтобы не удалять более
        старые копии, потенциально более ценные.
        """
        try:
            if not os.path.exists(self.db_path):
                return
            backup_path = self.db_path + '.corrupt'
            counter = 1
            while os.path.exists(backup_path):
                backup_path = self.db_path + f'.corrupt.{counter}'
                counter += 1
            shutil.copy2(self.db_path, backup_path)
            logger.warning(f"Corrupt database backed up to {backup_path}")
        except OSError as e:
            logger.error(f"Failed to back up corrupt database {self.db_path}: {e}")

    def _save_data(self):
        """Атомарно сохраняет данные в файл через временный файл и rename"""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            # Пишем во временный файл в той же директории, чтобы rename был атомарным
            dir_name = os.path.dirname(self.db_path) or '.'
            fd, temp_path = tempfile.mkstemp(dir=dir_name, prefix='.file_db_tmp_', suffix='.json')
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    json.dump(self.data, f, ensure_ascii=False, indent=2, default=self._json_serializer)
                shutil.move(temp_path, self.db_path)
            except Exception:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                raise
        except Exception as e:
            logger.error(f"Error saving database: {e}")

    @staticmethod
    def _json_serializer(obj):
        """Функция для сериализации с обработкой специальных типов"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        else:
            # Для других несериализуемых объектов возвращаем строку
            return str(obj)

    def reload(self):
        """Перезагружает данные из файла (потокобезопасно)"""
        with self._lock:
            self.data = self._load_data()

    def get_collection(self, collection_name: str) -> 'Collection':
        """Возвращает коллекцию"""
        return Collection(self, collection_name)

class Collection:
    def __init__(self, db: FileDB, name: str):
        self.db = db
        self.name = name

        # Инициализируем коллекцию если её нет (потокобезопасно)
        with self.db._lock:
            if name not in self.db.data:
                self.db.data[name] = []

    def find_one(self, query: Dict) -> Optional[Dict]:
        """Находит один документ по запросу"""
        with self.db._lock:
            for doc in self.db.data[self.name]:
                if all(doc.get(k) == v for k, v in query.items()):
                    return self._clean_document(doc)
            return None

    def find(self, query: Dict = None) -> List[Dict]:
        """Находит все документы по запросу"""
        with self.db._lock:
            if query is None:
                return [self._clean_document(doc) for doc in self.db.data[self.name]]

            return [self._clean_document(doc) for doc in self.db.data[self.name]
                    if all(doc.get(k) == v for k, v in query.items())]

    def insert_one(self, document: Dict):
        """Вставляет один документ"""
        clean_doc = self._clean_document(document)
        with self.db._lock:
            self.db.data[self.name].append(clean_doc)
            self.db._save_data()

    def update_one(self, query: Dict, update: Dict, upsert: bool = False):
        """Обновляет один документ"""
        with self.db._lock:
            for doc in self.db.data[self.name]:
                if all(doc.get(k) == v for k, v in query.items()):
                    clean_update = self._clean_document(update)
                    doc.update(clean_update)
                    self.db._save_data()
                    return

            # Если документ не найден и upsert=True, создаем новый
            if upsert:
                new_doc = query.copy()
                clean_update = self._clean_document(update)
                new_doc.update(clean_update)
                clean_doc = self._clean_document(new_doc)
                self.db.data[self.name].append(clean_doc)
                self.db._save_data()

    def delete_one(self, query: Dict):
        """Удаляет один документ"""
        with self.db._lock:
            for i, doc in enumerate(self.db.data[self.name]):
                if all(doc.get(k) == v for k, v in query.items()):
                    del self.db.data[self.name][i]
                    self.db._save_data()
                    return
    
    def _clean_document(self, document: Dict) -> Dict:
        """Очищает документ от несериализуемых объектов"""
        cleaned = {}
        for key, value in document.items():
            if isinstance(value, (str, int, float, bool, type(None))):
                cleaned[key] = value
            elif isinstance(value, (list, tuple)):
                cleaned[key] = [self._clean_value(item) for item in value]
            elif isinstance(value, dict):
                cleaned[key] = self._clean_document(value)
            else:
                # Для других типов преобразуем в строку
                cleaned[key] = self._clean_value(value)
        return cleaned
    
    def _clean_value(self, value):
        """Очищает значение от несериализуемых объектов"""
        if isinstance(value, (str, int, float, bool, type(None))):
            return value
        elif isinstance(value, datetime):
            return value.isoformat()
        elif hasattr(value, '__dict__'):
            return str(value)  # Для объектов возвращаем строковое представление
        elif isinstance(value, (list, tuple)):
            return [self._clean_value(item) for item in value]
        elif isinstance(value, dict):
            return self._clean_document(value)
        else:
            return str(value)