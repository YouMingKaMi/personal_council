import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from expense_allocation import allocation,report_rows
from task_domain import validate_task
from capture_contract import envelope,apply_capture
from repository import Repository
from mobile_inbox import MobileInbox
from personal_query import Query
from cloud_backup import create_bundle
from recovery import restore

def entry(**kw):
    return dict(id='purchase',date='2024-01-01',title='模拟话费',amountCents=10000,kind='expense',categoryId='food',necessity='necessary',deleted=False,refundOf=None,subscriptionId=None,billedOccurrence=None,createdAt='2024-01-01T00:00:00Z',updatedAt='2024-01-01T00:00:00Z',**kw)
def signed(rows):return sum((-1 if e['kind']=='refund' else 1)*e['amountCents'] for e in rows)
def submission(kind,payload,id='usage-sample'):
    return {'version':1,'id':id,'kind':kind,'createdAt':'2024-01-01T12:00:00+08:00','payload':payload}

class UsageTasksTest(unittest.TestCase):
    def test_leap_month_allocation_and_cash_stays_on_payment_date(self):
        e=entry(allocation={'startDate':'2024-01-01','expectedEndDate':'2024-02-29'})
        rows=[e];before=copy.deepcopy(rows)
        self.assertEqual(signed(report_rows(rows,'2024-01','cash')),10000)
        self.assertEqual(signed(report_rows(rows,'2024-02','cash')),0)
        self.assertEqual(signed(report_rows(rows,'2024-01','usage')),5166)
        self.assertEqual(signed(report_rows(rows,'2024-02','usage')),4834)
        self.assertEqual(rows,before)
    def test_settlement_resale_and_refund_restate_cost_without_duplicate_cash(self):
        e=entry(allocation={'startDate':'2024-01-01','expectedEndDate':'2024-12-31','endDate':'2024-03-31','resaleCents':3000})
        rows=[e]
        self.assertEqual(sum(signed(report_rows(rows,f'2024-{m:02}','usage')) for m in range(1,13)),7000)
        self.assertEqual(signed(report_rows(rows,'2024-03','cash')),-3000)
        e['allocation']['resaleDate']='2024-04-05'
        self.assertEqual(signed(report_rows(rows,'2024-03','cash')),0)
        self.assertEqual(signed(report_rows(rows,'2024-04','cash')),-3000)
        r={**e,'id':'refund','date':'2024-02-15','kind':'refund','refundOf':e['id'],'allocation':None,'amountCents':1000};rows.append(r)
        self.assertEqual(sum(signed(report_rows(rows,f'2024-{m:02}','usage')) for m in range(1,13)),6000)
        self.assertEqual(signed(report_rows(rows,'2024-02','cash')),-1000)
        self.assertEqual(signed(report_rows(rows,'2024-01','cash')),10000)
        e['deleted']=True;r['deleted']=True
        self.assertEqual(report_rows(rows,'2024-03','cash'),[])
        self.assertEqual(report_rows(rows,'2024-03','usage'),[])
    def test_negative_cost_and_large_amount_conservation(self):
        e=entry(allocation={'startDate':'2024-01-01','expectedEndDate':'2024-01-03','endDate':'2024-01-03','resaleCents':10001})
        rows=report_rows([e],'2024-01','usage');self.assertEqual(signed(rows),-1)
        self.assertEqual([(-1 if r['kind']=='refund' else 1)*r['amountCents'] for r in rows],[-1,0,0])
        e['amountCents']=99999999999;e['allocation'].pop('endDate');e['allocation'].pop('resaleCents')
        self.assertEqual(signed(report_rows([e],'2024-01','usage')),99999999999)
    def test_allocation_validation(self):
        a={'startDate':'2024-01-01','expectedEndDate':'2024-02-29'}
        allocation(a,purchase_date='2024-01-01')
        for change in ({'expectedEndDate':'2023-12-31'},{'expectedEndDate':'2024-02-30'},{'resaleCents':1},{'resaleCents':True},{'endDate':'2099-01-01'},{'unknown':1}):
            with self.assertRaises(ValueError):allocation({**a,**change},purchase_date='2024-01-01')
        with self.assertRaises(ValueError):allocation(a,purchase_date='2024-01-02')
        with self.assertRaises(ValueError):allocation({**a,'endDate':'2024-01-10'},allow_settlement=False)
    def test_recent_deadline_and_legacy_task_validation(self):
        validate_task({'title':'旧任务','date':'2024-01-01','done':False})
        validate_task({'title':'近期任务','schedule':'recent','date':None,'done':False})
        validate_task({'title':'截止任务','schedule':'deadline','date':None,'deadline':'2024-01-03','deadlineTime':'18:30','done':False})
        for changes in ({'date':'2024-01-01'},{'schedule':'deadline'},{'deadlineTime':'25:00'},{'completedDate':'2024-02-30'}):
            with self.assertRaises(ValueError):validate_task({'title':'近期','date':None,'schedule':'recent','done':False,**changes})
    def test_mobile_atomic_approval_old_payload_and_backup_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo=Repository(Path(tmp)/'data');inbox=MobileInbox(repo)
            samples=[submission('expense',{'date':'2024-01-01','title':'话费','amountCents':10000,'categoryId':'food','necessity':'necessary','allocation':{'startDate':'2024-01-01','expectedEndDate':'2024-02-29'}},'long'),
                     submission('taskPlan',{'date':'2024-01-01','title':'最近做一次整理','schedule':'recent'},'recent'),
                     submission('taskPlan',{'date':'2024-01-01','title':'发材料','schedule':'deadline','deadline':'2024-01-05','deadlineTime':'18:00'},'deadline'),
                     submission('task',{'date':'2024-01-02','title':'旧离线任务'},'old-task'),
                     submission('expense',{'date':'2024-01-02','title':'旧离线消费','amountCents':1200,'categoryId':'food','necessity':'necessary'},'old-expense')]
            for record in samples:envelope(record);inbox.receive(record);inbox.approve(record['id']);inbox.approve(record['id'])
            state=repo.read('main')['state'];self.assertEqual(len(state['expenses']['entries']),2)
            self.assertEqual(len(state['tasks']),3);self.assertIsNone(state['tasks'][0]['date']);self.assertEqual(state['tasks'][0]['schedule'],'recent')
            self.assertNotIn('schedule',state['tasks'][2]);self.assertNotIn('allocation',state['expenses']['entries'][1])
            create_bundle(repo.db,Path(tmp)/'backup.zip');restore(Path(tmp)/'backup.zip',Path(tmp)/'restored')
            self.assertEqual(Repository(Path(tmp)/'restored').read('main')['state'],state)
    def test_readonly_query_matches_both_reporting_bases(self):
        rows=[entry(allocation={'startDate':'2024-01-01','expectedEndDate':'2024-02-29'})]
        state={'expenses':{'entries':rows,'categories':[{'id':'food','name':'餐饮','archived':False}],'budgets':{}}}
        self.assertEqual(Query.expenses(state,{'month':'2024-02'})['netCents'],0)
        cost=Query.expenses(state,{'month':'2024-02','basis':'usage'})
        self.assertEqual(cost['netCents'],4834);self.assertEqual(cost['calendarDays'],29)
        self.assertEqual(cost['basis'],'usage')

if __name__=='__main__':unittest.main()
