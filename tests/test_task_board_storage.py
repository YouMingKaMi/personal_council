import copy,json,tempfile,unittest
from pathlib import Path
from repository import Repository
from domain import validate
from cloud_backup import create_bundle
from recovery import restore
from capture_contract import envelope,apply_capture

class TaskBoardStorageTest(unittest.TestCase):
 def test_layout_and_original_task_fields_survive_backup(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);repo=Repository(root/'data');r=repo.read('main');s=r['state']
   task={'id':'old-task','title':'旧任务','date':'2026-10-27','done':False,'folder':s['folders'][0]['id']}
   s['tasks'].append(task);before=copy.deepcopy(s['tasks'])
   s['layout'].append({'id':'task-backlog','size':'half','visible':True});repo.save('main',r['revision'],validate(s))
   create_bundle(repo.db,root/'backup.zip');restore(root/'backup.zip',root/'restored');restored=Repository(root/'restored').read('main')['state']
   self.assertEqual(restored['tasks'],before);self.assertTrue(any(l['id']=='task-backlog' for l in restored['layout']))
 def test_old_phone_and_new_plans_keep_their_contract(self):
  with tempfile.TemporaryDirectory() as tmp:
   s=Repository(Path(tmp)/'data').read('main')['state']
   def record(kind,id,**p):return {'version':1,'id':id,'kind':kind,'createdAt':'2026-10-27T10:00:00+08:00','payload':{'date':'2026-10-27','title':'手机模拟任务',**p}}
   old=record('task','old');new=record('taskPlan','new',schedule='recent')
   for r in [old,new]:envelope(r);apply_capture(s,r)
   self.assertEqual(s['tasks'][-2]['date'],'2026-10-27');self.assertNotIn('schedule',s['tasks'][-2]);self.assertIsNone(s['tasks'][-1]['date']);self.assertEqual(s['tasks'][-1]['schedule'],'recent')

if __name__=='__main__':unittest.main()
