import copy,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from expense_allocation import allocation,report_rows
from personal_query import Query
from capture_contract import envelope
from repository import Repository
from mobile_inbox import MobileInbox
from cloud_backup import create_bundle
from recovery import restore

def entry(id='fixed',amount=6000,date='2024-01-01',term=None,**kw):
    e=dict(id=id,date=date,title='模拟固定期限费用',amountCents=amount,kind='expense',categoryId='food',necessity='necessary',deleted=False,refundOf=None,subscriptionId=None,billedOccurrence=None,createdAt='2024-01-01T00:00:00Z',updatedAt='2024-01-01T00:00:00Z')
    if term is not None:e['allocation']=term
    e.update(kw);return e
FIXED={'termType':'fixed','startDate':'2024-01-01','fixedEndDate':'2024-02-29'}
def signed(rows):return sum((-1 if e['kind']=='refund' else 1)*e['amountCents'] for e in rows)

class FixedExpensesTest(unittest.TestCase):
    def test_fixed_period_validation_and_independent_payment_date(self):
        allocation(FIXED,purchase_date='2024-01-15',allow_settlement=False)
        for a in [dict(FIXED,expectedEndDate='2024-02-29'),dict(FIXED,endDate='2024-02-20'),dict(FIXED,resaleCents=0),dict(FIXED,termType=None),dict(FIXED,termType='other'),dict(FIXED,fixedEndDate='2024-02-30'),dict(FIXED,fixedEndDate='2023-12-31'),{'startDate':'2024-01-01','fixedEndDate':'2024-02-29'},{'termType':'fixed','startDate':'2024-01-01'}]:
            with self.assertRaises(ValueError):allocation(a)
        legacy={'startDate':'2024-01-01','expectedEndDate':'2024-02-29'}
        self.assertEqual(allocation(legacy),legacy)
        with self.assertRaises(ValueError):allocation(legacy,purchase_date='2024-01-15')
    def test_cash_vs_usage_and_exact_conservation(self):
        rows=[entry(term=dict(FIXED)),entry('estimated',3100,term={'startDate':'2024-01-01','expectedEndDate':'2024-01-31'}),entry('ordinary',2000)]
        before=copy.deepcopy(rows)
        self.assertEqual(signed(report_rows(rows,'2024-01','cash')),11100)
        self.assertEqual(signed(report_rows(rows,'2024-01','usage')),8200)
        self.assertEqual(signed(report_rows(rows,'2024-02','usage')),2900)
        self.assertEqual(signed(report_rows(rows,'2024-03','usage')),0)
        self.assertEqual(sum(signed(report_rows(rows,f'2024-{m:02}','usage')) for m in range(1,13)),11100)
        self.assertEqual(before,rows)
        huge=entry(amount=99999999999,term=dict(FIXED))
        self.assertEqual(signed(report_rows([huge],'2024-01','usage'))+signed(report_rows([huge],'2024-02','usage')),huge['amountCents'])
    def test_refunds_not_deducted_twice_and_query_parity(self):
        rows=[entry(term=dict(FIXED)),entry('estimated',3100,term={'startDate':'2024-01-01','expectedEndDate':'2024-01-31'}),entry('ordinary',2000),entry('long-refund',600,date='2024-01-20',kind='refund',refundOf='fixed'),entry('ordinary-refund',200,date='2024-01-21',kind='refund',refundOf='ordinary')]
        self.assertEqual(signed(report_rows(rows,'2024-01','cash')),10300)
        self.assertEqual(signed(report_rows(rows,'2024-01','usage')),7690)
        self.assertEqual(signed(report_rows(rows,'2024-02','usage')),2610)
        state={'expenses':{'entries':rows,'categories':[{'id':'food','name':'餐饮','archived':False}],'budgets':{}}}
        self.assertEqual(Query.expenses(state,{'month':'2024-01','basis':'usage'})['netCents'],7690)
        self.assertEqual(Query.expenses(state,{'month':'2024-01','basis':'cash'})['netCents'],10300)
    def test_phone_fixed_and_old_offline_payloads_approve_once_and_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo=Repository(Path(tmp)/'data');inbox=MobileInbox(repo)
            records=[]
            for id,extra in [('fixed',{'allocation':dict(FIXED)}),('old-estimated',{'allocation':{'startDate':'2024-01-01','expectedEndDate':'2024-02-29'}}),('old-once',{})]:
                record={'version':1,'id':id,'kind':'expense','createdAt':'2024-01-01T12:00:00+08:00','payload':{'date':'2024-01-01','title':'模拟费用','amountCents':6000,'categoryId':'food','necessity':'necessary',**extra}}
                original=copy.deepcopy(record);envelope(record);self.assertEqual(original,record);inbox.receive(record);inbox.approve(id);inbox.approve(id);records.append(record)
            state=repo.read('main')['state'];rows=state['expenses']['entries'];self.assertEqual(len(rows),3)
            self.assertEqual(rows[0]['allocation'],FIXED);self.assertNotIn('termType',rows[1]['allocation']);self.assertNotIn('allocation',rows[2])
            create_bundle(repo.db,Path(tmp)/'backup.zip');restore(Path(tmp)/'backup.zip',Path(tmp)/'restore')
            self.assertEqual(Repository(Path(tmp)/'restore').read('main')['state'],state)

if __name__=='__main__':unittest.main()
