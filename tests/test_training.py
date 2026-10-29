import copy,datetime as dt,tempfile,unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from repository import Repository
from advancement_service import command
from domain import validate
from capture_contract import form_config,envelope
from mobile_inbox import MobileInbox
from cloud_backup import create_bundle
from recovery import restore

class TrainingTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.repo=Repository(self.root/'data');self.n=0;self.clock=1793210400
  self.call('init');s=self.call('domain',name='健身');self.did=next(d['id'] for d in s['advancement']['domains'] if d['name']=='健身')
  s=self.call('domain',name='AI');self.other=next(d['id'] for d in s['advancement']['domains'] if d['name']=='AI')
  self.call('activity-add',id='run',domainId=self.did,name='跑步')
 def tearDown(self):self.tmp.cleanup()
 def call(self,op,at=None,**p):
  self.n+=1;return command(self.repo,'main',dict(op=op,commandId=f'training-{self.n}',**p),self.clock if at is None else at)['state']
 def test_manual_target_and_normal_timer_share_stable_activity(self):
  s=self.call('manual',domainId=self.did,activityId='run',date='2026-10-29',durationMs=1800000,note='忘记开启计时，补记')
  row=s['advancement']['sessions'][-1];self.assertEqual((row['title'],row['activityId'],row['manual'],row['segments']),('跑步','run',True,[]))
  r=self.call('start',domainId=self.did,activityId='run',date='2026-10-29',owner='browser')['advancement']['active']
  self.call('heartbeat',id=r['id'],owner='browser',at=self.clock+15)
  s=self.call('finish',id=r['id'],note='第二次训练',date='2026-10-29',at=self.clock+20)
  self.assertEqual(sum(x['durationMs'] for x in s['advancement']['sessions']),1820000)
  self.assertEqual(s['advancement']['updates'][-1]['activityId'],'run');validate(s)
 def test_cross_domain_mixed_targets_and_stale_edit_rollback(self):
  self.call('problem-add',id='knee',domainId=self.did,title='训练问题',date='2026-10-29')
  before=self.repo.read('main')
  for extra in [dict(domainId=self.other),dict(problemId='knee'),dict(planId='missing')]:
   with self.assertRaises(ValueError):self.call('manual',**{**dict(domainId=self.did,activityId='run',date='2026-10-29',durationMs=600000),**extra})
  self.assertEqual(before,self.repo.read('main'))
  x=before['state']['advancement']['activities'][0]
  self.call('activity-edit',id='run',expected=x['updatedAt'],name='户外跑步',at=self.clock+1)
  with self.assertRaises(ValueError):self.call('activity-edit',id='run',expected=x['updatedAt'],name='旧窗口覆盖',at=self.clock+2)
 def test_idempotency_archive_and_history_preservation(self):
  c=dict(op='manual',commandId='same-manual',domainId=self.did,activityId='run',durationMs=600000,date='2026-10-29')
  with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(lambda _:command(self.repo,'main',c,self.clock),range(3)))
  s=self.repo.read('main')['state'];self.assertEqual(len(s['advancement']['sessions']),1);row=copy.deepcopy(s['advancement']['sessions'][0]);x=s['advancement']['activities'][0]
  s=self.call('activity-edit',id=x['id'],expected=x['updatedAt'],archived=True,at=self.clock+1)
  self.assertEqual(row,s['advancement']['sessions'][0]);self.assertEqual(form_config(s)['activities'],[])
  with self.assertRaises(ValueError):self.call('start',domainId=self.did,activityId='run',date='2026-10-29',owner='browser')
  x=s['advancement']['activities'][0];self.call('activity-edit',id=x['id'],expected=x['updatedAt'],archived=False,at=self.clock+2)
 def test_phone_manual_and_timer_atomic_approval_and_restore(self):
  inbox=MobileInbox(self.repo)
  def record(kind,id,p):return dict(version=1,kind=kind,id=id,createdAt='2026-10-29T16:00:00+08:00',payload=dict(date='2026-10-29',domainId=self.did,title='跑步',note='手机原文',**p))
  manual=record('time','mobile-manual',dict(activityId='run',durationMs=1800000));envelope(manual)
  start=int(dt.datetime(2026,10,29,10,tzinfo=dt.timezone(dt.timedelta(hours=8))).timestamp()*1000)
  timer=record('focus','mobile-training',dict(activityId='run',problemId=None,planId=None,durationMs=600000,segments=[dict(start=start,end=start+600000)]));envelope(timer)
  old=record('focus','old-free-timer',dict(problemId=None,planId=None,durationMs=600000,segments=[dict(start=start+1200000,end=start+1800000)]));envelope(old)
  for submission in (manual,timer,old):inbox.receive(submission)
  for id in ('mobile-manual','mobile-training','old-free-timer'):
   inbox.approve(id);inbox.approve(id)
  s=self.repo.read('main')['state'];self.assertEqual(len(s['advancement']['sessions']),3);self.assertEqual(sum(r['durationMs'] for r in s['advancement']['sessions']),3000000)
  cfg=form_config(s);self.assertEqual(cfg['activities'],[dict(id='run',domainId=self.did,name='跑步')]);self.assertNotIn('手机原文',str(cfg))
  zip=self.root/'bundle.zip';create_bundle(self.root/'data/personal.sqlite3',zip);restore(zip,self.root/'restored');restored=Repository(self.root/'restored').read('main')['state'];self.assertEqual(s,restored)
 def test_invalid_manual_never_enters_inbox(self):
  for n in (0,-1,86400001,60000.5,True):
   value=dict(version=1,kind='time',id='invalid',createdAt='2026-10-29T12:00:00+08:00',payload=dict(date='2026-10-29',domainId=self.did,durationMs=n))
   with self.assertRaises(ValueError):envelope(value)
