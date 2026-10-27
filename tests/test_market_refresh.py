import datetime as dt
import sys
import tempfile
import threading
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from repository import Repository,Conflict
from market import MarketService

class MarketRefreshTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.repo=Repository(Path(self.tmp.name)/'data');self.lock=threading.Lock();self.edited=False
 def tearDown(self):self.tmp.cleanup()
 def fetch(self,url):
  return {'base':'USD' if '/usd/' in url else 'HKD','quote':'CNY','rate':'7' if '/usd/' in url else '0.9','date':dt.datetime.now(dt.timezone.utc).date().isoformat()}
 def test_stale_tab_can_check_and_catches_latest_revision_when_not_due(self):
  before=self.repo.read('main');fresh=self.repo.read('main');fresh['state']['tasks'].append({'id':'edit','title':'新记录','date':'2026-10-27','done':False});self.repo.save('main',fresh['revision'],fresh['state'])
  market=MarketService(self.repo,self.fetch);r=market.refresh('main',before['revision'],True)
  self.assertTrue(r['refreshed']);self.assertEqual(r['state']['tasks'][-1]['id'],'edit')
  again=market.refresh('main',before['revision'],False);self.assertFalse(again['refreshed']);self.assertEqual(again['revision'],r['revision'])
 def test_independent_edit_during_fetch_is_preserved(self):
  def fetch(url):
   with self.lock:
    if not self.edited:
     self.edited=True;r=self.repo.read('main');r['state']['tasks'].append({'id':'during','title':'行情请求期间编辑','date':'2026-10-27','done':False});self.repo.save('main',r['revision'],r['state'])
   return self.fetch(url)
  result=MarketService(self.repo,fetch).refresh('main',1,True)
  self.assertEqual(result['state']['tasks'][-1]['id'],'during');self.assertEqual(result['state']['treasury']['market']['fx']['USD']['rate'],'7')
 def test_user_policy_change_during_fetch_wins(self):
  before=self.repo.read('main');frequency=before['state']['treasury']['market']['frequency'];changed='weekly' if frequency!='weekly' else 'daily'
  def fetch(url):
   with self.lock:
    if not self.edited:
     self.edited=True;r=self.repo.read('main');r['state']['treasury']['market']['frequency']=changed;self.repo.save('main',r['revision'],r['state'])
   return self.fetch(url)
  result=MarketService(self.repo,fetch).refresh('main',1,True)
  self.assertFalse(result['refreshed']);self.assertEqual(result['state']['treasury']['market']['frequency'],changed);self.assertEqual(result['state']['treasury']['market']['fx'],before['state']['treasury']['market']['fx'])
 def test_cas_retry_merges_latest_and_ordinary_edits_still_conflict(self):
  save=self.repo.save
  def race(space,revision,state):
   if not self.edited:
    self.edited=True;r=self.repo.read(space);r['state']['tasks'].append({'id':'race','title':'并发保存','date':'2026-10-27','done':False});save(space,r['revision'],r['state']);raise Conflict('concurrent')
   return save(space,revision,state)
  self.repo.save=race;before=self.repo.read('main');result=MarketService(self.repo,self.fetch).refresh('main',before['revision'],True)
  self.assertEqual(result['state']['tasks'][-1]['id'],'race');self.assertEqual(len(result['state']['treasury']['changes']),1)
  with self.assertRaises(Conflict):save('main',before['revision'],before['state'])

if __name__=='__main__':unittest.main()
