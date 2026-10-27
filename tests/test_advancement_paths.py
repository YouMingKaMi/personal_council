import copy
import json
import unittest
import test_advancement as fixture
from advancement_domain import plan_chain,problem_scope
from advancement_service import command
from capture_contract import envelope,form_config,apply_capture

class AdvancementPathsTest(unittest.TestCase):
 setUp=fixture.AdvancementTest.setUp
 tearDown=fixture.AdvancementTest.tearDown
 call=fixture.AdvancementTest.call
 problem=fixture.AdvancementTest.problem
 def root(self):
  self.problem();self.call('plan-add',id='root',problemId='problem-1',title='查国内资源')
 def add(self,id,parent=None,**kw):return self.call('plan-add',id=id,problemId='problem-1',title=id,parentId=parent,**kw)
 def test_nested_questions_identity_cycles_and_depth(self):
  self.root();self.add('question','root',nodeType='question');s=self.add('child','question')
  self.assertEqual([q['id'] for q in plan_chain(s['advancement']['plans'],'child')],['root','question','child'])
  q=s['advancement']['plans'][0];before=self.repo.read('main')
  with self.assertRaisesRegex(ValueError,'循环'):self.call('plan-edit',id='root',expected=q['updatedAt'],parentId='child')
  self.assertEqual(self.repo.read('main'),before)
  self.call('problem-add',id='other',domainId='ai-field',title='另一问题')
  with self.assertRaises(ValueError):self.call('plan-add',id='bad',problemId='other',title='串线',parentId='root')
  for i in range(9):self.add('level-'+str(i),'child' if i==0 else 'level-'+str(i-1))
  with self.assertRaisesRegex(ValueError,'12'):self.add('too-deep','level-8')
 def test_abandoned_branch_keeps_notes_and_does_not_block_sibling(self):
  self.root();self.add('discarded','root');s=self.add('chosen','root')
  self.call('update',id='original',domainId='ai-field',problemId='problem-1',planId='discarded',date='2027-01-15',body='原文：太长，不合适\n仍保留')
  q=next(q for q in s['advancement']['plans'] if q['id']=='discarded')
  s=self.call('plan-edit',id=q['id'],expected=q['updatedAt'],status='abandoned')
  self.assertEqual(s['advancement']['updates'][0]['body'],'原文：太长，不合适\n仍保留')
  self.assertNotIn('discarded',{q['id'] for q in form_config(s)['plans']})
  with self.assertRaises(ValueError):self.call('start',domainId='ai-field',problemId='problem-1',planId='discarded',owner='w',date='2027-01-15')
  s=self.call('start',domainId='ai-field',problemId='problem-1',planId='chosen',owner='w',date='2027-01-15')
  root=next(q for q in s['advancement']['plans'] if q['id']=='root')
  with self.assertRaises(ValueError):self.call('plan-edit',id='root',expected=root['updatedAt'],status='abandoned')
  with self.assertRaises(ValueError):self.call('plan-trash',id='root')
  self.assertEqual(s['advancement']['active']['planId'],'chosen')
 def test_atomic_repair_preserves_time_and_text_and_retries(self):
  self.root();self.add('child','root')
  self.add('abandoned-on-create','root',status='abandoned')
  self.call('update',id='u',domainId='ai-field',problemId='problem-1',planId='root',date='2027-01-15',body='第一节原文')
  s=self.call('start',domainId='ai-field',problemId='problem-1',planId='root',owner='w',date='2027-01-15');rid=s['advancement']['active']['id']
  self.call('heartbeat',at=self.clock+20,id=rid,owner='w')
  s=self.call('finish',at=self.clock+21.498,id=rid,note='原始备注');old=copy.deepcopy(s['advancement'])
  steps=[{'op':'update-link','id':'u','expectedPlanId':'root','planId':'child'}, {'op':'session-link','id':rid,'expectedPlanId':'root','planId':'child'}, {'op':'plan-focus','id':'child'}]
  c={'op':'path-restructure','commandId':'repair-stable','problemId':'problem-1','expected':problem_scope(old,'problem-1'),'steps':steps}
  s=command(self.repo,'main',c,self.clock+22)['state'];new=s['advancement']
  before=copy.deepcopy(old['sessions'][0]);before['planId']='child';self.assertEqual(before,new['sessions'][0])
  before=copy.deepcopy(old['updates'][0]);before['planId']='child';self.assertEqual(before,new['updates'][0])
  self.assertEqual(new['sessions'][0]['durationMs'],21498)
  again=command(self.repo,'main',c,self.clock+22)['state'];self.assertEqual(again,s)
  stale={**c,'commandId':'stale'}
  with self.assertRaises(ValueError):command(self.repo,'main',stale,self.clock+22)
  snap=self.repo.read('main');bad={'op':'path-restructure','commandId':'bad','problemId':'problem-1','expected':problem_scope(new,'problem-1'),'steps':[{'op':'update-link','id':'u','expectedPlanId':'child','planId':'root'},{'op':'session-link','id':rid,'expectedPlanId':'wrong','planId':'root'}]}
  with self.assertRaises(ValueError):command(self.repo,'main',bad,self.clock+23)
  self.assertEqual(self.repo.read('main'),snap)
 def test_mobile_legacy_and_nested_plan_promote_and_restore(self):
  self.root();self.add('question','root',nodeType='question')
  old={'version':1,'id':'legacy','createdAt':'2027-01-15T12:00:00+08:00','kind':'plan','payload':{'date':'2027-01-15','domainId':'ai-field','problemId':'problem-1','title':'旧离线方案','body':''}}
  s=self.repo.read('main')['state'];apply_capture(s,envelope(old))
  new=copy.deepcopy(old);new['id']='nested';new['payload'].update(parentId='question',nodeType='solution',title='手机子方案');apply_capture(s,envelope(new))
  self.assertEqual(s['advancement']['plans'][-1]['parentId'],'question')
  cfg=form_config(s);self.assertEqual(next(q for q in cfg['plans'] if q['id']=='question')['nodeType'],'question')
  self.assertNotIn('body',cfg['plans'][-1]);self.assertNotIn('updates',cfg)
  self.call('update',id='u',domainId='ai-field',problemId='problem-1',planId='root',date='2027-01-15',body='可以试另一种方法')
  s=self.call('plan-from-update',updateId='u',parentId='root',attachRecord=True,nodeType='question')
  q=s['advancement']['plans'][-1];self.assertEqual(s['advancement']['updates'][-1]['planId'],q['id']);self.assertEqual(q['parentId'],'root')
  from cloud_backup import create_bundle
  from recovery import restore
  from repository import Repository
  bundle=self.path/'hierarchy.zip';create_bundle(self.repo.db,bundle);restore(bundle,self.path/'hierarchy-restore')
  self.assertEqual(Repository(self.path/'hierarchy-restore').read('main')['state'],s)
 def test_relay_nested_config_and_static_path_module(self):
  import threading,urllib.request
  from capture_relay import Relay,make_server
  from mobile_bridge import MobileBridge
  from mobile_inbox import MobileInbox
  self.root();self.add('question','root',nodeType='question')
  relay=Relay(self.path/'relay','http://127.0.0.1:8899');server=make_server(relay,'127.0.0.1',0);relay.origin='http://127.0.0.1:'+str(server.server_port)
  thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  try:
   (self.repo.root/'mobile-bridge.json').write_text(json.dumps({'url':relay.origin,'desktopToken':relay.tokens['desktopToken']}))
   self.assertIsNone(MobileBridge(MobileInbox(self.repo)).sync()['error'])
   req=urllib.request.Request(relay.origin+'/api/config',headers={'Cookie':'capture_session='+relay.tokens['phoneToken']})
   with urllib.request.urlopen(req) as response:cfg=json.load(response)
   self.assertEqual(next(q for q in cfg['plans'] if q['id']=='question')['parentId'],'root')
   with urllib.request.urlopen(relay.origin+'/static/plan-path.js') as response:self.assertIn(b'planChain',response.read())
  finally:server.shutdown();server.server_close();thread.join()
