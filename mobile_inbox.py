"""Local receipt log + atomic approval; no network endpoint can approve records."""
import json
from capture_contract import envelope, canonical, apply_capture, now, form_config

class MobileInbox:
    def __init__(self, repo):
        self.repo = repo
        with repo.connect() as c:
            c.execute('CREATE TABLE IF NOT EXISTS mobile_inbox (id TEXT PRIMARY KEY, original TEXT NOT NULL, status TEXT NOT NULL, received TEXT NOT NULL, accepted TEXT, record_id TEXT)')

    def receive(self, value):
        envelope(value)
        body = canonical(value)
        with self.repo.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            old = c.execute('SELECT original FROM mobile_inbox WHERE id=?', (value['id'],)).fetchone()
            if old and old[0] != body: raise ValueError('重复标识携带不同内容，已拒绝覆盖')
            c.execute('INSERT OR IGNORE INTO mobile_inbox VALUES (?,?,?, ?,NULL,NULL)', (value['id'],body,'pending',now()))
        if not old and self.repo.on_saved: self.repo.on_saved()

    def rows(self):
        with self.repo.connect() as c:
            rows = c.execute('SELECT id,original,status,received,accepted,record_id FROM mobile_inbox ORDER BY received DESC LIMIT 500').fetchall()
        return [{'id':r[0], 'submission':json.loads(r[1]), 'status':r[2], 'receivedAt':r[3],
                 'accepted':json.loads(r[4]) if r[4] else None, 'recordId':r[5]} for r in rows]

    def receipts(self, ids):
        with self.repo.connect() as c:
            return [{'id': i, 'status': row[0]} for i in ids
                    if (row := c.execute('SELECT status FROM mobile_inbox WHERE id=?', (i,)).fetchone()) and row[0] != 'pending']

    def approve(self, identifier, corrected=None):
        with self.repo.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT original,status,record_id FROM mobile_inbox WHERE id=?', (identifier,)).fetchone()
            if not row: raise ValueError('待处理记录不存在')
            if row[1]=='imported': return {'status':'imported', 'recordId':row[2]}
            if row[1]!='pending': raise ValueError('此条已不在待确认列表')
            submission = json.loads(row[0])
            if corrected is not None: submission['payload'] = corrected
            revision, body = c.execute("SELECT revision,body FROM spaces WHERE name='main'").fetchone()
            state = json.loads(body)
            record_id = apply_capture(state, submission)
            # Receipt and application data share one transaction, including crash recovery.
            c.execute("INSERT INTO snapshots(space,revision,body) VALUES ('main',?,?)", (revision,body))
            c.execute("UPDATE spaces SET revision=?,body=? WHERE name='main'", (revision+1,canonical(state)))
            c.execute("DELETE FROM snapshots WHERE space='main' AND id NOT IN (SELECT id FROM snapshots WHERE space='main' ORDER BY id DESC LIMIT 100)")
            c.execute("UPDATE mobile_inbox SET status='imported',accepted=?,record_id=? WHERE id=?", (canonical(submission),record_id,identifier))
        if self.repo.on_saved: self.repo.on_saved()
        return {'status':'imported','recordId':record_id}

    def reject(self, identifier):
        with self.repo.connect() as c:
            c.execute("UPDATE mobile_inbox SET status='rejected' WHERE id=? AND status='pending'", (identifier,))
        if self.repo.on_saved: self.repo.on_saved()

    def config(self):
        return form_config(self.repo.read('main')['state'])
