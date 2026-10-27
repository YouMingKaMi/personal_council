"""Small command API. Timers and problem changes commit against the latest state."""
import datetime as dt
import json
import time
import uuid
from advancement_domain import ident,text,day,number
from advancement_folders import new_domain,rename_domain,synchronize

SERVER_CLOCK_GAP_MS = 30000
INTERNAL_CLOCK_OPS = ('clock-pulse', 'clock-interrupt')
BACKGROUND_OPS = ('heartbeat', 'reconcile') + INTERNAL_CLOCK_OPS


def empty(state):
    roots={f['id'] for f in state['folders'] if f['name']=='中科院'}
    folders=[f for f in state['folders'] if f.get('parent') in roots and not f.get('module')]
    return {'version':1,'domains':[{'id':f['id'],'folderId':f['id'],'name':f['name'],'goal':'','focusId':None,'archived':False} for f in folders],
            'issues':[],'plans':[],'updates':[],'sessions':[],'active':None,'commands':[]}


def stamp(ms):return dt.datetime.fromtimestamp(ms/1000,dt.timezone.utc).isoformat()

def close_segment(active,end):
    start=active['segmentStart']
    if start is not None and end>start:active['segments'].append({'start':start,'end':end})
    active.update(segmentStart=None,status='paused',lastSeen=end)


def reconcile(a,now):
    r=a.get('active')
    limit=SERVER_CLOCK_GAP_MS if r and r.get('clockMode')=='server' else 60000
    if r and r['status']=='running' and (now-r['lastSeen']>limit or now<r['lastSeen']):
        close_segment(r,r['lastSeen']);r['interrupted']=True
        return True
    return False


def domain(a,id):
    d=next((x for x in a['domains'] if x['id']==id and not x['archived']),None)
    if not d:raise ValueError('领域不存在或已收起')
    return d


def issue(a,id):
    p=next((x for x in a['issues'] if x['id']==id and not x['deleted']),None)
    if not p:raise ValueError('问题已移除或不存在')
    return p


def add_issue(state,p,id,at):
    a=state.setdefault('advancement',empty(state));d=domain(a,p.get('domainId'))
    if any(x['id']==id for x in a['issues']):raise ValueError('问题标识冲突')
    source=p.get('sourceNoteId') or None
    if source and not any(n['id']==source and not n.get('trashed') for n in state['notes']):raise ValueError('原记录不存在')
    row={'id':id,'date':day(p.get('date') or at[:10]),'domainId':d['id'],'title':text(p.get('title'),300,True).strip(),'body':text(p.get('body','')),
         'next':text(p.get('next','')),'conclusion':'','status':'open','deleted':False,'sourceNoteId':source,'links':[],
         'createdAt':at,'updatedAt':at}
    a['issues'].append(row)
    if not d['focusId']:d['focusId']=id
    return row


def plan(a,id):
    q=next((q for q in a.get('plans',[]) if q['id']==id and not q['deleted']),None)
    if not q:raise ValueError('方案已移除或不存在')
    return q


def add_plan(state,c,id,at):
    a=state.setdefault('advancement',empty(state));p=issue(a,c.get('problemId'));domain(a,p['domainId'])
    if c.get('domainId') and c['domainId']!=p['domainId']:raise ValueError('方案与领域不一致')
    source=c.get('sourceUpdateId') or None
    if source:
        u=next((u for u in a['updates'] if u['id']==source and u.get('problemId')==p['id']),None)
        if not u:raise ValueError('原进展不属于该问题')
        existing=next((q for q in a.get('plans',[]) if q.get('sourceUpdateId')==source),None)
        if existing:
            if existing['deleted']:raise ValueError('这条记录已转为方案，请先恢复该方案')
            return existing
    if any(q['id']==id for q in a.get('plans',[])):raise ValueError('方案标识冲突')
    q={'id':ident(id),'domainId':p['domainId'],'problemId':p['id'],'title':text(c.get('title'),300,True).strip(),
       'body':text(c.get('body','')),'status':'open','deleted':False,'sourceUpdateId':source,
       'date':day(c.get('date') or at[:10]),'createdAt':at,'updatedAt':at}
    a.setdefault('plans',[]).append(q)
    if not p.get('focusPlanId'):p['focusPlanId']=id;p['updatedAt']=at
    return q


def add_update(state,p,id,at):
    a=state.setdefault('advancement',empty(state));d=domain(a,p.get('domainId'));pid=p.get('problemId') or None
    if pid and issue(a,pid)['domainId']!=d['id']:raise ValueError('问题不属于该领域')
    qid=p.get('planId') or None
    if qid:
        q=plan(a,qid)
        if q['domainId']!=d['id'] or q['problemId']!=pid:raise ValueError('进展与方案不一致')
    if any(x['id']==id for x in a['updates']):raise ValueError('进展标识冲突')
    row={'id':id,'domainId':d['id'],'problemId':pid,'date':day(p.get('date')),'body':text(p.get('body'),100000,True),'createdAt':at}
    if qid:row['planId']=qid
    a['updates'].append(row);return row


def mutate(state,c,now):
    a=state.setdefault('advancement',empty(state));op=c.get('op');at=stamp(now)
    if op in ('init','reconcile','sync-folders'):return
    if op in INTERNAL_CLOCK_OPS:
        r=a.get('active')
        # A delayed worker must never revive or affect a replacement session.
        if not r or r['id']!=c.get('id') or r['owner']!=c.get('owner') or r['status']!='running':return
        if op=='clock-interrupt':
            close_segment(r,r['lastSeen']);r['interrupted']=True
        elif r.get('clockMode')=='server' and c.get('connected') is True:
            r['lastSeen']=now
        return
    if op in ('workbench-focus','workbench-select'):
        w=a.setdefault('workbench',{'focusDomainIds':[],'temporaryDate':None,'temporaryDomainIds':[]})
        if op=='workbench-focus':
            ids=c.get('domainIds')
            if not isinstance(ids,list) or any(not isinstance(id,str) for id in ids) or len(set(ids))!=len(ids):raise ValueError('请选择有效领域')
            if c.get('expected')!=w['focusDomainIds']:raise ValueError('专注领域已在另一窗口修改，请重新打开设置')
            for id in ids:domain(a,id)
            w['focusDomainIds']=ids
        else:
            id=domain(a,c.get('domainId'))['id'];date=day(c.get('date'))
            if w['temporaryDate']!=date:w.update(temporaryDate=date,temporaryDomainIds=[])
            if id not in w['temporaryDomainIds']:w['temporaryDomainIds'].append(id)
        return
    if op=='discard':
        r=a.get('active')
        if not r or r['id']!=c.get('id'):raise ValueError('当前计时已变化，请刷新后取消')
        mutate(state,{'op':'finish','id':r['id']},now)
        a['sessions'][-1].update(deleted=True,cancelled=True)
        return
    if op=='switch':
        r=a.get('active')
        if not r or r['id']!=c.get('id'):raise ValueError('当前计时已变化，请刷新后切换')
        mutate(state,{'op':'finish','id':r['id'],'date':c['date']},now)
        mutate(state,{**c,'op':'start'},now)
        return
    if op=='domain':
        old=next((d for d in a['domains'] if d['id']==c.get('id')),None)
        if old:
            if 'goal' in c:old['goal']=text(c['goal'],2000)
            if 'name' in c:rename_domain(state,old,c['name'])
            if 'archived' in c:
                if type(c['archived']) is not bool:raise ValueError('领域状态无效')
                if a['active'] and a['active']['domainId']==old['id']:raise ValueError('请先结束该领域的计时')
                old['archived']=c['archived']
        else:
            new_domain(state,c)
    elif op=='problem-add':add_issue(state,c,c.get('id') or str(uuid.uuid4()),at)
    elif op=='plan-add':add_plan(state,c,c.get('id') or str(uuid.uuid4()),at)
    elif op=='plan-from-update':
        u=next((u for u in a['updates'] if u['id']==c.get('updateId')),None)
        if not u or not u.get('problemId'):raise ValueError('请选择某个问题下的进展记录')
        add_plan(state,{'problemId':u['problemId'],'domainId':u['domainId'],'sourceUpdateId':u['id'],
                        'title':c.get('title') or u['body'].strip().splitlines()[0][:300],
                        'body':u['body'],'date':u['date']},c.get('id') or str(uuid.uuid4()),at)
    elif op=='plan-edit':
        q=plan(a,c['id'])
        if c.get('expected')!=q['updatedAt']:raise ValueError('方案已在另一处更新，请重新打开后修改；草稿仍保留')
        changes={k:c[k] for k in ('title','body','status') if k in c}
        if changes.get('status')=='done' and q['status']!='done':
            add_update(state,{'domainId':q['domainId'],'problemId':q['problemId'],'planId':q['id'],'date':c['date'],'body':'方案已完成'},str(uuid.uuid4()),at)
        q.update(changes,updatedAt=at)
    elif op=='plan-focus':
        q=plan(a,c['id']);p=issue(a,q['problemId']);domain(a,p['domainId'])
        if q['status'] in ('done','parked'):raise ValueError('请先将方案恢复为待推进或推进中')
        p['focusPlanId']=q['id'];p['updatedAt']=at;domain(a,p['domainId'])['focusId']=p['id']
    elif op=='plan-trash':
        q=next((q for q in a.get('plans',[]) if q['id']==c['id']),None)
        if not q:raise ValueError('方案不存在')
        if a['active'] and a['active'].get('planId')==q['id']:raise ValueError('请先结束此方案的计时')
        issue(a,q['problemId']);q['deleted']=bool(c.get('deleted',True));q['updatedAt']=at
    elif op=='problem-edit':
        p=issue(a,c['id'])
        if c.get('expected')!=p['updatedAt']:raise ValueError('这个问题已在另一处更新，请重新打开后修改；当前草稿仍保留')
        changes={k:c[k] for k in ('title','body','next','conclusion','links','status') if k in c}
        if changes.get('status')=='resolved' and p['status']!='resolved':
            a['updates'].append({'id':str(uuid.uuid4()),'domainId':p['domainId'],'problemId':p['id'],'date':day(c['date']),
                                 'body':'已解决'+('：'+changes.get('conclusion',p['conclusion']) if changes.get('conclusion',p['conclusion']) else ''),'createdAt':at})
        if p['status']=='resolved' and changes.get('status') not in (None,'resolved'):
            a['updates'].append({'id':str(uuid.uuid4()),'domainId':p['domainId'],'problemId':p['id'],'date':day(c['date']),'body':'重新打开问题','createdAt':at})
        p.update(changes,updatedAt=at)
    elif op=='problem-trash':
        p=next((x for x in a['issues'] if x['id']==c['id']),None)
        if not p:raise ValueError('问题不存在')
        if a['active'] and a['active'].get('problemId')==p['id']:raise ValueError('请先结束此问题的计时')
        p['deleted']=bool(c.get('deleted',True));p['updatedAt']=at
        for d in a['domains']:
            if d['focusId']==p['id']:d['focusId']=None
    elif op=='focus':
        d=domain(a,c['domainId']);pid=c.get('problemId') or None
        if pid and issue(a,pid)['domainId']!=d['id']:raise ValueError('问题不属于此领域')
        d['focusId']=pid
    elif op=='update':add_update(state,c,c.get('id') or str(uuid.uuid4()),at)
    elif op=='task':
        p=issue(a,c['id']);title=text(c.get('title') or p['next'],200,True)
        state['tasks'].append({'id':str(uuid.uuid4()),'title':title,'date':day(c['date']),'done':False,'advancementProblemId':p['id']})
    elif op in ('start','pause','resume','finish','heartbeat'):
        r=a['active']
        if op=='start':
            if r:raise ValueError('已有计时，请先结束后切换')
            d=domain(a,c['domainId']);pid=c.get('problemId') or None;qid=c.get('planId') or None
            if qid:
                q=plan(a,qid)
                if q['domainId']!=d['id'] or q['problemId']!=pid:raise ValueError('计时与方案不一致')
                if q['status'] in ('done','parked'):raise ValueError('此方案已完成或暂放，请先重新打开')
                if q['status']=='open':q.update(status='active',updatedAt=at)
            if pid:
                p=issue(a,pid)
                if p['domainId']!=d['id']:raise ValueError('问题不属于此领域')
                d['focusId']=pid
                if qid:p['focusPlanId']=qid
                if p['status']=='open':p.update(status='active',updatedAt=at)
            a['active']={'id':str(uuid.uuid4()),'domainId':d['id'],'problemId':pid,'title':text(c.get('title',''),300),
                         'date':day(c['date']),'owner':ident(c['owner']),'status':'running','startedAt':now,'lastSeen':now,'segmentStart':now,'segments':[],'interrupted':False}
            if qid:a['active']['planId']=qid
        elif r and c.get('id')!=r['id']:raise ValueError('计时已变化，请刷新后重试')
        elif not r:
            if op!='heartbeat':raise ValueError('当前没有计时')
        elif op=='heartbeat':
            if r['status']=='running' and r['owner']==c.get('owner') and r.get('clockMode')!='server':r['lastSeen']=now
        elif op=='pause':
            if r['status']=='running':close_segment(r,now)
        elif op=='resume':
            if r['status']!='paused':raise ValueError('计时正在另一窗口运行')
            r.update(owner=ident(c['owner']),status='running',segmentStart=now,lastSeen=now,interrupted=False)
        elif op=='finish':
            if r['status']=='running':close_segment(r,now)
            note=text(c.get('note',''));a['sessions'].append({k:r[k] for k in ('id','domainId','problemId','title','date','segments')})
            s=a['sessions'][-1]
            if r.get('planId'):s['planId']=r['planId']
            s.update(manual=False,deleted=False,durationMs=sum(x['end']-x['start'] for x in r['segments']),note=note,endedAt=now)
            if note.strip():add_update(state,{'domainId':r['domainId'],'problemId':r['problemId'],'date':c.get('date',r['date']),'body':note,'planId':r.get('planId')},str(uuid.uuid4()),at)
            if 'next' in c and r['problemId']:
                p=issue(a,r['problemId']);p['next']=text(c['next']);p['updatedAt']=at
            a['active']=None
    elif op=='session-edit':
        s=next((s for s in a['sessions'] if s['id']==c['id']),None)
        if not s:raise ValueError('计时记录不存在')
        if 'deleted' in c:s['deleted']=bool(c['deleted'])
        if 'durationMs' in c:
            duration=number(c['durationMs'])
            if duration>86400000:raise ValueError('单次补记不能超过 24 小时')
            if 'original' not in s:s['original']={k:s[k] for k in ('segments','durationMs','manual')}
            s.update(manual=True,segments=[],durationMs=duration)
        if 'note' in c:s['note']=text(c['note'])
    elif op=='manual':
        d=domain(a,c['domainId']);pid=c.get('problemId') or None
        if pid and issue(a,pid)['domainId']!=d['id']:raise ValueError('问题不属于此领域')
        qid=c.get('planId') or None
        if qid:
            q=plan(a,qid)
            if q['domainId']!=d['id'] or q['problemId']!=pid:raise ValueError('补记与方案不一致')
        duration=number(c.get('durationMs'))
        if duration<=0 or duration>86400000:raise ValueError('补记时长须在 0—24 小时内')
        a['sessions'].append({'id':str(uuid.uuid4()),'domainId':d['id'],'problemId':pid,'title':text(c.get('title',''),300),'date':day(c['date']),
                              'segments':[],'durationMs':duration,'manual':True,'deleted':False,'note':text(c.get('note','')),'endedAt':now})
        if qid:a['sessions'][-1]['planId']=qid
    else:raise ValueError('未知推进操作')


def command(repo,space,c,clock=None,*,server_timer=False):
    from domain import validate
    now=int((time.time() if clock is None else clock)*1000)
    if not isinstance(c,dict):raise ValueError('推进请求无效')
    op=c.get('op');request=c.get('commandId')
    if op not in BACKGROUND_OPS+('init',):ident(request)
    changed=False
    with repo.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        revision,body=db.execute('SELECT revision,body FROM spaces WHERE name=?',(space,)).fetchone()
        state=json.loads(body);a=state.setdefault('advancement',empty(state));before=json.dumps(state,ensure_ascii=False,sort_keys=True)
        initialized='advancement' not in json.loads(body)
        was_running=bool(a.get('active') and a['active']['status']=='running')
        reconcile(a,now)
        synchronize(state)
        if request not in a['commands']:
            mutate(state,c,now)
            if server_timer and op in ('start','resume','switch') and a.get('active'):
                a['active']['clockMode']='server'
            if request and op not in BACKGROUND_OPS:a['commands']=(a['commands']+[request])[-2000:]
        synchronize(state)
        validate(state)
        if initialized or json.dumps(state,ensure_ascii=False,sort_keys=True)!=before:
            # Heartbeats are durable, but should not evict useful user-change snapshots.
            if op not in BACKGROUND_OPS:
                db.execute('INSERT INTO snapshots(space,revision,body) VALUES (?,?,?)',(space,revision,body))
                db.execute('DELETE FROM snapshots WHERE space=? AND id NOT IN (SELECT id FROM snapshots WHERE space=? ORDER BY id DESC LIMIT 100)',(space,space))
            revision+=1;changed=True
            db.execute('UPDATE spaces SET revision=?,body=? WHERE name=?',(revision,json.dumps(state,ensure_ascii=False),space))
    stopped=was_running and a.get('active') and a['active']['status']=='paused'
    if changed and repo.on_saved and (stopped or op not in BACKGROUND_OPS or now-getattr(repo,'_advance_backup_at',0)>=300000):
        repo._advance_backup_at=now
        repo.on_saved()
    return {'state':state,'revision':revision}
