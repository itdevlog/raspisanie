# tests/test_file_db.py
"""Юнит-тесты FileDB: битый файл (.corrupt бэкап), upsert, delete_one."""
import json
import os
import tempfile
from typing import cast

from database.file_db import FileDB


def _mkdb():
    d = tempfile.mkdtemp()
    return os.path.join(d, 'database.json')


def test_corrupt_file_backed_up():
    db_path = _mkdb()
    with open(db_path, 'w', encoding='utf-8') as f:
        f.write('{broken json!!')
    db = FileDB(db_path)
    assert db.data == {}
    assert os.path.exists(db_path + '.corrupt')


def test_insert_and_upsert():
    db_path = _mkdb()
    db = FileDB(db_path)
    col = db.get_collection('users')
    col.update_one({'user_id': 1}, {'user_id': 1, 'name': 'A'}, upsert=True)
    col.update_one({'user_id': 1}, {'name': 'B'}, upsert=True)
    assert cast(dict, col.find_one({'user_id': 1}))['name'] == 'B'
    assert len(col.find({'user_id': 1})) == 1  # upsert не плодит дубли


def test_delete_one_only_matching():
    db_path = _mkdb()
    db = FileDB(db_path)
    col = db.get_collection('users')
    col.insert_one({'user_id': 1})
    col.insert_one({'user_id': 1})  # дубль для проверки delete_one
    col.delete_one({'user_id': 1})
    # delete_one должен удалить ОДИН документ, а не все
    assert len(col.find({'user_id': 1})) == 1


def test_persist_round_trip():
    db_path = _mkdb()
    db = FileDB(db_path)
    db.get_collection('users').insert_one({'user_id': 42, 'current_school': 'school_133'})
    # перечитываем из файла
    assert FileDB(db_path).data['users'][0]['user_id'] == 42


def test_save_data_returns_true_on_success():
    db_path = _mkdb()
    db = FileDB(db_path)
    assert db._save_data() is True


def test_update_one_returns_false_when_save_fails(monkeypatch):
    db_path = _mkdb()
    db = FileDB(db_path)
    col = db.get_collection('users')
    monkeypatch.setattr(db, '_save_data', lambda: False)
    assert col.update_one({'user_id': 1}, {'user_id': 1, 'name': 'A'}, upsert=True) is False


def test_save_data_creates_bak_backup():
    db_path = _mkdb()
    db = FileDB(db_path)
    col = db.get_collection('users')
    col.insert_one({'user_id': 1})
    assert not os.path.exists(db_path + '.bak')
    # Вторая запись должна оставить .bak с предыдущей целой версией
    col.insert_one({'user_id': 2})
    assert os.path.exists(db_path + '.bak')
    with open(db_path + '.bak', encoding='utf-8') as f:
        backup = json.load(f)
    assert [d['user_id'] for d in backup['users']] == [1]


def test_save_data_no_temp_files_left():
    db_path = _mkdb()
    db = FileDB(db_path)
    db.get_collection('users').insert_one({'user_id': 1})
    leftovers = [n for n in os.listdir(os.path.dirname(db_path)) if n.startswith('.file_db_tmp_')]
    assert leftovers == []


def test_bare_filename_does_not_crash():
    d = tempfile.mkdtemp()
    cwd = os.getcwd()
    try:
        os.chdir(d)
        db = FileDB('database.json')
        col = db.get_collection('users')
        assert col.insert_one({'user_id': 7}) is True
    finally:
        os.chdir(cwd)
