"""Daily observations v1. One dated record; absent values are never zero-filled."""
import copy,csv,datetime as dt,io,json,math,re,uuid
DEFAULTS=[
 {'id':'sleepMinutes','name':'睡眠时长','kind':'duration','unit':'分钟','min':0,'max':1440,'archived':False},
 {'id':'sleepQuality','name':'睡眠质量','kind':'score','unit':'分','min':0,'max':10,'archived':False},
 {'id':'mood','name':'情绪评分','kind':'score','unit':'分','min':0,'max':10,'archived':False},
 {'id':'learning','name':'学习评分','kind':'score','unit':'分','min':0,'max':10,'archived':False}]
def today():return dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date().isoformat()
def ident(v):
 if not isinstance(v,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',v):raise ValueError('指标标识无效')
 return v
def day(v):
 if not isinstance(v,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',v) or not '1901-01-01'<=v<='2099-12-31':raise ValueError('指标日期无效')
 dt.date.fromisoformat(v);return v
def number(v):
 if type(v) not in (int,float) or not math.isfinite(v) or abs(v)>1e9:raise ValueError('指标数值无效')
 return v
def definitions(rows):
 if not isinstance(rows,list) or not 1<=len(rows)<=100:raise ValueError('指标设置无效')
 seen=set()
 for d in rows:
  if not isinstance(d,dict):raise ValueError('指标设置无效')
  id=ident(d.get('id'))
  if id in seen:raise ValueError('指标标识重复')
  seen.add(id)
  if not isinstance(d.get('name'),str) or not 1<=len(d['name'].strip())<=60 or not isinstance(d.get('unit'),str) or len(d['unit'])>20:raise ValueError('请填写有效指标名称及单位')
  if d.get('kind') not in ('duration','score','number') or type(d.get('archived')) is not bool:raise ValueError('指标类型无效')
  if number(d.get('min'))>number(d.get('max')):raise ValueError('指标数值范围无效')
  if d['kind']=='duration' and (d['min']!=0 or d['max']!=1440 or d['unit']!='分钟'):raise ValueError('睡眠时长以分钟保存')
  if d['kind']=='score' and (d['min']!=0 or d['max']!=10):raise ValueError('评分范围为 0—10')
 return rows
def values(v,defs,allow_clear=False):
 if not isinstance(v,dict) or len(v)>100:raise ValueError('指标数值格式无效')
 by={d['id']:d for d in defs}
 for id,n in v.items():
  ident(id)
  if id not in by:raise ValueError('指标已变化，请更新选项')
  if n is None and allow_clear:continue
  number(n);d=by[id]
  if not d['min']<=n<=d['max'] or d['kind']=='duration' and type(n) is not int:raise ValueError(d['name']+'超出范围或精度不正确')
 return v
def validate_metrics(state):
 m=state.get('dailyMetrics')
 if m is None:return
 if not isinstance(m,dict) or type(m.get('version')) is not int or m['version']!=1:raise ValueError('每日指标版本无效')
 definitions(m.get('definitions'));rows=m.get('records')
 if not isinstance(rows,list) or len(rows)>20000:raise ValueError('指标记录过多或格式无效')
 ids=set();dates=set()
 for r in rows:
  if not isinstance(r,dict):raise ValueError('每日指标记录无效')
  id=ident(r.get('id'));date=day(r.get('date'))
  if id in ids or date in dates:raise ValueError('每天只能有一份指标记录')
  ids.add(id);dates.add(date);values(r.get('values'),m['definitions'])
  if type(r.get('deleted')) is not bool or not isinstance(r.get('note'),str) or len(r['note'])>10000:raise ValueError('指标备注或状态无效')
  for key in ('createdAt','updatedAt'):
   if not isinstance(r.get(key),str):raise ValueError('指标保存时间无效')
   dt.datetime.fromisoformat(r[key].replace('Z','+00:00'))
def ensure(state):
 if 'dailyMetrics' in state:return state['dailyMetrics']
 state['dailyMetrics']={'version':1,'definitions':copy.deepcopy(DEFAULTS),'records':[]}
 root=next((f for f in state['folders'] if f['name']=='档案库'),None)
 if root is None:
  root={'id':'metrics-archive-root','name':'档案库','parent':None,'fields':[],'icon':'archive'};state['folders'].append(root)
 f=next((f for f in state['folders'] if f.get('module')=='metrics'),None)
 if f is None:
  f={'id':'daily-metrics-space','name':'每日指标','parent':root['id'],'fields':[],'icon':'activity','module':'metrics'};state['folders'].append(f)
 if f['id'] not in state['pins']:state['pins'].append(f['id'])
 if not any(p['id']=='metrics' for p in state['layout']):state['layout'].append({'id':'metrics','size':'half','visible':True})
 return state['dailyMetrics']
def save_day(state,p,stamp,*,mobile=False):
 m=ensure(state);date=day(p.get('date'))
 if date>today():raise ValueError('不能提前填写未来的每日指标')
 v=values(p.get('values'),m['definitions'],allow_clear=not mobile)
 r=next((r for r in m['records'] if r['date']==date),None)
 if not mobile and p.get('expected')!=(r or {}).get('updatedAt'):raise ValueError('这天的指标已在另一处更新，请重新打开后修改；原稿仍保留')
 old={} if not r or r['deleted'] else r['values']
 if mobile and p.get('replaceExisting',False) is not True and (any(id in old and old[id]!=n for id,n in v.items()) or r and not r['deleted'] and r['note'].strip() and p.get('note','').strip() and p['note']!=r['note']):raise ValueError('当天同项已有不同数值。请检查后勾选“更新当天同项已有值”，再确认入库')
 merged={**old,**v};merged={k:n for k,n in merged.items() if n is not None}
 note=p.get('note',r['note'] if r and not r['deleted'] else '')
 if not isinstance(note,str) or len(note)>10000:raise ValueError('备注过长')
 if not merged and not note.strip():raise ValueError('至少记录一项指标或备注')
 if not r:
  r={'id':str(uuid.uuid4()),'date':date,'createdAt':stamp};m['records'].append(r)
 r.update(values=merged,note=note,deleted=False,updatedAt=stamp)
 return r['id']
def command(repo,space,p):
 from domain import validate
 stamp=dt.datetime.now(dt.timezone.utc).isoformat()
 with repo.connect() as db:
  db.execute('BEGIN IMMEDIATE');revision,body=db.execute('SELECT revision,body FROM spaces WHERE name=?',(space,)).fetchone();s=json.loads(body);m=ensure(s)
  op=p.get('op')
  if op=='save':save_day(s,p,stamp)
  elif op=='delete':
   r=next((r for r in m['records'] if r['id']==p.get('id')),None)
   if not r or p.get('expected')!=r['updatedAt']:raise ValueError('记录已变化，请重新打开')
   if type(p.get('deleted')) is not bool:raise ValueError('记录状态无效')
   r.update(deleted=p['deleted'],updatedAt=stamp)
  elif op=='definition-add':
   if not isinstance(p.get('name'),str) or not isinstance(p.get('unit'),str):raise ValueError('指标名称和单位无效')
   d={'id':ident(p.get('id')),'name':p.get('name','').strip(),'unit':p.get('unit','').strip(),'kind':p.get('kind'),'min':0,'max':10 if p.get('kind')=='score' else 1e9,'archived':False}
   if d['kind'] not in ('score','number'):raise ValueError('请选择评分或数值')
   if any(x['id']==d['id'] or x['name']==d['name'] for x in m['definitions']):raise ValueError('同名指标已存在')
   m['definitions'].append(d)
  elif op=='definition-toggle':
   d=next((d for d in m['definitions'] if d['id']==p.get('id')),None)
   if d is None or type(p.get('archived')) is not bool:raise ValueError('指标设置无效')
   d['archived']=p['archived']
  elif op!='init':raise ValueError('未知指标操作')
  validate(s);new=json.dumps(s,ensure_ascii=False)
  changed=json.loads(body)!=s
  if changed:
   db.execute('INSERT INTO snapshots(space,revision,body) VALUES (?,?,?)',(space,revision,body));db.execute('DELETE FROM snapshots WHERE space=? AND id NOT IN (SELECT id FROM snapshots WHERE space=? ORDER BY id DESC LIMIT 100)',(space,space));revision+=1
   db.execute('UPDATE spaces SET revision=?,body=? WHERE name=?',(revision,new,space))
 if changed and repo.on_saved:repo.on_saved()
 return {'state':s,'revision':revision}
def export_csv(state):
 m=state.get('dailyMetrics',{'definitions':[],'records':[]});out=io.StringIO();w=csv.writer(out)
 def safe(v):return "'"+v if v and v[0] in '=+-@\t\r' else v
 w.writerow(['日期']+[safe(d['name']+'（'+d['unit']+'）') for d in m['definitions']]+['备注'])
 for r in sorted(m['records'],key=lambda r:r['date']):
  if not r['deleted']:w.writerow([r['date']]+[r['values'].get(d['id'],'') for d in m['definitions']]+[safe(r['note'])])
 return out.getvalue()
