import copy
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
from repository import Repository, Conflict
from capture_contract import envelope, form_config, apply_capture
from mobile_inbox import MobileInbox
from mobile_bridge import MobileBridge
from capture_relay import Relay, make_server
from cloud_backup import create_bundle
from recovery import restore

def record(capture_kind='expense', identifier='sample-one', **payload):
    p={'date':'2026-10-26', 'title':'测试午餐','amountCents':1800,'categoryId':'food-meals','necessity':'necessary'} if capture_kind=='expense' else {'date':'2026-10-26'}
    p.update(payload)
    return {'version':1,'id':identifier,'kind':capture_kind,'createdAt':'2026-10-26T12:30:00+08:00','payload':p}

class CaptureTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.repo=Repository(self.root/'desktop');self.inbox=MobileInbox(self.repo)
    def tearDown(self):self.temp.cleanup()

    def test_roundtrip_atomic_idempotent_and_concurrent_desktop_edit(self):
        a=record();before=self.repo.read('main');self.inbox.receive(a);self.inbox.receive(a)
        self.assertEqual(self.repo.read('main'),before)
        # An independent desktop edit must survive an approval based on newer state.
        fresh=copy.deepcopy(before['state']);fresh['tasks'].append({'id':'desktop-task','title':'电脑任务','date':'2026-10-26','done':False})
        self.repo.save('main',before['revision'],fresh)
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _:self.inbox.approve(a['id']),range(4)))
        state=self.repo.read('main')['state']
        self.assertEqual(len(state['expenses']['entries']),1)
        self.assertEqual(state['tasks'][-1]['id'],'desktop-task')
        self.assertEqual(self.inbox.rows()[0]['status'],'imported')
        with self.assertRaises(Conflict):self.repo.save('main',before['revision'],before['state'])
        bundle=self.root/'backup.zip';create_bundle(self.repo.db,bundle);restore(bundle,self.root/'restored')
        restored=MobileInbox(Repository(self.root/'restored'));restored.receive(a);restored.approve(a['id'])
        self.assertEqual(len(restored.repo.read('main')['state']['expenses']['entries']),1)

    def test_contract_validation_and_no_overwrite(self):
        a=record();self.inbox.receive(a);changed=copy.deepcopy(a);changed['payload']['amountCents']=1900
        with self.assertRaises(ValueError):self.inbox.receive(changed)
        for mutate in (lambda x:x.update(version=2),lambda x:x['payload'].update(extra='unknown'),
                       lambda x:x['payload'].update(amountCents=18.0),lambda x:x['payload'].update(date='2026-02-30'),
                       lambda x:x['payload'].update(amountCents=True)):
            bad=copy.deepcopy(a);mutate(bad)
            with self.assertRaises(ValueError):envelope(bad)
        corrected={**a['payload'],'categoryId':'missing'}
        with self.assertRaises(ValueError):self.inbox.approve(a['id'],corrected)
        self.assertEqual(self.inbox.rows()[0]['status'],'pending')
        self.assertNotIn('expenses',self.repo.read('main')['state'])
        self.inbox.approve(a['id'],{**a['payload'],'amountCents':2300})
        self.assertEqual(self.repo.read('main')['state']['expenses']['entries'][0]['amountCents'],2300)

    def test_all_text_modules_preserve_unicode_and_original(self):
        original='  原话 🌙\n第二行 <script>只作文本</script>\n'
        for k,p in [('ideas',{'body':original}),('materials',{'body':original}),('chronicle',{'text':original,'endDate':'2026-10-27'}),('task',{'title':'待办：学习'})]:
            item=record(k,k,**p);self.inbox.receive(item);self.inbox.approve(k)
        state=self.repo.read('main')['state']
        self.assertEqual([n['body'] for n in state['notes']],[original,original])
        self.assertEqual(state['chronicle']['events'][0]['text'],original)
        self.assertEqual(state['schemaVersion'],8)
        self.assertFalse(state['tasks'][0]['done'])
        config=form_config(state)
        self.assertNotIn('原话',json.dumps(config,ensure_ascii=False))
        self.assertEqual(set(config),{'version','kinds','categories','habits'})

    def test_habits_versions_and_existing_entry_are_protected(self):
        s=self.repo.read('main');state=s['state']
        state['habits']=[{'id':'h','name':'测试习惯','enabled':True,'target':1,'days':[],'logs':{},'entries':{},
          'versions':[{'id':'v1','fromDate':'2026-01-01','kind':'check','name':'测试习惯','unit':'','target':1,'items':[],'enabled':True,'days':[]}]}]
        self.repo.save('main',s['revision'],state)
        first=record('habit','habit-one',habitId='h',versionId='v1',kind='check',checked=True)
        self.inbox.receive(first);self.inbox.approve('habit-one')
        other=record('habit','habit-two',habitId='h',versionId='v1',kind='check',checked=False)
        self.inbox.receive(other)
        with self.assertRaisesRegex(ValueError,'已有'):self.inbox.approve('habit-two')
        self.assertTrue(self.repo.read('main')['state']['habits'][0]['entries']['2026-10-26']['checked'])

    def test_relay_permissions_and_complete_bridge_flow(self):
        relay=Relay(self.root/'relay','http://127.0.0.1:8890')
        server=make_server(relay,'127.0.0.1',0);relay.origin='http://127.0.0.1:'+str(server.server_port)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def request(path,body=None,role=None):
            headers={}
            if role=='desktop':headers['Authorization']='Bearer '+relay.tokens['desktopToken']
            if role=='phone':headers['Cookie']='capture_session='+relay.tokens['phoneToken']
            if body is not None:headers.update({'Content-Type':'application/json','X-Capture-Client':'1','Origin':relay.origin})
            req=urllib.request.Request(relay.origin+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
            with urllib.request.urlopen(req) as res:return res.status,json.load(res)
        try:
            for path,role in [('/api/config',None),('/bridge/pending','phone'),('/api/items','desktop')]:
                with self.assertRaises(urllib.error.HTTPError) as error:request(path,role=role)
                self.assertEqual(error.exception.code,401)
            with self.assertRaises(urllib.error.HTTPError):request('/api/session',{'token':'bad'})
            self.assertEqual(request('/api/session',{'token':relay.tokens['phoneToken']})[0],200)
            conf={'url':relay.origin,'desktopToken':relay.tokens['desktopToken']}
            (self.repo.root/'mobile-bridge.json').write_text(json.dumps(conf))
            bridge=MobileBridge(self.inbox);bridge.sync()
            self.assertIsNone(bridge.error)
            self.assertIn('food-meals',[c['id'] for c in request('/api/config',role='phone')[1]['categories']])
            a=record();request('/api/submit',a,'phone');request('/api/submit',a,'phone')
            bridge.sync();self.assertEqual(len(self.inbox.rows()),1)
            self.assertNotIn('expenses',self.repo.read('main')['state'])
            self.inbox.approve(a['id']);bridge.sync()
            self.assertEqual(request('/api/items',role='phone')[1]['items'][0]['status'],'imported')
            self.assertEqual(request('/bridge/pending',role='desktop')[1]['items'],[])
            for path in ('/api/state','/credentials.json','/api/approve'):
                with self.assertRaises(urllib.error.HTTPError):request(path,{} if path.endswith('approve') else None,'phone')
        finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__': unittest.main()
