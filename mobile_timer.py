"""Import a finished phone timer only inside the existing approval transaction."""
import datetime as dt
from advancement_service import domain,issue,plan,add_update


def import_timer(state,p,id,stamp):
    a=state.get('advancement')
    if a is None:raise ValueError('个人推进台尚未启用')
    d=domain(a,p['domainId']);pid=p.get('problemId');qid=p.get('planId')
    if pid and issue(a,pid)['domainId']!=d['id']:raise ValueError('问题与计时领域不一致')
    if qid:
        q=plan(a,qid)
        if q['domainId']!=d['id'] or q['problemId']!=pid:raise ValueError('方案与计时问题不一致')
    if any(r['id']==id for r in a['sessions']):raise ValueError('这条计时已存在，请更新收件箱状态')
    adjusted='adjustedDurationMs' in p
    segments=[] if adjusted else [dict(row) for row in p['segments']]
    if not adjusted:
        existing=[span for r in a['sessions'] if not r['deleted'] and not r['manual'] for span in r['segments']]
        active=a.get('active')
        if active:
            existing+=active['segments']
            if active['status']=='running':
                existing.append({'start':active['segmentStart'],'end':max(active['lastSeen'],dt.datetime.now(dt.timezone.utc).timestamp()*1000)})
        if any(x['start']<y['end'] and y['start']<x['end'] for x in segments for y in existing):raise ValueError('这段手机计时与电脑已有计时重叠，请检查记录，或修正用时后再确认')
    row={'id':id,'domainId':d['id'],'problemId':pid,'title':p.get('title',''),
         'date':p['date'],'segments':segments,'durationMs':p.get('adjustedDurationMs',p['durationMs']),
         'manual':adjusted,'deleted':False,'note':p.get('note',''),'endedAt':p['segments'][-1]['end'],'source':'mobile'}
    if qid:row['planId']=qid
    if adjusted:row['original']={'segments':p['segments'],'durationMs':p['durationMs'],'manual':False}
    a['sessions'].append(row)
    if row['note'].strip():add_update(state,{'domainId':d['id'],'problemId':pid,'planId':qid,'date':p['date'],'body':row['note']},id+'-progress',stamp)
