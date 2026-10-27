import copy,json,math,sys,tempfile,unittest,zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from repository import Repository
from daily_metrics import command,validate_metrics,export_csv
from capture_contract import envelope,form_config
from mobile_inbox import MobileInbox
from cloud_backup import create_bundle
from recovery import restore

class DailyMetricsTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.repo=Repository(self.root/'data');self.original=self.repo.read('main')['state'];self.call('init')
 def tearDown(self):self.tmp.cleanup()
 def call(self,op,**p):return command(self.repo,'main',{'op':op,**p})['state']
 def mobile(self,id,date='2024-02-29',**p):return {'id':id,'kind':'metrics','version':1,'createdAt':'2024-03-01T12:00:00+08:00','payload':{'date':date,**p}}
 def test_init_preserves_existing_records_and_is_idempotent(self):
  v=self.repo.read('main');self.call('init');self.assertEqual(v,self.repo.read('main'))
  for key in ('notes','tasks','habits','treasury','chronicle'):self.assertEqual(v['state'][key],self.original[key])
  f=next(f for f in v['state']['folders'] if f.get('module')=='metrics');self.assertIn(f['id'],v['state']['pins']);self.assertEqual(v['state']['dailyMetrics']['records'],[])
 def test_zero_missing_partial_and_optimistic_edit(self):
  s=self.call('save',date='2024-02-29',values={'mood':0,'sleepMinutes':450},expected=None)
  r=s['dailyMetrics']['records'][0];self.assertNotIn('learning',r['values'])
  s=self.call('save',date=r['date'],values={'mood':None,'sleepQuality':7},expected=r['updatedAt']);n=s['dailyMetrics']['records'][0]
  self.assertEqual(n['id'],r['id']);self.assertEqual(n['values'],{'sleepMinutes':450,'sleepQuality':7})
  before=self.repo.read('main')
  with self.assertRaises(ValueError):self.call('save',date=r['date'],values={'learning':8},expected=r['updatedAt'])
  self.assertEqual(before,self.repo.read('main'))
 def test_phone_merge_conflict_ack_and_atomic_idempotency(self):
  inbox=MobileInbox(self.repo)
  for id,v in [('sleep',{'sleepMinutes':450}),('mood',{'mood':0})]:inbox.receive(envelope(self.mobile(id,values=v)))
  with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda _:inbox.approve('sleep'),range(4)))
  inbox.approve('mood');rows=self.repo.read('main')['state']['dailyMetrics']['records'];self.assertEqual(len(rows),1);self.assertEqual(rows[0]['values'],{'sleepMinutes':450,'mood':0})
  inbox.receive(envelope(self.mobile('changed',values={'mood':8})));before=self.repo.read('main')
  with self.assertRaisesRegex(ValueError,'同项'):inbox.approve('changed')
  self.assertEqual(before,self.repo.read('main'))
  inbox.approve('changed',{'date':'2024-02-29','values':{'mood':8},'replaceExisting':True})
  self.assertEqual(self.repo.read('main')['state']['dailyMetrics']['records'][0]['values'],{'sleepMinutes':450,'mood':8})
 def test_invalid_values_dates_and_unknown_fields_rejected(self):
  for v in [{'mood':11},{'sleepMinutes':1441},{'sleepMinutes':450.5},{'mood':True},{'mood':float('nan')},{'missing':5}]:
   with self.assertRaises(ValueError):self.call('save',date='2024-02-29',values=v,expected=None)
  with self.assertRaises(ValueError):self.call('save',date='2024-02-30',values={'mood':5},expected=None)
  with self.assertRaises(ValueError):envelope(self.mobile('bad',values={'mood':1},unknown='ignored'))
  with self.assertRaises(ValueError):envelope(self.mobile('bad',values={'mood':1},replaceExisting='yes'))
 def test_custom_definition_archive_delete_restore_and_backup(self):
  self.call('definition-add',id='walk',name='散步距离',kind='number',unit='公里')
  self.call('save',date='2024-02-29',values={'walk':2.5},note='=保留原文',expected=None)
  s=self.call('definition-toggle',id='walk',archived=True);self.assertEqual(s['dailyMetrics']['records'][0]['values']['walk'],2.5)
  cfg=form_config(s);self.assertTrue(next(d for d in cfg['metricDefinitions'] if d['id']=='walk')['archived']);self.assertNotIn('records',cfg);self.assertNotIn('dailyMetrics',cfg)
  r=s['dailyMetrics']['records'][0];s=self.call('delete',id=r['id'],expected=r['updatedAt'],deleted=True);r=s['dailyMetrics']['records'][0]
  s=self.call('delete',id=r['id'],expected=r['updatedAt'],deleted=False);self.assertIn("'=保留原文",export_csv(s))
  bundle=self.root/'metrics.zip';create_bundle(self.repo.db,bundle);restore(bundle,self.root/'restored');self.assertEqual(Repository(self.root/'restored').read('main')['state'],s)
 def test_phone_configuration_contains_only_definitions_and_serves_shared_model(self):
  import threading,urllib.request
  from capture_relay import Relay,make_server
  from mobile_bridge import MobileBridge
  self.call('save',date='2024-02-29',values={'mood':4},note='不发布的历史备注',expected=None)
  relay=Relay(self.root/'relay','http://127.0.0.1:8899');server=make_server(relay,'127.0.0.1',0);relay.origin='http://127.0.0.1:'+str(server.server_port)
  thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  try:
   (self.repo.root/'mobile-bridge.json').write_text(json.dumps({'url':relay.origin,'desktopToken':relay.tokens['desktopToken']}))
   self.assertIsNone(MobileBridge(MobileInbox(self.repo)).sync()['error'])
   req=urllib.request.Request(relay.origin+'/api/config',headers={'Cookie':'capture_session='+relay.tokens['phoneToken']})
   with urllib.request.urlopen(req) as response:cfg=json.load(response)
   self.assertIn('metrics',cfg['kinds']);self.assertEqual(len(cfg['metricDefinitions']),4);self.assertNotIn('不发布的历史备注',json.dumps(cfg,ensure_ascii=False));self.assertNotIn('records',cfg)
   with urllib.request.urlopen(relay.origin+'/static/daily-metrics-model.js') as response:self.assertIn(b'metricValues',response.read())
  finally:server.shutdown();server.server_close();thread.join()
