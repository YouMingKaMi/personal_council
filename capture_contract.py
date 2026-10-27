"""Immutable mobile capture contract v1; adapters add records to desktop schema v8.

Never accept a whole workspace from a phone. No existing record is overwritten.
"""
import datetime as dt
import json
import math
import re

KINDS = {'expense': '花销', 'task': '任务', 'taskPlan':'任务', 'chronicle': '编年史',
         'ideas': '想法暂存', 'materials': '信息原料', 'habit': '习惯记录', 'problem':'新问题', 'progress':'推进进展', 'plan':'解决方案', 'focus':'推进计时','metrics':'每日指标'}
FIELDS = {
    'metrics': {'date','values','note','replaceExisting'},
    'expense': {'date', 'title', 'amountCents', 'categoryId', 'necessity', 'allocation'},
    'problem': {'date','domainId','title','body','next'},
    'progress': {'date','domainId','problemId','planId','body'},
    'plan': {'date','domainId','problemId','title','body','parentId','nodeType'},
    'focus': {'date','domainId','problemId','planId','title','note','segments','durationMs','adjustedDurationMs'},
    'taskPlan': {'date','title','schedule','scheduledDate','deadline','deadlineTime'},
    'task': {'date', 'title'}, 'chronicle': {'date', 'text', 'endDate'},
    'ideas': {'date', 'body'}, 'materials': {'date', 'body'},
    'habit': {'date', 'habitId', 'versionId', 'kind', 'value', 'checked', 'items'},
}

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def text(value, maximum=100000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError('内容为空或超过长度限制')
    return value

def day(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value) or not '1901-01-01' <= value <= '2099-12-31':
        raise ValueError('日期无效')
    dt.date.fromisoformat(value)
    return value

def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', value):
        raise ValueError('标识无效')
    return value

def focus_payload(p,submitted_at):
    identifier(p.get('domainId'))
    if p.get('problemId') is not None:identifier(p['problemId'])
    if p.get('planId') is not None:identifier(p['planId']);identifier(p.get('problemId'))
    for key,limit in [('title',300),('note',100000)]:
        if not isinstance(p.get(key,''),str) or len(p.get(key,''))>limit:raise ValueError('计时说明无效')
    rows=p.get('segments')
    if not isinstance(rows,list) or not 1<=len(rows)<=1000:raise ValueError('计时片段为空或过多')
    previous=0;duration=0
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'start','end'}:raise ValueError('计时片段格式无效')
        start,end=row['start'],row['end']
        if any(type(n) is not int or not 0<=n<=7258118400000 for n in (start,end)) or end<=start or start<previous:raise ValueError('计时时间无效、倒序或重叠')
        duration+=end-start;previous=end
    if type(p.get('durationMs')) is not int or p['durationMs']!=duration or not 0<duration<=30*86400000:raise ValueError('计时合计不一致或超过 30 天，请检查')
    if previous>submitted_at.timestamp()*1000+300000:raise ValueError('计时结束晚于提交时间，请检查设备时间')
    if 'adjustedDurationMs' in p and (type(p['adjustedDurationMs']) is not int or not 0<=p['adjustedDurationMs']<=86400000):raise ValueError('修正时长须为 0—24 小时')
    start_day=dt.datetime.fromtimestamp(rows[0]['start']/1000,dt.timezone(dt.timedelta(hours=8))).date().isoformat()
    if p['date']!=start_day and 'adjustedDurationMs' not in p:raise ValueError('计时日期须与实际开始日期一致')

def envelope(value):
    if not isinstance(value, dict) or set(value) != {'version', 'id', 'kind', 'createdAt', 'payload'}:
        raise ValueError('提交格式不兼容，原稿仍保留，请更新页面')
    if type(value['version']) is not int or value['version'] != 1:
        raise ValueError('不支持的提交版本，原稿仍保留')
    identifier(value['id'])
    if len(value['id']) > 64:
        raise ValueError('提交标识过长')
    stamp = dt.datetime.fromisoformat(text(value['createdAt'], 50).replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('提交时间须包含时区')
    kind, p = value['kind'], value['payload']
    if kind not in KINDS or not isinstance(p, dict) or set(p) - FIELDS[kind]:
        raise ValueError('功能或字段不兼容，不能忽略未知字段')
    day(p.get('date'))
    if kind=='metrics':
        v=p.get('values')
        if not isinstance(v,dict) or len(v)>100:raise ValueError('指标格式无效')
        for id,n in v.items():
            identifier(id)
            if type(n) not in (int,float) or not math.isfinite(n) or abs(n)>1e9:raise ValueError('指标数值无效')
        if not isinstance(p.get('note',''),str) or len(p.get('note',''))>10000:raise ValueError('指标备注过长')
        if not v and not p.get('note','').strip():raise ValueError('至少填写一项指标或备注')
        if 'replaceExisting' in p and type(p['replaceExisting']) is not bool:raise ValueError('指标更新确认无效')
    if kind=='focus':focus_payload(p,stamp)
    if kind in ('problem','progress','plan'):
        identifier(p.get('domainId'))
        if kind in ('problem','plan'):
            text(p.get('title'),300)
            for key in ('body','next'):
                if not isinstance(p.get(key,''),str) or len(p.get(key,''))>100000:raise ValueError('问题内容无效')
            if kind=='plan':
                identifier(p.get('problemId'))
                if p.get('parentId') is not None:identifier(p['parentId'])
                if p.get('nodeType','solution') not in ('solution','question'):raise ValueError('路径类型无效')
        else:
            text(p.get('body'))
            if p.get('problemId') is not None:identifier(p['problemId'])
            if p.get('planId') is not None:
                identifier(p['planId']);identifier(p.get('problemId'))
    if kind=='taskPlan':
        from task_domain import validate_task
        text(p.get('title'),120)
        validate_task({'title':p['title'],'done':False,'date':p.get('scheduledDate'),'schedule':p.get('schedule'),'deadline':p.get('deadline'),'deadlineTime':p.get('deadlineTime')})
    if kind in ('task', 'expense'):
        text(p.get('title'), 120)
    if kind in ('ideas', 'materials'):
        text(p.get('body'))
    if kind == 'chronicle':
        text(p.get('text'))
        if p.get('endDate') is not None and day(p['endDate']) < p['date']:
            raise ValueError('结束日期不能早于开始日期')
    if kind == 'expense':
        if type(p.get('amountCents')) is not int or not 1 <= p['amountCents'] <= 99999999999:
            raise ValueError('金额须为正整数分')
        if p.get('allocation') is not None:
            from expense_allocation import allocation
            allocation(p['allocation'],purchase_date=p['date'],allow_settlement=False)
        identifier(p.get('categoryId'))
        if p.get('necessity') not in ('necessary', 'optional', 'undecided'):
            raise ValueError('请选择必要性')
    if kind == 'habit':
        identifier(p.get('habitId')); identifier(p.get('versionId'))
        entry_kind = p.get('kind')
        expected = {'date', 'habitId', 'versionId', 'kind'} | {'number': {'value'}, 'check': {'checked'}, 'checklist': {'items'}}.get(entry_kind, set())
        if entry_kind not in ('number', 'check', 'checklist') or set(p) != expected:
            raise ValueError('习惯记录类型或字段不一致')
        if entry_kind == 'number' and (type(p['value']) not in (int, float) or not math.isfinite(p['value']) or not 0 <= p['value'] <= 1e9):
            raise ValueError('习惯数量无效')
        if entry_kind == 'check' and type(p['checked']) is not bool:
            raise ValueError('打卡状态无效')
        if entry_kind == 'checklist':
            if not isinstance(p['items'], dict) or len(p['items']) > 100:
                raise ValueError('清单无效')
            for key, val in p['items'].items():
                identifier(key)
                if type(val) is not bool: raise ValueError('清单状态无效')
    return value

def expense_ledger(state):
    if 'expenses' in state: return state['expenses']
    pairs = [('food','餐饮'),('living','居住与日用'),('transport','交通'),('health','健康'),('tools','学习与工具'),('leisure','娱乐与购物'),('social','人情'),('other','其他')]
    return {'entries': [], 'categories': [{'id': i, 'name': n, 'archived': False} for i,n in pairs] + [
        {'id':'food-coffee','name':'咖啡','parentId':'food','archived':False},
        {'id':'food-meals','name':'正餐','parentId':'food','archived':False}], 'budgets': {}, 'subscriptions': []}

def form_config(state):
    cats = expense_ledger(state)['categories']
    by_id = {c['id']: c for c in cats}
    active = []
    for c in cats:
        path, node = [], c
        while node:
            if node['archived']: break
            path.insert(0, node['name']); node = by_id.get(node.get('parentId'))
        else:
            active.append({'id': c['id'], 'name': ' / '.join(path)})
    modules = {f.get('module') for f in state['folders']}
    kinds = {k: v for k,v in KINDS.items() if k not in ('ideas','materials') or k in modules}
    habits = [{'id': h['id'], 'name': h['name'], 'versions': [
        {k: v[k] for k in ('id','fromDate','kind','name','unit','items','enabled','target') if k in v}
        for v in h.get('versions', [])]} for h in state['habits'] if h.get('versions')]
    if 'dailyMetrics' not in state:kinds.pop('metrics',None)
    advancement=state.get('advancement',{})
    fields=[{'id':d['id'],'name':d['name']} for d in advancement.get('domains',[]) if not d['archived']]
    field_ids={d['id'] for d in fields}
    if not fields:
        kinds={k:v for k,v in kinds.items() if k not in ('problem','progress','plan','focus')}
    problems=[{k:p[k] for k in ('id','domainId','title')} for p in advancement.get('issues',[]) if p['domainId'] in field_ids and not p['deleted'] and p['status'] in ('open','active')]
    problem_ids={p['id'] for p in problems}
    from advancement_domain import plan_available
    plan_by_id={q['id']:q for q in advancement.get('plans',[])}
    plans=[{**{k:q[k] for k in ('id','domainId','problemId','title')},
            **({'parentId':q['parentId']} if q.get('parentId') else {}),
            **({'nodeType':'question'} if q.get('nodeType')=='question' else {})}
           for q in advancement.get('plans',[]) if q['problemId'] in problem_ids and plan_available(plan_by_id,q['id'])]
    focused=[id for id in advancement.get('workbench',{}).get('focusDomainIds',[]) if id in field_ids]
    return {**({'metricDefinitions':state['dailyMetrics']['definitions']} if 'dailyMetrics' in state else {}),'version': 1, 'kinds': kinds, 'categories': active, 'habits': habits, **({'domains':fields, 'problems':problems, 'plans':plans,'focusDomainIds':focused} if 'advancement' in state else {})}

def apply_capture(state, submission):
    from domain import validate
    envelope(submission)
    kind, p = submission['kind'], submission['payload']
    record_id, stamp = 'mobile-' + submission['id'], now()
    if kind=='metrics':
        from daily_metrics import save_day
        record_id=save_day(state,p,stamp,mobile=True)
    elif kind=='focus':
        from mobile_timer import import_timer
        import_timer(state,p,record_id,stamp)
    elif kind in ('problem','progress','plan'):
        from advancement_service import add_issue,add_update,add_plan
        if kind=='problem':add_issue(state,p,record_id,stamp)
        elif kind=='plan':add_plan(state,p,record_id,stamp)
        else:add_update(state,p,record_id,stamp)
    elif kind in ('ideas', 'materials'):
        folder = next((f for f in state['folders'] if f.get('module') == kind), None)
        if not folder: raise ValueError('对应记录空间已不存在，请先恢复空间')
        if any(n['id'] == record_id for n in state['notes']): raise ValueError('记录标识冲突')
        title = next(x.strip()[:80] for x in p['body'].splitlines() if x.strip()) if kind == 'ideas' else p['date'] + ' · 未加工想法'
        state['notes'].append({'id':record_id,'folder':folder['id'],'date':p['date'],'title':title,
            'body':p['body'],'tags':[],'values':{},'status':'done','dateBasis':'记录日期','createdAt':stamp,'updatedAt':stamp})
    elif kind=='taskPlan':
        state['tasks'].append({'id':record_id,'title':p['title'].strip(),'date':p.get('scheduledDate'),'schedule':p['schedule'],'deadline':p.get('deadline'),'deadlineTime':p.get('deadlineTime'),'done':False})
    elif kind == 'task':
        state['tasks'].append({'id':record_id,'title':p['title'].strip(),'date':p['date'],'done':False})
    elif kind == 'chronicle':
        state['chronicle']['events'].append({'id':record_id,'date':p['date'],'endDate':p.get('endDate'),
            'text':p['text'],'deleted':False,'createdAt':stamp,'updatedAt':stamp})
    elif kind == 'expense':
        if p['categoryId'] not in {c['id'] for c in form_config(state)['categories']}:
            raise ValueError('原分类已停用或不存在，请在确认前更正分类')
        state.setdefault('expenses', expense_ledger(state))['entries'].append({
            **p,'id':record_id,'kind':'expense','deleted':False,'refundOf':None,
            'subscriptionId':None,'billedOccurrence':None,'createdAt':stamp,'updatedAt':stamp})
    else:
        h = next((h for h in state['habits'] if h['id'] == p['habitId']), None)
        versions = sorted((v for v in (h or {}).get('versions', []) if v['fromDate'] <= p['date']), key=lambda v:v['fromDate'])
        if not versions or versions[-1]['id'] != p['versionId'] or versions[-1]['kind'] != p['kind']:
            raise ValueError('这一天的习惯规则已变化，请重新选择习惯后确认')
        cfg = versions[-1]
        if not cfg['enabled']: raise ValueError('该日期的习惯已停用')
        if p['date'] in h['entries'] or p['date'] in h.get('logs', {}):
            raise ValueError('这一天已有该习惯记录，请在习惯记录库处理，手机记录不会覆盖它')
        if p['kind']=='checklist' and set(p['items']) - {i['id'] for i in cfg['items']}:
            raise ValueError('清单项目已变化')
        h['entries'][p['date']] = {k:p[k] for k in ('value','checked','items') if k in p}
        h['entries'][p['date']].update(versionId=cfg['id'], updatedAt=stamp)
    validate(state)
    return record_id

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
