"""Optional important-date collection; legacy states without it remain valid."""
import datetime
import re

def validate_important_dates(state):
    events=state.get('importantDates',[])
    if not isinstance(events,list) or len(events)>2000:raise ValueError('重要日子集合无效')
    ids=set()
    for e in events:
        if not isinstance(e,dict) or not isinstance(e.get('id'),str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',e['id']) or e['id'] in ids:raise ValueError('重要日子标识无效')
        ids.add(e['id'])
        if not isinstance(e.get('title'),str) or not e['title'].strip() or len(e['title'])>100:raise ValueError('重要日子名称无效')
        if e.get('calendar') not in ('solar','lunar') or e.get('repeat') not in ('none','weekly','monthly','yearly','custom'):raise ValueError('重要日子类型无效')
        if e['repeat']=='custom' and (type(e.get('interval')) is not int or not 1<=e['interval']<=999 or e.get('unit') not in ('day','week','month','year')):raise ValueError('重复间隔无效')
        if any(type(e.get(k)) is not int for k in ('year','month','day','remindDays')) or not 1901<=e['year']<=2099 or not 1<=e['month']<=12 or not 1<=e['day']<=(30 if e['calendar']=='lunar' else 31) or not 0<=e['remindDays']<=365:raise ValueError('重要日子日期或提醒天数无效')
        if e['calendar']=='solar':datetime.date(e['year'],e['month'],e['day'])
        if any(type(e.get(k)) is not bool for k in ('enabled','deleted','leap')) or e.get('missing') not in ('last','skip') or e.get('leapPolicy') not in ('regular','skip'):raise ValueError('重要日子设置无效')
        if e.get('dismissedOccurrence') is not None:
            if not isinstance(e['dismissedOccurrence'],str):raise ValueError('提醒关闭日期无效')
            datetime.date.fromisoformat(e['dismissedOccurrence'])
