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
 def test_discard_running_and_paused_timer_is_recoverable_and_idempotent(self):
  self.problem()
  self.call('update',domainId='ai-field',problemId='problem-1',date='2027-01-15',body='保留已写下的进展')
  self.call('manual',domainId='ai-field',date='2027-01-15',durationMs=600000)
  s=self.call('start',domainId='ai-field',problemId='problem-1',title='误触',owner='window-a',date='2027-01-15')
  rid=s['advancement']['active']['id'];self.call('pause',at=self.clock+3,id=rid)
  before=copy.deepcopy(self.repo.read('main')['state']['advancement'])
  c={'op':'discard','commandId':'cancel-once','id':rid}
  with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(lambda _:command(self.repo,'main',c,self.clock+10),range(3)))
  a=self.repo.read('main')['state']['advancement'];self.assertIsNone(a['active'])
  self.assertEqual(a['issues'],before['issues']);self.assertEqual(a['updates'],before['updates'])
  self.assertEqual(len(a['sessions']),2);row=a['sessions'][-1]
  self.assertTrue(row['deleted']);self.assertTrue(row['cancelled']);self.assertEqual(row['durationMs'],3000)
  self.assertEqual(sum(s['durationMs'] for s in a['sessions'] if not s['deleted']),600000)
  s=self.call('session-edit',id=rid,deleted=False);self.assertFalse(s['advancement']['sessions'][-1]['deleted'])
  s=self.call('start',at=self.clock+20,domainId='ai-field',owner='window-a',date='2027-01-15');new_id=s['advancement']['active']['id']
  with self.assertRaises(ValueError):self.call('discard',at=self.clock+21,id=rid)
  self.assertEqual(self.repo.read('main')['state']['advancement']['active']['id'],new_id)
  s=self.call('discard',at=self.clock+23,id=new_id);self.assertEqual(s['advancement']['sessions'][-1]['durationMs'],3000)
  validate(s)
 def test_repeated_plan_sessions_and_notes_stay_with_plan(self):
  self.problem();self.call('plan-add',id='plan-1',problemId='problem-1',title='先查文档',date='2027-01-15')
  for offset in (0,60):
   s=self.call('start',at=self.clock+offset,domainId='ai-field',problemId='problem-1',planId='plan-1',date='2027-01-15',owner='window-a')
   self.call('finish',at=self.clock+offset+10,id=s['advancement']['active']['id'],date='2027-01-15',note='本次实际发现')
  a=self.repo.read('main')['state']['advancement']
  self.assertEqual(sum(s['durationMs'] for s in a['sessions'] if s.get('planId')=='plan-1'),20000)
  self.assertEqual([u.get('planId') for u in a['updates']],['plan-1','plan-1'])
  q=a['plans'][0];self.assertEqual(q['status'],'active')
  s=self.call('plan-edit',at=self.clock+100,id=q['id'],expected=q['updatedAt'],status='done',date='2027-01-15')
  self.assertNotEqual(s['advancement']['issues'][0]['status'],'resolved')
  self.assertEqual(s['advancement']['updates'][-1]['planId'],'plan-1')
  with self.assertRaises(ValueError):self.call('start',domainId='ai-field',problemId='problem-1',planId='plan-1',date='2027-01-15',owner='window-a')
 def test_promote_is_idempotent_preserves_original_and_restore(self):
  self.problem();self.call('update',id='proposal-record',domainId='ai-field',problemId='problem-1',date='2027-01-15',body='问 GPT\n再核实资料')
  old=copy.deepcopy(self.repo.read('main')['state']['advancement']['updates'])
  self.call('plan-from-update',updateId='proposal-record');s=self.call('plan-from-update',updateId='proposal-record')
  a=s['advancement'];self.assertEqual(len(a['plans']),1);self.assertEqual(a['updates'],old);q=a['plans'][0]
  self.assertEqual(q['body'],old[0]['body']);self.assertEqual(a['issues'][0]['focusPlanId'],q['id'])
  self.call('plan-trash',id=q['id']);s=self.call('plan-trash',id=q['id'],deleted=False)
  bundle=self.path/'plans.zip';create_bundle(self.repo.db,bundle);restore(bundle,self.path/'plans-restored')
  self.assertEqual(Repository(self.path/'plans-restored').read('main')['state'],s)
 def test_plan_identity_validation_and_old_records_untouched(self):
  self.problem();s=self.call('plan-add',id='plan-1',problemId='problem-1',title='方案')
  q=s['advancement']['plans'][0]
  with self.assertRaises(ValueError):self.call('plan-edit',id=q['id'],expected='old',title='覆盖')
  before=self.repo.read('main')
  with self.assertRaises(ValueError):self.call('start',domainId='crypto-field',problemId='problem-1',planId=q['id'],date='2027-01-15',owner='window-a')
  self.assertEqual(before,self.repo.read('main'))
  s=self.call('start',domainId='ai-field',problemId='problem-1',date='2027-01-15',owner='window-a');rid=s['advancement']['active']['id']
  s=self.call('finish',at=self.clock+3,id=rid);self.assertNotIn('planId',s['advancement']['sessions'][0])
  s=self.call('update',domainId='ai-field',problemId='problem-1',planId=q['id'],date='2027-01-15',body='方案进展')
  bad=copy.deepcopy(s);bad['advancement']['updates'][-1]['problemId']=None
  with self.assertRaises(ValueError):validate(bad)
 def test_mobile_plan_and_legacy_progress_contract(self):
  self.problem();inbox=MobileInbox(self.repo)
  def mobile(kind,id,p):return {'version':1,'id':id,'kind':kind,'createdAt':'2026-10-27T00:00:00+08:00','payload':{'date':'2026-10-27','domainId':'ai-field','problemId':'problem-1',**p}}
  records=[mobile('progress','old-progress',{'body':'旧格式'}),mobile('plan','new-plan',{'title':'查询原文','body':'保留说明'})]
  for v in records:envelope(v);inbox.receive(v);inbox.approve(v['id']);inbox.approve(v['id'])
  v=mobile('progress','plan-progress',{'planId':'mobile-new-plan','body':'核实了第一条'})
  envelope(v);inbox.receive(v);inbox.approve(v['id'])
  a=self.repo.read('main')['state']['advancement'];self.assertNotIn('planId',a['updates'][0]);self.assertEqual(a['updates'][-1]['planId'],'mobile-new-plan')
  cfg=form_config(self.repo.read('main')['state']);self.assertEqual(set(cfg['plans'][0]),{'id','title','problemId','domainId'})
 def test_workbench_focus_selection_history_and_stale_form(self):
  self.problem();s=self.call('manual',domainId='ai-field',date='2027-01-15',durationMs=600000)
  sessions=copy.deepcopy(s['advancement']['sessions']);problems=copy.deepcopy(s['advancement']['issues'])
  s=self.call('workbench-focus',domainIds=['ai-field'],expected=[])
  self.assertEqual(s['advancement']['workbench']['focusDomainIds'],['ai-field'])
  cfg=form_config(s);self.assertEqual(len(cfg['domains']),2)
  s=self.call('workbench-select',domainId='crypto-field',date='2027-01-15')
  self.assertEqual(s['advancement']['workbench']['temporaryDomainIds'],['crypto-field'])
  self.assertEqual(s['advancement']['workbench']['focusDomainIds'],['ai-field'])
  s=self.call('workbench-focus',domainIds=[],expected=['ai-field'])
  self.assertEqual(s['advancement']['domains'][0]['archived'],False)
  self.assertEqual(s['advancement']['sessions'],sessions);self.assertEqual(s['advancement']['issues'],problems)
  self.call('workbench-focus',domainIds=['crypto-field'],expected=[])
  before=self.repo.read('main')
  with self.assertRaises(ValueError):self.call('workbench-focus',domainIds=['ai-field'],expected=[])
  self.assertEqual(before,self.repo.read('main'))
  for ids in (['missing'],['ai-field','ai-field'],'ai-field',[None]):
   with self.assertRaises(ValueError):self.call('workbench-focus',domainIds=ids,expected=['crypto-field'])
  s=self.call('workbench-select',domainId='ai-field',date='2027-01-16')
  self.assertEqual(s['advancement']['workbench']['temporaryDate'],'2027-01-16')
  self.assertEqual(s['advancement']['workbench']['temporaryDomainIds'],['ai-field'])
  bundle=self.path/'focus-backup.zip';create_bundle(self.repo.db,bundle);restore(bundle,self.path/'focus-restored')
  self.assertEqual(Repository(self.path/'focus-restored').read('main')['state']['advancement']['workbench'],s['advancement']['workbench'])
  for value in ({}, {'focusDomainIds':['missing'],'temporaryDate':None,'temporaryDomainIds':[]}, {'focusDomainIds':[],'temporaryDate':None,'temporaryDomainIds':['ai-field']}):
   bad=copy.deepcopy(s);bad['advancement']['workbench']=value
   with self.assertRaises(ValueError):validate(bad)
 def test_workbench_selections_merge_and_focus_retry_is_idempotent(self):
  c={'op':'workbench-focus','domainIds':['ai-field'],'expected':[],'commandId':'focus-retry'}
  command(self.repo,'main',c,self.clock);command(self.repo,'main',c,self.clock)
  def select(d):return command(self.repo,'main',{'op':'workbench-select','domainId':d,'date':'2027-01-15','commandId':'select-'+d},self.clock)
  with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(select,['ai-field','crypto-field']))
  self.assertEqual(set(self.repo.read('main')['state']['advancement']['workbench']['temporaryDomainIds']),{'ai-field','crypto-field'})
 def test_integrity_trash_task_and_manual_edit(self):
  p=self.problem();s=self.call('task',id=p['id'],date='2027-01-16',title='做一次复现');self.assertEqual(s['tasks'][-1]['advancementProblemId'],p['id'])
  self.call('problem-trash',id=p['id']);s=self.call('problem-trash',id=p['id'],deleted=False);self.assertFalse(s['advancement']['issues'][0]['deleted'])
  s=self.call('manual',domainId='ai-field',date='2027-01-15',durationMs=900000);sid=s['advancement']['sessions'][0]['id']
  s=self.call('session-edit',id=sid,durationMs=600000);self.assertEqual(s['advancement']['sessions'][0]['durationMs'],600000)
  bad=copy.deepcopy(s);bad['advancement']['sessions'][0]['durationMs']=float('nan')
  with self.assertRaises(ValueError):validate(bad)
  bad=copy.deepcopy(s);bad['advancement']['issues'][0]['domainId']='missing'
  with self.assertRaises(ValueError):validate(bad)
 def test_new_domain_creates_child_and_old_parent_payload_is_compatible(self):
  s=self.call('domain',folderId='science',name='自动化');a=s['advancement'];d=next(d for d in a['domains'] if d['name']=='自动化')
  f=next(f for f in s['folders'] if f['id']==d['folderId']);self.assertEqual(f['parent'],'science');self.assertNotEqual(f['id'],'science')
  s=self.call('domain',folderId='science',name='自动化');self.assertEqual(len(s['advancement']['domains']),3)
  self.assertEqual(sum(f['parent']=='science' and f['name']=='自动化' for f in s['folders']),1)
  s=self.call('domain',parentId='science',name='英语');english=next(d for d in s['advancement']['domains'] if d['name']=='英语')
  s=self.call('domain',id=english['id'],name='英语学习');self.assertEqual(next(f for f in s['folders'] if f['id']==english['folderId'])['name'],'英语学习')
  self.call('domain',id=english['id'],archived=True)
  with self.assertRaises(ValueError):self.call('domain',parentId='science',name='英语学习')
  with self.assertRaises(ValueError):self.call('domain',folderId='science',name='')
 def test_legacy_root_alias_repair_preserves_identity_and_all_records(self):
  self.problem();self.call('manual',domainId='ai-field',date='2027-01-15',durationMs=60000)
  v=self.repo.read('main');s=v['state'];a=s['advancement'];a['domains'].append({'id':'science','folderId':'science','name':'自动化','goal':'保留目标','focusId':'old-problem','archived':False})
  p=copy.deepcopy(a['issues'][0]);p.update(id='old-problem',domainId='science');a['issues'].append(p)
  q={'id':'old-plan','domainId':'science','problemId':'old-problem','title':'原方案','body':'原说明','status':'active','deleted':False,'date':'2027-01-15'};a['plans'].append(q)
  t=copy.deepcopy(a['sessions'][0]);t.update(id='old-time',domainId='science',problemId='old-problem',planId='old-plan');a['sessions'].append(t)
  a['updates'].append({'id':'old-update','domainId':'science','problemId':'old-problem','planId':'old-plan','date':'2027-01-15','body':'保留原进展','createdAt':'2027-01-15T00:00:00Z'})
  a['workbench']={'focusDomainIds':['science'],'temporaryDate':None,'temporaryDomainIds':[]}
  before=copy.deepcopy(s);self.repo.save('main',v['revision'],validate(s));s=self.call('sync-folders')
  fixed=next(d for d in s['advancement']['domains'] if d['id']=='science');self.assertNotEqual(fixed['folderId'],'science');self.assertEqual(fixed['name'],'自动化');self.assertEqual(fixed['goal'],'保留目标')
  for key in ('issues','plans','updates','sessions','workbench'):self.assertEqual(s['advancement'][key],before['advancement'][key])
  self.assertEqual(next(f for f in s['folders'] if f['id']=='science')['name'],'中科院')
  count=len(s['folders']);s=self.call('reconcile');self.assertEqual(len(s['folders']),count)
  bundle=self.path/'linked.zip';create_bundle(self.repo.db,bundle);restore(bundle,self.path/'linked-restored');self.assertEqual(Repository(self.path/'linked-restored').read('main')['state'],s)
 def test_folder_api_returns_linked_state_and_renames_sync_both_directions(self):
  from http.server import ThreadingHTTPServer
  from urllib.request import Request,urlopen
  from urllib.error import HTTPError
  from server import handler
  server=ThreadingHTTPServer(('127.0.0.1',0),handler(self.repo));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  def save(v):
   request=Request(f'http://127.0.0.1:{server.server_port}/api/state',data=json.dumps(v).encode(),headers={'Content-Type':'application/json','X-Personal-Client':'1'})
   with urlopen(request) as response:return json.load(response)
  try:
   v=self.repo.read('main');old=copy.deepcopy(v);v['state']['folders'].append({'id':'new-folder','name':'新领域','parent':'science','fields':[]})
   response=save(v);d=next(d for d in response['state']['advancement']['domains'] if d['folderId']=='new-folder')
   self.assertEqual(response,self.repo.read('main'))
   with self.assertRaises(HTTPError) as conflict:save(old)
   self.assertEqual(conflict.exception.code,409)
   next(f for f in response['state']['folders'] if f['id']=='new-folder')['name']='从文件夹改名'
   response=save(response);self.assertEqual(next(x for x in response['state']['advancement']['domains'] if x['id']==d['id'])['name'],'从文件夹改名')
   s=self.call('domain',id=d['id'],name='从推进台改名');self.assertEqual(next(f for f in s['folders'] if f['id']=='new-folder')['name'],'从推进台改名')
   s=self.call('domain',id=d['id'],archived=True)
   v=self.repo.read('main');response=save(v);self.assertTrue(next(x for x in response['state']['advancement']['domains'] if x['id']==d['id'])['archived'])
   self.assertEqual(sum(x['folderId']=='new-folder' for x in response['state']['advancement']['domains']),1)
  finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
