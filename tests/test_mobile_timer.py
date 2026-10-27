import copy
import datetime as dt
import json
import sys
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from repository import Repository
from advancement_service import command
from capture_contract import envelope,form_config
from mobile_inbox import MobileInbox
from mobile_bridge import MobileBridge
from capture_relay import Relay,make_server
from cloud_backup import create_bundle
from recovery import restore

START=int(dt.datetime(2026,10,26,23,55,tzinfo=dt.timezone(dt.timedelta(hours=8))).timestamp()*1000)
class MobileTimerTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.repo=Repository(self.root/'data');self.inbox=MobileInbox(self.repo);self.n=0
  self.call('init');s=self.call('domain',name='健身');self.did=next(d['id'] for d in s['advancement']['domains'] if d['name']=='健身')
  s=self.call('domain',name='AI');self.other=next(d['id'] for d in s['advancement']['domains'] if d['name']=='AI')
  self.call('problem-add',id='training',domainId=self.did,title='测试训练',date='2026-10-26')
  self.call('plan-add',id='training-plan',problemId='training',title='测试方案',date='2026-10-26')
 def tearDown(self):self.tmp.cleanup()
 def call(self,op,clock=None,**p):
  self.n+=1;return command(self.repo,'main',{'op':op,'commandId':f'fixture-{self.n}',**p},clock)['state']
 def record(self,id='phone-timer',**p):
  return {'version':1,'id':id,'kind':'focus','createdAt':'2026-10-27T01:00:00+08:00','payload':{
   'date':'2026-10-26','domainId':self.did,'problemId':'training','planId':'training-plan','title':'测试跑步','note':'原话\n第二行',
   'segments':[{'start':START,'end':START+300000},{'start':START+600000,'end':START+900000}],'durationMs':600000,**p}}
 def test_pending_approval_is_atomic_idempotent_and_backed_up(self):
  r=self.record();before=self.repo.read('main');self.inbox.receive(r);self.inbox.receive(r);self.assertEqual(before,self.repo.read('main'))
  fresh=self.repo.read('main');fresh['state']['tasks'].append({'id':'other-edit','title':'电脑的独立编辑','date':'2026-10-27','done':False});self.repo.save('main',fresh['revision'],fresh['state'])
  with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(lambda _:self.inbox.approve(r['id']),range(3)))
  s=self.repo.read('main')['state'];a=s['advancement'];self.assertEqual(len(a['sessions']),1);session=a['sessions'][0]
  self.assertEqual(session['segments'],r['payload']['segments']);self.assertEqual(session['durationMs'],600000);self.assertEqual(session['planId'],'training-plan');self.assertFalse(session['manual'])
  self.assertIsNone(a['active']);self.assertEqual(len(a['updates']),1);self.assertEqual(a['updates'][0]['body'],'原话\n第二行');self.assertEqual(a['updates'][0]['planId'],'training-plan')
  self.assertEqual(s['tasks'][-1]['id'],'other-edit')
  bundle=self.root/'timer.zip';create_bundle(self.repo.db,bundle);restore(bundle,self.root/'restored');recovered=MobileInbox(Repository(self.root/'restored'));recovered.approve(r['id']);self.assertEqual(len(recovered.repo.read('main')['state']['advancement']['sessions']),1)
 def test_invalid_segments_and_contract_reject_without_receiving(self):
  variants=[{'durationMs':True},{'durationMs':1},{'durationMs':float('nan')},{'segments':[]},{'planId':'training-plan','problemId':None},{'adjustedDurationMs':-1},{'adjustedDurationMs':True},{'unknown':'no'},
   {'segments':[{'start':START+1,'end':START}]},{'segments':[{'start':START,'end':START+300000},{'start':START+1,'end':START+600000}],'durationMs':899999},
   {'segments':[{'start':START,'end':START+9000000}],'durationMs':9000000}, {'date':'2026-10-27'}]
  for value in variants:
   with self.subTest(value=value):
    with self.assertRaises(ValueError):self.inbox.receive(self.record(**value))
  self.assertEqual(self.inbox.rows(),[])
 def test_overlap_keeps_pending_and_correction_preserves_original(self):
  v=self.repo.read('main');a=v['state']['advancement'];a['sessions'].append({'id':'existing','domainId':self.other,'problemId':None,'title':'电脑计时','date':'2026-10-26','segments':[{'start':START,'end':START+60000}],'durationMs':60000,'manual':False,'deleted':False,'note':'','endedAt':START+60000});self.repo.save('main',v['revision'],v['state'])
  r=self.record();self.inbox.receive(r);before=self.repo.read('main')
  with self.assertRaisesRegex(ValueError,'重叠'):self.inbox.approve(r['id'])
  self.assertEqual(self.repo.read('main'),before);self.assertEqual(self.inbox.rows()[0]['status'],'pending')
  self.inbox.approve(r['id'],{**r['payload'],'adjustedDurationMs':180000});s=self.repo.read('main')['state']['advancement']['sessions'][-1]
  self.assertTrue(s['manual']);self.assertEqual(s['durationMs'],180000);self.assertEqual(s['segments'],[]);self.assertEqual(s['original']['segments'],r['payload']['segments']);self.assertEqual(self.inbox.rows()[0]['submission'],r)
 def test_running_desktop_timer_is_not_stopped_or_overwritten(self):
  s=self.call('start',clock=(START+60000)/1000,domainId=self.other,date='2026-10-26',owner='desktop');active=copy.deepcopy(s['advancement']['active'])
  r=self.record();self.inbox.receive(r)
  with self.assertRaisesRegex(ValueError,'重叠'):self.inbox.approve(r['id'])
  self.assertEqual(self.repo.read('main')['state']['advancement']['active'],active)
 def test_expired_metadata_requires_explicit_correction_and_reject_is_neutral(self):
  r=self.record();self.inbox.receive(r);self.call('domain',id=self.did,archived=True)
  with self.assertRaises(ValueError):self.inbox.approve(r['id'])
  self.inbox.approve(r['id'],{**r['payload'],'domainId':self.other,'problemId':None,'planId':None})
  self.assertEqual(self.repo.read('main')['state']['advancement']['sessions'][0]['domainId'],self.other)
  r=self.record('rejected');self.inbox.receive(r);before=self.repo.read('main');self.inbox.reject(r['id']);self.assertEqual(before,self.repo.read('main'))
 def test_relay_queue_receipt_and_legacy_v1_compatibility(self):
  self.call('workbench-focus',domainIds=[self.did],expected=[])
  relay=Relay(self.root/'relay','http://127.0.0.1:8891');server=make_server(relay,'127.0.0.1',0);relay.origin=f'http://127.0.0.1:{server.server_port}';thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  def request(path,body=None,role='phone'):
   headers={'Authorization':'Bearer '+relay.tokens['desktopToken']} if role=='desktop' else {'Cookie':'capture_session='+relay.tokens['phoneToken']}
   if body is not None:headers.update({'Content-Type':'application/json','X-Capture-Client':'1','Origin':relay.origin})
   req=urllib.request.Request(relay.origin+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
   with urllib.request.urlopen(req) as res:return json.load(res)
  try:
   (self.repo.root/'mobile-bridge.json').write_text(json.dumps({'url':relay.origin,'desktopToken':relay.tokens['desktopToken']}));bridge=MobileBridge(self.inbox);bridge.sync();self.assertIsNone(bridge.error)
   config=request('/api/config');self.assertIn('focus',config['kinds']);self.assertEqual(config['focusDomainIds'],[self.did]);self.assertNotIn('sessions',config)
   old={'version':1,'kinds':{'task':'每日任务'},'categories':[],'habits':[]};request('/bridge/config',old,'desktop');self.assertEqual(request('/api/config'),old)
   bridge.sync();r=self.record();request('/api/submit',r);request('/api/submit',r)
   task={'version':1,'id':'legacy-offline','kind':'task','createdAt':'2026-10-26T12:00:00+08:00','payload':{'date':'2026-10-26','title':'旧手机离线任务'}};request('/api/submit',task);bridge.sync()
   self.assertEqual(len(self.inbox.rows()),2);self.assertEqual(len(self.repo.read('main')['state']['advancement']['sessions']),0)
   self.inbox.approve(r['id']);self.inbox.approve(task['id']);bridge.sync();self.assertTrue(all(row['status']=='imported' for row in request('/api/items')['items']))
   with self.assertRaises(urllib.error.HTTPError):request('/bridge/pending')
   for path in ('/mobile/timer-model.js','/mobile/timer-workbench.js'):
    with urllib.request.urlopen(relay.origin+path) as response:self.assertEqual(response.status,200)
  finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
