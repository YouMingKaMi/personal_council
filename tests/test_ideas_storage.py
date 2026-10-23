import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from repository import Repository
from cloud_backup import create_bundle
from recovery import restore
from domain import validate


class IdeaStorageTest(unittest.TestCase):
    def test_new_module_uses_existing_notes_and_survives_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = Repository(root / 'data')
            before = repo.read('main')
            state = before['state']
            folder = next(f for f in state['folders'] if f.get('module') == 'ideas')
            self.assertEqual(next(f for f in state['folders'] if f['id'] == folder['parent'])['name'], '执行部')
            self.assertNotIn(folder['id'], state['pins'])
            protected = {k: json.dumps(state[k], sort_keys=True) for k in ('tasks', 'habits', 'rules', 'chronicle', 'treasury')}
            note = {'id': 'synthetic-idea', 'folder': folder['id'], 'date': '2026-10-23',
                    'title': '虚构想法', 'body': '  原话\n\n以后也许会做 <script>只是文本</script> ',
                    'tags': [], 'values': {}, 'status': 'done', 'createdAt': '2026-10-23T01:00:00Z',
                    'updatedAt': '2026-10-23T01:00:00Z', 'dateBasis': '记录日期', 'trashed': True}
            state['notes'].append(note)
            repo.save('main', before['revision'], validate(state))
            backup = root / 'ideas-backup.zip'
            create_bundle(repo.db, backup)
            target = root / 'restored'
            restore(backup, target)
            with closing(sqlite3.connect(target / 'personal.sqlite3')) as db:
                saved = json.loads(db.execute("SELECT body FROM spaces WHERE name='main'").fetchone()[0])
            self.assertEqual(next(n for n in saved['notes'] if n['id'] == note['id']), note)
            self.assertEqual(saved['schemaVersion'], 8)
            self.assertEqual({k: json.dumps(saved[k], sort_keys=True) for k in protected}, protected)


if __name__ == '__main__':
    unittest.main()
