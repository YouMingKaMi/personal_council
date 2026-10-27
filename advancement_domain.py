"""Optional advancement contract; existing v8 collections retain their meaning."""
import datetime as dt
import math
import re


def ident(v):
    if not isinstance(v, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', v):
        raise ValueError('推进记录标识无效')
    return v


def text(v, limit=100000, required=False):
    if not isinstance(v, str) or len(v)>limit or (required and not v.strip()):
        raise ValueError('推进内容为空或过长')
    return v


def day(v):
    if not isinstance(v,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',v) or not '1901-01-01'<=v<='2099-12-31':
        raise ValueError('推进日期无效')
    dt.date.fromisoformat(v)
    return v


def number(v):
    if type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=7258118400000:
        raise ValueError('计时数值无效')
    return v


def validate_advancement(state):
    a=state.get('advancement')
    if a is None:return
    if not isinstance(a,dict) or (type(a.get('version')) is not int or a['version']!=1):raise ValueError('推进台版本无效')
    for key in ('domains','issues','updates','sessions','commands'):
        if not isinstance(a.get(key),list) or len(a[key])>20000:raise ValueError('推进集合无效')
        if key!='commands':
            ids=[ident(x.get('id')) for x in a[key] if isinstance(x,dict)]
            if len(ids)!=len(a[key]) or len(set(ids))!=len(ids):raise ValueError('推进标识重复')
    if 'plans' in a:
        rows=a['plans']
        if not isinstance(rows,list) or len(rows)>20000 or any(not isinstance(q,dict) for q in rows):raise ValueError('方案集合无效')
        ids=[ident(q.get('id')) for q in rows]
        if len(set(ids))!=len(ids):raise ValueError('方案标识重复')
    plans={q['id']:q for q in a.get('plans',[])}
    if any(not isinstance(x,str) for x in a['commands']):raise ValueError('推进请求标识无效')
    domains={d['id']:d for d in a['domains']};issues={p['id']:p for p in a['issues']}
    if 'workbench' in a:
        w=a['workbench']
        if not isinstance(w,dict):raise ValueError('工作台设置无效')
        for key in ('focusDomainIds','temporaryDomainIds'):
            ids=w.get(key)
            if not isinstance(ids,list) or any(not isinstance(id,str) or id not in domains for id in ids) or len(set(ids))!=len(ids):raise ValueError('工作台领域无效')
        if w.get('temporaryDate') is not None:day(w['temporaryDate'])
        elif w['temporaryDomainIds']:raise ValueError('临时领域缺少日期')
    folders={f['id'] for f in state['folders']};notes={n['id'] for n in state['notes']}
    if a.get('scienceRootId') is not None:
        ident(a['scienceRootId'])
        if a['scienceRootId'] not in folders:raise ValueError('中科院资料空间不存在')
    for d in domains.values():
        text(d.get('name'),80,True);text(d.get('goal'),2000)
        if d.get('folderId') is not None and d['folderId'] not in folders:raise ValueError('关联领域不存在')
        if type(d.get('archived')) is not bool:raise ValueError('领域状态无效')
        if d.get('focusId') and (d['focusId'] not in issues or issues[d['focusId']]['domainId']!=d['id']):raise ValueError('当前问题不属于该领域')
    def belongs(p):
        if p.get('domainId') not in domains:raise ValueError('推进领域不存在')
        if p.get('problemId') and (p['problemId'] not in issues or issues[p['problemId']]['domainId']!=p['domainId']):raise ValueError('问题与领域不一致')
    for q in plans.values():
        belongs(q);text(q.get('title'),300,True);text(q.get('body',''))
        if not q.get('problemId') or q.get('status') not in ('open','active','done','parked') or type(q.get('deleted')) is not bool:raise ValueError('方案状态无效')
        if q.get('sourceUpdateId') is not None and not any(u['id']==q['sourceUpdateId'] and u.get('problemId')==q['problemId'] for u in a['updates']):raise ValueError('方案原记录不存在')
        if 'date' in q:day(q['date'])
    def plan_belongs(row):
        if row.get('planId') and (row['planId'] not in plans or plans[row['planId']]['problemId']!=row.get('problemId') or plans[row['planId']]['domainId']!=row['domainId']):raise ValueError('方案与问题或领域不一致')
    for p in issues.values():
        if 'date' in p:day(p['date'])
        if p.get('focusPlanId') and (p['focusPlanId'] not in plans or plans[p['focusPlanId']]['problemId']!=p['id']):raise ValueError('当前方案不属于此问题')
        belongs(p);text(p.get('title'),300,True)
        for k in ('body','next','conclusion'):text(p.get(k))
        if p.get('status') not in ('open','active','resolved','parked') or type(p.get('deleted')) is not bool:raise ValueError('问题状态无效')
        if p.get('sourceNoteId') is not None and p['sourceNoteId'] not in notes:raise ValueError('原记录不存在')
        if not isinstance(p.get('links'),list) or any(x not in notes for x in p['links']):raise ValueError('关联资料不存在')
    for u in a['updates']:
        belongs(u);plan_belongs(u);day(u.get('date'));text(u.get('body'),100000,True)
    spans=[]
    def segments(rows):
        if not isinstance(rows,list) or len(rows)>10000:raise ValueError('计时片段无效')
        for r in rows:
            if not isinstance(r,dict):raise ValueError('计时片段无效')
            start,end=number(r.get('start')),number(r.get('end'))
            if end<start:raise ValueError('计时结束早于开始')
            if end>start:spans.append((start,end))
    for s in a['sessions']:
        if 'cancelled' in s and type(s['cancelled']) is not bool:raise ValueError('计时取消状态无效')
        belongs(s);plan_belongs(s);day(s.get('date'));text(s.get('title'),300);text(s.get('note'))
        if type(s.get('deleted')) is not bool or type(s.get('manual')) is not bool:raise ValueError('计时记录状态无效')
        number(s.get('durationMs'))
        if s['durationMs']>86400000*30:raise ValueError('计时记录过长')
        if not s['deleted']:
            segments(s.get('segments'))
            if not s['manual'] and s['durationMs']!=sum(r['end']-r['start'] for r in s['segments']):raise ValueError('计时合计不一致')
    active=a.get('active')
    if active is not None:
        belongs(active);plan_belongs(active);ident(active.get('id'));ident(active.get('owner'));text(active.get('title'),300)
        if active.get('status') not in ('running','paused'):raise ValueError('当前计时状态无效')
        day(active.get('date'));segments(active.get('segments'));number(active.get('lastSeen'))
        if active['status']=='running':
            number(active.get('segmentStart'))
            if active['lastSeen']<active['segmentStart']:raise ValueError('计时心跳无效')
            spans.append((active['segmentStart'],active['lastSeen']))
        elif active.get('segmentStart') is not None:raise ValueError('暂停片段无效')
    spans.sort()
    if any(spans[i][0]<spans[i-1][1] for i in range(1,len(spans))):raise ValueError('计时片段重叠')
