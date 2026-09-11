# tests/test_file_db.py
"""Юнит-тесты FileDB: битый файл (.corrupt бэкап), upsert, delete_one."""
import json
import os
import tempfile

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
    assert col.find_one({'user_id': 1})['name'] == 'B'
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
