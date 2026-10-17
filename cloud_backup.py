"""Consistent local snapshots, then atomic publication to a configured sync folder.
A successful publication is NOT proof that the cloud provider uploaded the file.
"""
from contextlib import closing
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
import threading
import uuid
import zipfile
from domain import validate

FORMAT = 1
PREFIX = 'council-'
PATTERN = re.compile(r'^council-\d{8}T\d{12}Z-[a-f0-9]{8}\.zip$')

def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('w', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

def inspect_database(path):
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)) as c:
        if c.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('数据库完整性检查失败')
        states = {}
        for space, revision, body in c.execute('SELECT name,revision,body FROM spaces'):
            if space not in ('main', 'lab'):
                raise ValueError('备份包含未知数据空间')
            states[space] = {'revision': revision, 'state': validate(json.loads(body))}
        if 'main' not in states:
            raise ValueError('备份缺少正式数据')
        # Reading historical rows also catches damaged snapshot pages.
        c.execute('SELECT COUNT(*), SUM(LENGTH(body)) FROM snapshots').fetchone()
    return states

def create_bundle(source, output, code_version='0.9-cloud1'):
    """SQLite online backup, including WAL, into an immutable verified ZIP."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='council-snapshot-') as tmp:
        db = Path(tmp) / 'personal.sqlite3'
        with closing(sqlite3.connect(Path(source).resolve().as_uri() + '?mode=ro', uri=True)) as a, closing(sqlite3.connect(db)) as b:
            a.backup(b, pages=256, sleep=.01)
        states = inspect_database(db)
        data = db.read_bytes()
        manifest = {'format': FORMAT, 'app': 'personal-council', 'createdAt': stamp(),
                    'codeVersion': code_version, 'schemaVersion': 8,
                    'databaseSha256': hashlib.sha256(data).hexdigest(),
                    'spaces': {k: {'revision': v['revision']} for k, v in states.items()}}
        temporary = output.with_name(output.name + '.tmp')
        try:
            with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as z:
                z.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
                z.writestr('personal.sqlite3', data)
                for space, value in states.items():
                    z.writestr(space + '.json', json.dumps(value['state'], ensure_ascii=False, indent=2))
                z.writestr('恢复说明.txt', '下载 GitHub 的 personal_council 程序，先双击“恢复数据.command”，选择本 ZIP；成功后双击“启动个人决策团.command”。完整步骤见程序中的 RECOVERY.md。不要解压后只复制某个 JSON 来代替全部数据。')
            with temporary.open('rb') as f:
                os.fsync(f.fileno())
            os.replace(temporary, output)
        finally:
            temporary.unlink(missing_ok=True)
    return manifest

def prune(directory):
    """Keep latest 20 + latest of each of 30 days + latest of 12 months."""
    files = sorted((p for p in Path(directory).iterdir() if PATTERN.fullmatch(p.name)), reverse=True)
    keep = set(files[:20])
    days, months = {}, {}
    for p in files:
        days.setdefault(p.name[8:16], p)
        months.setdefault(p.name[8:14], p)
    keep.update(list(days.values())[:30])
    keep.update(list(months.values())[:12])
    for p in files:
        if p not in keep:
            p.unlink()

class BackupManager:
    def __init__(self, repository, destination, delay=2, retry_delay=60):
        self.repo, self.destination = repository, Path(destination).expanduser().resolve()
        self.delay, self.retry_delay = delay, retry_delay
        self.lock, self.run_lock = threading.Lock(), threading.Lock()
        self.timer, self.pending, self.closed = None, False, False
        self.status_path = self.repo.root / 'cloud-backup-status.json'
        try:
            self.previous = json.loads(self.status_path.read_text())
        except (OSError, ValueError):
            self.previous = {}

    def status(self):
        with self.lock:
            return {**self.previous, 'configured': True, 'destination': str(self.destination),
                    'pending': self.pending, 'uploadConfirmed': False}

    def request(self):
        with self.lock:
            if self.closed:
                return
            self.pending = True
            if self.timer is None:
                self.timer = threading.Timer(self.delay, self._scheduled)
                self.timer.daemon = True
                self.timer.start()

    def _scheduled(self):
        with self.lock:
            self.timer = None
        self.run()

    def run(self):
        with self.run_lock:
            with self.lock:
                self.pending = False
            try:
                # Never silently create a replacement cloud root when a drive is absent.
                if not self.destination.is_dir():
                    raise ValueError('备份目录不可用，请检查 iCloud Drive')
                local = self.repo.root / 'auto-backup'
                name = PREFIX + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-' + uuid.uuid4().hex[:8] + '.zip'
                bundle = local / name
                manifest = create_bundle(self.repo.db, bundle)
                target = self.destination / name
                temporary = target.with_name('.' + name + '.partial')
                try:
                    with bundle.open('rb') as a, temporary.open('xb') as b:
                        shutil.copyfileobj(a, b)
                        b.flush()
                        os.fsync(b.fileno())
                    if hashlib.sha256(bundle.read_bytes()).digest() != hashlib.sha256(temporary.read_bytes()).digest():
                        raise ValueError('云盘文件夹副本校验失败')
                    os.replace(temporary, target)
                finally:
                    temporary.unlink(missing_ok=True)
                result = {'lastSuccess': stamp(), 'file': name, 'sha256': hashlib.sha256(bundle.read_bytes()).hexdigest(),
                          'revisions': manifest['spaces'], 'error': None, 'lastAttempt': stamp()}
                # A retention failure is surfaced separately; the new backup remains valid.
                try:
                    prune(self.destination)
                    prune(local)
                except OSError as e:
                    result['warning'] = '备份已生成，旧版本整理失败：' + str(e)
                with self.lock:
                    self.previous = result
                    atomic_json(self.status_path, result)
            except Exception as e:
                with self.lock:
                    self.previous = {**self.previous, 'error': str(e), 'lastAttempt': stamp()}
                    try:
                        atomic_json(self.status_path, self.previous)
                    except OSError:
                        pass
                    if not self.closed and self.timer is None:
                        self.pending = True
                        self.timer = threading.Timer(self.retry_delay, self._scheduled)
                        self.timer.daemon = True
                        self.timer.start()
            return self.status()

    def close(self):
        with self.lock:
            self.closed = True
            if self.timer:
                self.timer.cancel()
                self.timer = None
            pending = self.pending
        if pending:
            self.run()
        # Wait for an in-flight publication to finish before process exit.
        with self.run_lock:
            pass
