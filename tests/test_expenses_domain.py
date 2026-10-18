from contextlib import closing
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from expenses_domain import validate_expenses
from domain import validate
from repository import Repository, Conflict
from cloud_backup import create_bundle
from recovery import restore

class ExpenseTests(unittest.TestCase):
    def ledger(self):
        return dict(categories=[dict(id='food',name='餐饮',archived=False)],entries=[],budgets={},subscriptions=[])
    def entry(self,**kw):
        e=dict(id='e',title='午饭',amountCents=1250,date='2026-10-18',categoryId='food',necessity='necessary',kind='expense',refundOf=None,subscriptionId=None,billedOccurrence=None,deleted=False,createdAt='2026-10-18T00:00:00Z',updatedAt='2026-10-18T00:00:00Z');e.update(kw);return e
    def test_legacy_and_amount_validation(self):
        validate_expenses({})
        for bad in (True,1.5,-1,0,'1250',10**12):
            x=self.ledger();x['entries']=[self.entry(amountCents=bad)]
            with self.assertRaises(ValueError):validate_expenses(dict(expenses=x))
        for changes in (dict(date='2026-02-30'),dict(necessity='guess'),dict(categoryId='missing'),dict(deleted=0)):
            x=self.ledger();x['entries']=[self.entry(**changes)]
            with self.assertRaises(ValueError):validate_expenses(dict(expenses=x))
    def test_refund_invariants_and_duplicate_bills(self):
        x=self.ledger();x['entries']=[self.entry(),self.entry(id='r',kind='refund',refundOf='e',amountCents=250,date='2026-11-01')];validate_expenses(dict(expenses=x))
        for changes in (dict(amountCents=1251),dict(date='2026-10-17'),dict(necessity='optional')):
            bad=copy.deepcopy(x);bad['entries'][1].update(changes)
            with self.assertRaises(ValueError):validate_expenses(dict(expenses=bad))
        x['subscriptions']=[dict(id='bill',title='月费',amountCents=1250,categoryId='food',necessity='necessary',deleted=False,enabled=True,anchorDate='2026-10-18',nextIndex=1,cycle='monthly')]
        x['entries'][0].update(subscriptionId='bill',billedOccurrence='2026-10-18');validate_expenses(dict(expenses=x))
        x['entries'].append(self.entry(id='duplicate',subscriptionId='bill',billedOccurrence='2026-10-18'))
        with self.assertRaises(ValueError):validate_expenses(dict(expenses=x))
    def test_budget_and_roundtrip_recovery(self):
        x=self.ledger();x['budgets']={'2026-10':dict(total=200000,optional=50000)};x['entries']=[self.entry()]
        validate_expenses(dict(expenses=x))
        x['budgets']['2026-10']['optional']=200001
        with self.assertRaises(ValueError):validate_expenses(dict(expenses=x))
        x['budgets']['2026-10']['optional']=50000
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);repo=Repository(p/'data');before=repo.read('main');s=before['state'];s['expenses']=x;s['layout']=[l for l in s['layout'] if l['id']!='expenses']+[dict(id='expenses',size='half',visible=True)];validate(s)
            revision=repo.save('main',before['revision'],s)
            with self.assertRaises(Conflict):repo.save('main',before['revision'],s)
            out=p/'bundle.zip';create_bundle(repo.db,out);restore(out,p/'restored')
            with closing(sqlite3.connect(p/'restored'/'personal.sqlite3')) as c:
                body=json.loads(c.execute("SELECT body FROM spaces WHERE name='main'").fetchone()[0]);self.assertEqual(body['expenses'],x);self.assertEqual(body['treasury'],before['state']['treasury'])
