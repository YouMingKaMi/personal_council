import unittest
from important_dates_domain import validate_important_dates

class ImportantDatesTests(unittest.TestCase):
    def event(self):
        return dict(id='test',title='生日',calendar='solar',year=2024,month=2,day=29,repeat='yearly',remindDays=3,leap=False,missing='last',leapPolicy='regular',enabled=True,deleted=False,dismissedOccurrence=None)
    def test_old_state_and_valid_dates(self):
        validate_important_dates({})
        validate_important_dates({'importantDates':[self.event()]})
        e=self.event();e.update(calendar='lunar',month=6,day=30,leap=True)
        validate_important_dates({'importantDates':[e]})
    def test_invalid_dates_and_types(self):
        for update in [dict(year=2026),dict(remindDays=True),dict(remindDays=-1),dict(leap=1),dict(calendar='other'),dict(dismissedOccurrence='bad')]:
            with self.subTest(update=update),self.assertRaises((ValueError,TypeError)):
                validate_important_dates({'importantDates':[{**self.event(),**update}]})
        with self.assertRaises(ValueError):validate_important_dates({'importantDates':[self.event(),self.event()]})

    def test_custom_and_legacy_recurrence(self):
        for repeat in ('none','weekly','monthly','yearly'):
            validate_important_dates({'importantDates':[{**self.event(),'repeat':repeat}]})
        validate_important_dates({'importantDates':[{**self.event(),'repeat':'custom','interval':2,'unit':'week'}]})
        for extra in ({'interval':0,'unit':'day'},{'interval':True,'unit':'week'},{'interval':2,'unit':'hour'}):
            with self.assertRaises(ValueError):validate_important_dates({'importantDates':[{**self.event(),'repeat':'custom',**extra}]})
