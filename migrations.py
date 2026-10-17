"""Idempotent v1 -> v2 migration; preserve original text and ambiguous date ranges."""
import copy
import datetime as dt
import hashlib
import re
from zoneinfo import ZoneInfo


def key(text):
    return hashlib.sha256(text.encode()).hexdigest()[:24]


def upgrade_v2(original, effective=None):
    if original.get('schemaVersion') == 2:
        return copy.deepcopy(original)
    if original.get('schemaVersion') != 1:
        raise ValueError('不支持的数据版本')
    s = copy.deepcopy(original)
    effective = effective or dt.datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()
    special = {'习惯记录库':'habits', '每日任务':'tasks', '编年史':'chronicle'}
    for f in s['folders']:
        if f['name'] in special:
            f['module'] = special[f['name']]
    for h in s['habits']:
        config = {k:copy.deepcopy(h[k]) for k in ('name','target','unit','days','enabled')}
        baseline = dict(config, id=key(h['id']+'/baseline'), fromDate='0001-01-01', kind='number', items=[], policy='all')
        h['versions'] = [baseline]
        h['entries'] = {day:{'value':value,'versionId':baseline['id']} for day,value in h['logs'].items()}
        if h['name'] == '饮食':
            start = effective
            if any(day >= start for day in h['entries']):
                start = (dt.date.fromisoformat(max(h['entries'])) + dt.timedelta(days=1)).isoformat()
            h['versions'].append(dict(config, id=key(h['id']+'/diet-v2'), fromDate=start, kind='checklist', policy='all', target=3, unit='项', items=[{'id':key(h['id']+'/'+name),'name':name} for name in ('水果','坚果','鱼油')]))
    history_ids = {f['id'] for f in s['folders'] if f.get('module') in ('habits','chronicle')}
    for _ in s['folders']:
        history_ids.update(f['id'] for f in s['folders'] if f.get('parent') in history_ids)
    for n in s['notes']:
        if n['folder'] in history_ids:
            n['readOnlyArchive'] = True
    events, day_states = [], {}
    chronicle_folders = {f['id'] for f in s['folders'] if f.get('module') == 'chronicle'}
    changed = True
    while changed:
        before = len(chronicle_folders)
        chronicle_folders.update(f['id'] for f in s['folders'] if f.get('parent') in chronicle_folders)
        changed = before != len(chronicle_folders)
    for n in s['notes']:
        if n['folder'] not in chronicle_folders or n.get('trashed'):
            continue
        text = n['body']
        year = int(n['date'][:4])
        monthly = bool(re.search(r'\d+月$', n['title']))
        current = None if monthly else n['date'] if n.get('ruleId') == 'chronicle' else None
        end_date = None
        buffer = []
        def flush():
            nonlocal buffer
            body = '\n'.join(buffer).strip()
            if body and current:
                events.append({'id':key(n['id']+'/'+str(len(events))), 'date':current, 'endDate':end_date, 'text':body, 'sourceNote':n['id'], 'createdAt':n['createdAt'], 'updatedAt':n['updatedAt']})
            buffer = []
        for line in text.splitlines():
            label = line.strip().strip('#* ').strip()
            m = re.fullmatch(r'(\d{1,2})[./](\d{1,2})(?:\s*[-—~至]\s*(?:(\d{1,2})[./])?(\d{1,2}))?', label)
            if m:
                flush()
                try:
                    current = dt.date(year,int(m[1]),int(m[2])).isoformat()
                    end_date = dt.date(year,int(m[3] or m[1]),int(m[4])).isoformat() if m[4] else None
                except ValueError:
                    current = None
                    end_date = None
            elif current:
                if re.match(r'^\s*[-*]\s+',line):
                    flush()
                    buffer = [re.sub(r'^\s*[-*]\s+','',line)]
                elif not line.strip() or line.startswith('#'):
                    flush()
                else:
                    buffer.append(line)
        flush()
        if n.get('ruleId') == 'chronicle' and n.get('status') == 'done':
            day_states[n['date']] = {'complete':True,'updatedAt':n['updatedAt']}
        n['legacyChronicle'] = True
    s['chronicle'] = {'events':events, 'days':day_states}
    s['schemaVersion'] = 2
    s['migrationInfo'] = {'from':1,'date':effective,'eventCount':len(events)}
    return s


def upgrade_v3(original, effective=None):
    if original.get('schemaVersion') == 3:
        return copy.deepcopy(original)
    s = upgrade_v2(original, effective)
    for f in s['folders']:
        if f['name'] == '国库':
            f['module'] = 'treasury'
    treasury_folders = {f['id'] for f in s['folders'] if f.get('module') == 'treasury'}
    for _ in s['folders']:
        treasury_folders.update(f['id'] for f in s['folders'] if f.get('parent') in treasury_folders)
    for n in s['notes']:
        if n['folder'] in treasury_folders:
            n['readOnlyArchive'] = True
    assets = []
    for name, symbol, category, unit in [('人民币','CNY','cash','元'),('比特币','BTC','crypto','BTC'),('以太坊','ETH','crypto','ETH'),('USD Coin','USDC','crypto','USDC'),('外部个人投资','CNY-INV','investment','元')]:
        assets.append({'id':key('treasury/'+symbol),'name':name,'symbol':symbol,'category':category,'unit':unit,'priceCny':'1' if category in ('cash','investment') else None,'priceDate':None,'archived':False})
    s['treasury'] = {'assets':assets,'accounts':[],'changes':[],'snapshots':[]}
    s['schemaVersion'] = 3
    return s


def upgrade_v4(original, effective=None):
    if original.get('schemaVersion') == 4:
        return copy.deepcopy(original)
    s = upgrade_v3(original, effective)
    # Original manual CNY prices and historical portfolios remain untouched.
    from market_defaults import empty_market, COINS
    s['treasury']['market'] = empty_market()
    for a in s['treasury']['assets']:
        coin = COINS.get(a['symbol'].upper()) if a['category']=='crypto' else None
        a['pricingMode'] = 'auto' if coin else 'manual'
        a['quoteId'] = coin or ''
    s['schemaVersion'] = 4
    return s


def upgrade_v5(original, effective=None):
    if original.get('schemaVersion')==5:return copy.deepcopy(original)
    s=upgrade_v4(original,effective)
    s['schemaVersion']=5
    return s


def upgrade_v6(original,effective=None):
    if original.get('schemaVersion')==6:return copy.deepcopy(original)
    s=upgrade_v5(original,effective)
    for h in s['habits']:
        if h['name']!='计算机知识':continue
        for v in h['versions']:
            if v['kind']=='check':continue
            v['previousNumericRule']={'kind':v['kind'],'target':v['target'],'unit':v['unit']}
            v.update(kind='check',target=1,unit='次',items=[],policy='all')
        for date,e in h['entries'].items():
            e['checked']=e.get('legacy',{}).get('status')=='complete' or (isinstance(e.get('value'),(int,float)) and e['value']>0)
        h.update(target=1,unit='次')
    s['schemaVersion']=6
    return s


def upgrade_v7(original,effective=None):
    if original.get('schemaVersion')==7:return copy.deepcopy(original)
    from monthly_domain import migrate_monthly
    s=migrate_monthly(upgrade_v6(original,effective))
    s['schemaVersion']=7
    return s


def upgrade(original,effective=None):
    if original.get('schemaVersion')==8:return copy.deepcopy(original)
    s=upgrade_v7(original,effective)
    s['settings'].setdefault('cardOrder',{})
    s['schemaVersion']=8
    return s
