"""Monthly reports use their reporting period, independent of writing timestamps."""
import re

def monthly_folders(state):
    ids={f['id'] for f in state['folders'] if f.get('module')=='monthly' or f['name']=='月报'}
    for _ in state['folders']:
        ids.update(f['id'] for f in state['folders'] if f.get('parent') in ids)
    return ids

def infer_month(state,n):
    if re.fullmatch(r'[1-9]\d{3}-(0[1-9]|1[0-2])',n.get('period','')):return n['period']
    text=n.get('source','')+'/'+n['title']
    full=re.search(r'(?<!\d)([1-9]\d{3})[-年/](0?[1-9]|1[0-2])(?:月|[-/：:\s]|$)',text)
    if full:return f'{int(full[1]):04d}-{int(full[2]):02d}'
    month=re.match(r'\s*(0?[1-9]|1[0-2])月',n['title'])
    year=re.search(r'(?:^|/)([1-9]\d{3})(?:/|$)',n.get('source',''))
    folders={f['id']:f for f in state['folders']};f=folders.get(n['folder']);seen=set()
    while not year and f and f['id'] not in seen:
        seen.add(f['id']);year=re.fullmatch(r'([1-9]\d{3})',f['name']);f=folders.get(f.get('parent'))
    if month and year:return f'{int(year[1]):04d}-{int(month[1]):02d}'
    if n.get('dateBasis')=='月份归档':return n['date'][:7]
    return None

def migrate_monthly(state):
    ids=monthly_folders(state)
    for f in state['folders']:
        if f['name']=='月报':f['module']='monthly'
    rules=[r for r in state['rules'] if r['folder'] in ids and r['frequency']=='monthly']
    for n in state['notes']:
        if n['folder'] not in ids:continue
        month=infer_month(state,n)
        if month:
            n['period']=month
            if not n.get('ruleId') and rules:n['ruleId']=rules[0]['id']
            if n['status']=='imported' and n['body'].strip():n['status']='done'
    return state

def validate_monthly(state):
    ids=monthly_folders(state);seen=set()
    for n in state['notes']:
        if n['folder'] not in ids or 'period' not in n:continue
        if not re.fullmatch(r'[1-9]\d{3}-(0[1-9]|1[0-2])',n['period']):raise ValueError('月报所属月份无效')
        if n.get('trashed'):continue
        if n['period'] in seen:raise ValueError('这个月份已有月报，请打开已有月报或选择其他月份')
        seen.add(n['period'])
