"""Versioned local persistence. UI and domain code do not access SQLite directly."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from migrations import upgrade
from domain import validate


class Conflict(Exception):
    pass


class Repository:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / 'personal.sqlite3'
        self.on_saved = None
        with self.connect() as c:
            c.execute('PRAGMA journal_mode=WAL')
            c.execute('CREATE TABLE IF NOT EXISTS spaces (name TEXT PRIMARY KEY, revision INTEGER NOT NULL, body TEXT NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS snapshots (id INTEGER PRIMARY KEY, space TEXT, revision INTEGER, body TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP)')
            seed_path = Path(__file__).parent / 'seed.json'
            if not seed_path.exists():
                seed_path = Path(__file__).parent / 'seed.example.json'
            seed = validate(upgrade(json.loads(seed_path.read_text())))
            c.execute('INSERT OR IGNORE INTO spaces VALUES (?, ?, ?)', ('main', 1, json.dumps(seed, ensure_ascii=False)))
            for name, rev, body in c.execute('SELECT name,revision,body FROM spaces').fetchall():
                old = json.loads(body)
                if old.get('schemaVersion') in (1, 2, 3, 4, 5, 6, 7):
                    updated = validate(upgrade(old))
                    backup = self.root / ('before-v8-' + name + '.json')
                    if not backup.exists():
                        backup.write_text(body)
                    c.execute('INSERT INTO snapshots(space,revision,body) VALUES (?,?,?)', (name,rev,body))
                    c.execute('UPDATE spaces SET revision=?,body=? WHERE name=?', (rev+1,json.dumps(updated,ensure_ascii=False),name))

    @contextmanager
    def connect(self):
        c = sqlite3.connect(self.db, timeout=10)
        try:
            c.execute('PRAGMA foreign_keys=ON')
            with c:
                yield c
        finally:
            c.close()

    def read(self, space):
        with self.connect() as c:
            if space == 'lab':
                c.execute("INSERT OR IGNORE INTO spaces SELECT 'lab', 1, body FROM spaces WHERE name='main'")
            row = c.execute('SELECT revision, body FROM spaces WHERE name=?', (space,)).fetchone()
        return {'revision': row[0], 'state': json.loads(row[1])}

    def save(self, space, revision, state):
        body = json.dumps(state, ensure_ascii=False)
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT revision, body FROM spaces WHERE name=?', (space,)).fetchone()
            if not row or row[0] != revision:
                raise Conflict('另一窗口已保存更新，请重新载入后重试。')
            c.execute('INSERT INTO snapshots(space,revision,body) VALUES (?,?,?)', (space, row[0], row[1]))
            c.execute('UPDATE spaces SET revision=?,body=? WHERE name=?', (revision + 1, body, space))
            c.execute('DELETE FROM snapshots WHERE space=? AND id NOT IN (SELECT id FROM snapshots WHERE space=? ORDER BY id DESC LIMIT 100)', (space, space))
        if self.on_saved:
            self.on_saved()
        return revision + 1

    def backups(self, space):
        with self.connect() as c:
            return [dict(zip(('id', 'revision', 'created'), x)) for x in c.execute('SELECT id,revision,created FROM snapshots WHERE space=? ORDER BY id DESC LIMIT 20', (space,))]

    def snapshot(self, space, identifier):
        with self.connect() as c:
            row = c.execute('SELECT body FROM snapshots WHERE space=? AND id=?', (space, identifier)).fetchone()
            if row is None:
                raise ValueError('快照不存在')
            return json.loads(row[0])
