import http.client
import json
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from repository import Repository
from migrations import upgrade
from domain import validate
from advancement_service import command
from advancement_clock import AdvancementClock
from server import handler
from http.server import ThreadingHTTPServer

ROOT=Path(__file__).resolve().parents[1]

class AdvancementClockTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();data=Path(self.tmp.name)/'data';data.mkdir()
        s=upgrade(json.loads((ROOT/'seed.example.json').read_text()))
        s['folders'] += [{'id':'science','name':'中科院','parent':None,'fields':[]}, {'id':'ai-field','name':'AI','parent':'science','fields':[]}]
        with sqlite3.connect(data/'personal.sqlite3') as db:
            db.execute('CREATE TABLE spaces (name TEXT PRIMARY KEY, revision INTEGER NOT NULL, body TEXT NOT NULL)')
            db.execute('INSERT INTO spaces VALUES (?,?,?)',('main',1,json.dumps(validate(s))))
        self.repo=Repository(data);self.clock=AdvancementClock(self.repo);self.now=1800000000;self.n=0
        self.call('init')
    def tearDown(self):self.clock.close();self.tmp.cleanup()
    def call(self,op,at=0,server=True,**payload):
        self.n+=1
        return command(self.repo,'main',{'op':op,'commandId':'clock-test-'+str(self.n),**payload},self.now+at,server_timer=server)['state']['advancement']
    def start_timer(self,server=True):
        return self.call('start',domainId='ai-field',owner='window-a',date='2027-01-15',server=server)['active']['id']
    def active(self):return self.repo.read('main')['state']['advancement']['active']
    def test_background_for_two_hours_without_any_browser_heartbeat(self):
        rid=self.start_timer();backups=[];self.repo.on_saved=lambda:backups.append(True)
        snapshots=len(self.repo.backups('main'))
        with self.clock.watch('main','window-a'),self.clock.watch('main','window-a'),self.clock.watch('main','other-tab'):
            for elapsed in range(10,7201,10):self.clock.tick(clock=self.now+elapsed)
        r=self.active();self.assertEqual(r['status'],'running');self.assertEqual(r['lastSeen'],(self.now+7200)*1000)
        a=self.call('finish',at=7201,id=rid)
        self.assertEqual(a['sessions'][-1]['durationMs'],7201000)
        self.assertEqual(len(self.repo.backups('main')),snapshots+1)
        self.assertLessEqual(len(backups),26)  # durable ticks do not flood backup requests
    def test_page_close_and_foreign_tab_do_not_keep_timer_alive(self):
        self.start_timer()
        with self.clock.watch('main','window-a'):self.clock.tick(clock=self.now+10)
        with self.clock.watch('main','other-tab'):
            self.clock.tick(clock=self.now+20);self.clock.tick(clock=self.now+41)
        r=self.active();self.assertEqual(r['status'],'paused');self.assertTrue(r['interrupted'])
        self.assertEqual(r['segments'],[{'start':self.now*1000,'end':(self.now+10)*1000}])
        with self.clock.watch('main','window-a'):self.clock.tick(clock=self.now+100)
        self.assertEqual(self.active(),r)  # reconnect never resumes a paused record
    def test_reload_reconnect_and_pause_from_another_tab(self):
        rid=self.start_timer()
        with self.clock.watch('main','window-a'):self.clock.tick(clock=self.now+10)
        self.clock.tick(clock=self.now+20)
        with self.clock.watch('main','window-a'):
            self.clock.tick(clock=self.now+25)
            self.assertEqual(self.active()['status'],'running')
            self.call('pause',at=26,id=rid)
            before=self.active();self.clock.tick(clock=self.now+30);self.assertEqual(self.active(),before)
            self.call('resume',at=40,id=rid,owner='window-b')
            self.clock.tick(clock=self.now+71)
            self.assertEqual(self.active()['status'],'paused')  # previous owner cannot confirm a new owner
    def test_sleep_gap_clock_rollback_and_restart(self):
        rid=self.start_timer()
        with self.clock.watch('main','window-a'):
            self.clock.tick(clock=self.now+10);self.clock.tick(clock=self.now+600)
        self.assertEqual(self.active()['segments'][0]['end'],(self.now+10)*1000)
        self.assertEqual(self.active()['status'],'paused')
        self.call('resume',at=601,id=rid,owner='window-a')
        with self.clock.watch('main','window-a'):self.clock.tick(clock=self.now+600)
        self.assertEqual(self.active()['status'],'paused')
        self.call('resume',at=610,id=rid,owner='window-a')
        self.clock.tick(clock=self.now+611,interrupt=True)
        self.assertEqual(self.active()['lastSeen'],(self.now+610)*1000)
        self.assertEqual(self.active()['status'],'paused')
    def test_legacy_timer_restart_and_stale_worker_cannot_replace_session(self):
        rid=self.start_timer(server=False)
        self.clock.tick(clock=self.now+10,interrupt=True)
        self.assertEqual(self.active()['status'],'paused')
        self.call('finish',at=11,id=rid)
        new=self.call('start',at=12,domainId='ai-field',owner='window-a',date='2027-01-15')['active']
        self.call('clock-pulse',at=13,id=rid,owner='window-a',connected=True)
        self.assertEqual(self.active(),new)
    def test_browser_heartbeat_cannot_extend_server_timer(self):
        rid=self.start_timer()
        self.call('heartbeat',at=20,id=rid,owner='window-a')
        self.assertEqual(self.active()['lastSeen'],self.now*1000)
        self.call('heartbeat',at=40,id=rid,owner='window-a')
        self.assertEqual(self.active()['status'],'paused')
    def test_stream_same_origin_and_internal_command_guard(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),handler(self.repo,timer_clock=self.clock))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        port=server.server_port;path='/api/advancement/watch?space=main&owner=window-a'
        conn=http.client.HTTPConnection('127.0.0.1',port,timeout=3)
        try:
            conn.request('GET',path);r=conn.getresponse();self.assertEqual(r.status,403);r.read()
            conn.request('GET',path,headers={'Sec-Fetch-Site':'cross-site'});r=conn.getresponse();self.assertEqual(r.status,403);r.read()
            conn.request('GET',path,headers={'Sec-Fetch-Site':'same-origin','Origin':'https://other.example'});r=conn.getresponse();self.assertEqual(r.status,403);r.read()
            conn.request('POST','/api/advancement',json.dumps({'op':'clock-pulse'}),{'X-Personal-Client':'1'});r=conn.getresponse();self.assertEqual(r.status,403);r.read()
            conn.request('GET',path,headers={'Sec-Fetch-Site':'same-origin'});r=conn.getresponse();self.assertEqual(r.status,200)
            self.assertEqual(r.headers['Content-Type'],'text/event-stream');self.assertIn(b'retry:',r.readline())
            with self.clock._lock:self.assertEqual(self.clock._pages[('main','window-a')],1)
        finally:
            self.clock.close();conn.close();server.shutdown();server.server_close();thread.join(timeout=3)

if __name__=='__main__':unittest.main()
