from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cloud_backup import create_bundle, BackupManager, prune
from recovery import restore

class CloudBackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.data = self.root / 'data'
        self.data.mkdir()
        self.db = self.data / 'personal.sqlite3'
        self.state = json.loads((Path(__file__).resolve().parents[1] / 'seed.example.json').read_text())
        with closing(sqlite3.connect(self.db)) as c:
            c.execute('PRAGMA journal_mode=WAL')
            c.execute('CREATE TABLE spaces(name TEXT PRIMARY KEY, revision INTEGER, body TEXT)')
            c.execute('CREATE TABLE snapshots(id INTEGER PRIMARY KEY, space TEXT, revision INTEGER, body TEXT, created TEXT)')
            for name in ('main', 'lab'):
                c.execute('INSERT INTO spaces VALUES(?,?,?)', (name, 3, json.dumps(self.state)))
            c.execute('INSERT INTO snapshots VALUES(1,?,?,?,?)', ('main', 2, json.dumps(self.state), '2026-01-01'))
            c.commit()
    def tearDown(self):
        self.tmp.cleanup()
    def test_live_wal_bundle_and_exact_restore(self):
        # Keep writer open: the committed new state is still in the WAL.
        writer = sqlite3.connect(self.db)
        try:
            changed = dict(self.state, requests=[{'id':'idea','title':'Test fixture','detail':'Round trip'}])
            writer.execute('UPDATE spaces SET revision=4, body=? WHERE name=?', (json.dumps(changed), 'main'))
            writer.commit()
            out = self.root / 'bundle.zip'
            create_bundle(self.db, out)
            target = self.root / 'restored'
            info = restore(out, target)
            self.assertEqual(info['spaces']['main']['revision'], 4)
            with closing(sqlite3.connect(target / 'personal.sqlite3')) as c:
                self.assertEqual(json.loads(c.execute("SELECT body FROM spaces WHERE name='main'").fetchone()[0]), changed)
                self.assertEqual(json.loads(c.execute("SELECT body FROM spaces WHERE name='lab'").fetchone()[0]), self.state)
                self.assertEqual(c.execute('SELECT COUNT(*) FROM snapshots').fetchone()[0], 1)
            with self.assertRaisesRegex(ValueError, '不是空'):
                restore(out, target)
        finally:
            writer.close()
    def test_corruption_is_rejected_before_target_creation(self):
        out = self.root / 'bundle.zip'
        create_bundle(self.db, out)
        broken = self.root / 'broken.zip'
        with zipfile.ZipFile(out) as a, zipfile.ZipFile(broken, 'w') as b:
            for name in a.namelist():
                data = a.read(name)
                b.writestr(name, data + b'broken' if name == 'personal.sqlite3' else data)
        with self.assertRaisesRegex(ValueError, '校验失败'):
            restore(broken, self.root / 'target')
        self.assertFalse((self.root / 'target').exists())
    def test_manager_success_failure_and_retry(self):
        cloud = self.root / 'cloud'
        cloud.mkdir()
        manager = BackupManager(SimpleNamespace(root=self.data, db=self.db), cloud, delay=.02, retry_delay=100)
        try:
            manager.request()
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline and not manager.status().get('lastSuccess'):
                time.sleep(.02)
            status = manager.status()
            self.assertTrue(status.get('lastSuccess'))
            self.assertIsNone(status['error'])
            self.assertFalse(status['uploadConfirmed'])
            self.assertTrue((cloud / status['file']).is_file())
            restore(cloud / status['file'], self.root / 'verified', verify_only=True)
            manager.destination = self.root / 'missing' / 'cloud'
            status = manager.run()
            self.assertIsNotNone(status['error'])
            self.assertTrue(status['lastSuccess'])
            self.assertFalse(manager.destination.exists())
            manager.destination = cloud
            self.assertIsNone(manager.run()['error'])
        finally:
            manager.close()
    def test_repository_commit_requests_backup_after_commit_only(self):
        from repository import Repository, Conflict
        repo = Repository(self.data)
        observed = []
        repo.on_saved = lambda: observed.append(repo.read('main')['revision'])
        before = repo.read('main')
        repo.save('main', before['revision'], before['state'])
        self.assertEqual(observed, [before['revision'] + 1])
        with self.assertRaises(Conflict):
            repo.save('main', before['revision'], before['state'])
        self.assertEqual(len(observed), 1)

    def test_retention_keeps_exact_latest_three_and_foreign_files(self):
        cloud = self.root / 'retention'
        cloud.mkdir()
        (cloud / 'personal-notes.zip').write_text('not ours')
        (cloud / '.council-partial').write_text('in flight')
        names = [f'council-202601{day:02d}T010200000000Z-1234abcd.zip' for day in range(1, 29)]
        for name in names:
            (cloud / name).write_text('fixture')
        prune(cloud)
        self.assertEqual(sorted(p.name for p in cloud.glob('council-*.zip')), names[-3:])
        self.assertTrue((cloud / 'personal-notes.zip').exists())
        self.assertTrue((cloud / '.council-partial').exists())
        prune(cloud)
        self.assertEqual(len(list(cloud.glob('council-*.zip'))), 3)

    def test_failed_new_backup_never_prunes_existing_bundles(self):
        from unittest.mock import patch
        cloud = self.root / 'retention-failure'
        cloud.mkdir()
        names = [f'council-202601{day:02d}T010200000000Z-1234abcd.zip' for day in range(1, 6)]
        for name in names:
            (cloud / name).write_text('previous backup')
        manager = BackupManager(SimpleNamespace(root=self.data, db=self.db), cloud, retry_delay=100)
        try:
            with patch('cloud_backup.create_bundle', side_effect=OSError('simulated failure')):
                self.assertIsNotNone(manager.run()['error'])
            self.assertEqual(sorted(p.name for p in cloud.iterdir()), names)
            manager.destination = cloud
            self.assertIsNone(manager.run()['error'])
            self.assertEqual(len(list(cloud.glob('council-*.zip'))), 3)
            self.assertEqual(len(list((self.data / 'auto-backup').glob('council-*.zip'))), 1)
        finally:
            manager.close()

if __name__ == '__main__':
    unittest.main()
