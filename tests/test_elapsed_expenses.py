import copy,unittest
from expense_allocation import report_rows
from personal_query import Query
from test_fixed_expenses import entry,FIXED,signed
class ElapsedExpenseTest(unittest.TestCase):
    def test_hybrid_rebasing_and_no_double_counting(self):
        rows=[entry(term=dict(FIXED)),entry('device',3100,term={'startDate':'2024-01-01','expectedEndDate':'2024-12-31'}),entry('ordinary',2000,date='2024-01-05'),entry('refund',600,date='2024-01-20',kind='refund',refundOf='device')]
        before=copy.deepcopy(rows)
        self.assertEqual(signed([r for r in report_rows(rows,'2024-01','usage_elapsed',as_of='2024-01-10') if r['date']<='2024-01-10']),6100)
        self.assertEqual(signed([r for r in report_rows(rows,'2024-01','usage_elapsed',as_of='2024-01-11') if r['date']<='2024-01-11']),6200)
        self.assertEqual(signed(report_rows(rows,'2024-01','cash')),10500)
        self.assertEqual(signed(report_rows([rows[0]],'2024-01','usage_elapsed',as_of='2024-01-10')),signed(report_rows([rows[0]],'2024-01','usage')))
        state={'expenses':{'entries':rows,'categories':[{'id':'food','name':'餐饮'}]}}
        self.assertEqual(Query.expenses(state,{'month':'2024-01','basis':'usage_elapsed'})['netCents'],signed(report_rows(rows,'2024-01','usage_elapsed')))
        self.assertEqual(rows,before)
    def test_cross_month_conservation_and_future_settlement(self):
        rows=[entry(term={'startDate':'2023-12-01','expectedEndDate':'2025-01-01'},amount=6001,date='2023-12-01')]
        self.assertEqual(sum(signed(report_rows(rows,m,'usage_elapsed',as_of='2024-01-15')) for m in ('2023-12','2024-01')),6001)
        sold=[entry(amount=3100,term={'startDate':'2024-01-01','expectedEndDate':'2025-01-01','endDate':'2024-01-08','resaleCents':800,'resaleDate':'2024-01-08'})]
        self.assertEqual(signed(report_rows(sold,'2024-01','usage_elapsed',as_of='2024-01-07')),3100)
        self.assertEqual(signed(report_rows(sold,'2024-01','usage_elapsed',as_of='2024-01-10')),2300)
        self.assertEqual(signed(report_rows(rows,'2024-02','usage_elapsed',as_of='2024-01-15')),0)
