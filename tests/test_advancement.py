import copy
import json
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from repository import Repository,Conflict
from migrations import upgrade
from domain import validate
from advancement_service import command
from capture_contract import envelope,form_config
from mobile_inbox import MobileInbox
from mobile_bridge import MobileBridge
from capture_relay import Relay,make_server
from cloud_backup import create_bundle
from recovery import restore

ROOT=Path(__file__).resolve().parents[1]
class AdvancementTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name);data=self.path/'data';data.mkdir()
  s=upgrade(json.loads((ROOT/'seed.example.json').read_text()))
  s['folders'] += [{'id':'science','name':'中科院','parent':None,'fields':[]}, {'id':'ai-field','name':'AI','parent':'science','fields':[]},{'id':'crypto-field','name':'Crypto','parent':'science','fields':[]}]
  with sqlite3.connect(data/'personal.sqlite3') as db:
   db.execute('CREATE TABLE spaces (name TEXT PRIMARY KEY, revision INTEGER NOT NULL, body TEXT NOT NULL)');db.execute('INSERT INTO spaces VALUES (?,?,?)',('main',1,json.dumps(validate(s))))
  self.repo=Repository(data);self.n=0;self.clock=1800000000
  self.call('init')
 def tearDown(self):self.tmp.cleanup()
 def call(self,op,at=None,**payload):
  self.n+=1;return command(self.repo,'main',{'op':op,'commandId':'cmd-'+str(self.n),**payload},self.clock if at is None else at)['state']
 def problem(self):return self.call('problem-add',id='problem-1',domainId='ai-field',title='接口为什么失败？',body='原文\n第二行',next='做最小复现')['advancement']['issues'][0]
 def test_timer_single_global_pause_resume_switch_and_sleep(self):
  self.problem();s=self.call('start',domainId='ai-field',problemId='problem-1',owner='window-a',date='2027-01-15',title='最小复现');r=s['advancement']['active'];rid=r['id']
  with self.assertRaises(ValueError):self.call('start',domainId='crypto-field',owner='window-b',date='2027-01-15')
  self.call('heartbeat',at=self.clock+15,id=rid,owner='window-a')
  s=self.call('pause',at=self.clock+25,id=rid);self.assertEqual(s['advancement']['active']['segments'],[{'start':self.clock*1000,'end':(self.clock+25)*1000}])
  self.call('resume',at=self.clock+50,id=rid,owner='window-a')
  self.call('heartbeat',at=self.clock+65,id=rid,owner='window-a')
  s=self.call('reconcile',at=self.clock+600);r=s['advancement']['active'];self.assertEqual(r['status'],'paused');self.assertTrue(r['interrupted'])
  # A later heartbeat cannot revive an interrupted timer or count the sleeping interval.
  self.call('heartbeat',at=self.clock+700,id=rid,owner='window-a')
  s=self.call('finish',at=self.clock+701,id=rid,date='2027-01-15',note='验证了一个方案');self.assertEqual(s['advancement']['sessions'][0]['durationMs'],40000)
  self.assertEqual(len(s['advancement']['updates']),1);self.assertNotEqual(s['advancement']['issues'][0]['status'],'resolved')
  s=self.call('start',at=self.clock+800,domainId='ai-field',date='2027-01-15',owner='window-a');rid=s['advancement']['active']['id']
  s=self.call('switch',at=self.clock+810,id=rid,domainId='crypto-field',date='2027-01-15',owner='window-a')
  self.assertEqual(s['advancement']['active']['domainId'],'crypto-field');self.assertEqual(s['advancement']['sessions'][-1]['durationMs'],10000)
  validate(s)
 def test_concurrent_duplicate_and_stale_editor(self):
  p=self.problem();before=self.repo.read('main')
  s=self.call('problem-edit',id=p['id'],expected=p['updatedAt'],date='2027-01-15',next='查官方接口',at=self.clock+1)
  with self.assertRaises(ValueError):self.call('problem-edit',id=p['id'],expected=p['updatedAt'],date='2027-01-15',body='旧窗口覆盖',at=self.clock+2)
  p=s['advancement']['issues'][0]
  self.call('problem-edit',id=p['id'],expected=p['updatedAt'],date='2027-01-15',status='resolved',conclusion='有效方案',at=self.clock+3)
  c={'op':'manual','commandId':'same-command','domainId':'ai-field','date':'2027-01-15','durationMs':600000}
  with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda _:command(self.repo,'main',c,self.clock+4),range(4)))
  self.assertEqual(len(self.repo.read('main')['state']['advancement']['sessions']),1)
  with self.assertRaises(Conflict):self.repo.save('main',before['revision'],before['state'])
 def test_phone_legacy_and_new_kinds_backup_restore(self):
  self.problem();inbox=MobileInbox(self.repo)
  def capture(kind,id,payload):return {'version':1,'kind':kind,'id':id,'createdAt':'2026-10-26T12:00:00+08:00','payload':{'date':'2026-10-26',**payload}}
  old=capture('expense','old-phone',{'title':'咖啡','categoryId':'food-coffee','amountCents':1500,'necessity':'necessary'})
  new=capture('problem','new-phone',{'domainId':'ai-field','title':'手机的问题','body':'原文\n换行','next':''})
  for v in (old,new):envelope(v);inbox.receive(v);inbox.approve(v['id']);inbox.approve(v['id'])
  update=capture('progress','phone-progress',{'domainId':'ai-field','problemId':'mobile-new-phone','body':'测试了一个方案'})
  inbox.receive(update);inbox.approve(update['id'])
  s=self.repo.read('main')['state'];self.assertEqual(len(s['advancement']['issues']),2);self.assertEqual(s['advancement']['updates'][-1]['body'],'测试了一个方案')
  cfg=form_config(s);self.assertNotIn('body',cfg['problems'][-1]);self.assertNotIn('sessions',cfg)
  invalid=copy.deepcopy(new);invalid['id']='invalid';invalid['payload']['domainId']='missing';inbox.receive(invalid)
  before=self.repo.read('main')
  with self.assertRaises(ValueError):inbox.approve(invalid['id'])
  self.assertEqual(before,self.repo.read('main'))
  bundle=self.path/'backup.zip';create_bundle(self.repo.db,bundle);restore(bundle,self.path/'restored');self.assertEqual(Repository(self.path/'restored').read('main')['state'],s)
 def test_relay_accepts_extended_config_and_receipts(self):
  relay=Relay(self.path/'relay','http://127.0.0.1:8899')
  server=make_server(relay,'127.0.0.1',0)
  # Test server's actual origin must match its randomly allocated local port.
  relay.origin='http://127.0.0.1:'+str(server.server_port)
  thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  try:
   conf=self.repo.root/'mobile-bridge.json';conf.write_text(json.dumps({'url':relay.origin,'desktopToken':relay.tokens['desktopToken']}))
   bridge=MobileBridge(MobileInbox(self.repo));self.assertIsNone(bridge.sync()['error'])
   config=form_config(self.repo.read('main')['state'])
   self.assertIn('domains',config);self.assertIn('problem',config['kinds'])
   import urllib.request
   req=urllib.request.Request(relay.origin+'/api/config',headers={'Cookie':'capture_session='+relay.tokens['phoneToken']})
   with urllib.request.urlopen(req) as response:self.assertEqual(json.load(response)['domains'],config['domains'])
  finally:server.shutdown();server.server_close();thread.join()
 def test_integrity_trash_task_and_manual_edit(self):
  p=self.problem();s=self.call('task',id=p['id'],date='2027-01-16',title='做一次复现');self.assertEqual(s['tasks'][-1]['advancementProblemId'],p['id'])
  self.call('problem-trash',id=p['id']);s=self.call('problem-trash',id=p['id'],deleted=False);self.assertFalse(s['advancement']['issues'][0]['deleted'])
  s=self.call('manual',domainId='ai-field',date='2027-01-15',durationMs=900000);sid=s['advancement']['sessions'][0]['id']
  s=self.call('session-edit',id=sid,durationMs=600000);self.assertEqual(s['advancement']['sessions'][0]['durationMs'],600000)
  bad=copy.deepcopy(s);bad['advancement']['sessions'][0]['durationMs']=float('nan')
  with self.assertRaises(ValueError):validate(bad)
  bad=copy.deepcopy(s);bad['advancement']['issues'][0]['domainId']='missing'
  with self.assertRaises(ValueError):validate(bad)

if __name__=='__main__':unittest.main()
