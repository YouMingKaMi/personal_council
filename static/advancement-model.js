export const states={open:'待推进',active:'推进中',resolved:'已解决',parked:'暂放'};
export const data=s=>s.advancement||{domains:[],issues:[],updates:[],sessions:[],active:null};
export const planStates={open:'待推进',active:'推进中',done:'已完成',parked:'暂放'};
export const plans=(s,id)=>(data(s).plans||[]).filter(q=>q.problemId===id&&!q.deleted);
export function currentPlan(s,id){const p=data(s).issues.find(p=>p.id===id),qs=plans(s,id).filter(q=>['open','active'].includes(q.status));return qs.find(q=>q.id===p?.focusPlanId)||qs.find(q=>q.status==='active')||qs[0];}
export function target(s,value){if(value?.startsWith('plan:')){const q=(data(s).plans||[]).find(q=>q.id===value.slice(5));if(!q)throw Error('方案已变化，请刷新后重试');return {problemId:q.problemId,planId:q.id};}return {problemId:value||null,planId:null};}
export const domains=s=>data(s).domains.filter(d=>!d.archived);
export const focusDomains=s=>domains(s).filter(d=>(data(s).workbench?.focusDomainIds||[]).includes(d.id));
export function workbenchDomains(s,day,now=Date.now()){
 const a=data(s),focus=new Set(focusDomains(s).map(d=>d.id)),w=a.workbench;
 const ids=new Set([...focus,...(w?.temporaryDate===day?w.temporaryDomainIds:[])]);
 const [lo,hi]=interval(day),overlap=rows=>rows.some(r=>r.end>lo&&r.start<hi);
 for(const r of a.sessions){
  if(!r.deleted&&(r.manual?r.date===day:overlap(r.segments)||r.durationMs===0&&r.date===day))ids.add(r.domainId);
 }
 const r=a.active;
 if(r&&(r.date===day||overlap(r.segments)||r.status==='running'&&activeEnd(r,now)>lo&&r.segmentStart<hi))ids.add(r.domainId);
 return a.domains.filter(d=>ids.has(d.id)&&(!d.archived||total(s,{start:day,end:day,domainId:d.id,now})>0)).map(d=>({...d,temporary:!focus.has(d.id)}));
}
export const issues=(s,d)=>data(s).issues.filter(p=>p.domainId===d&&!p.deleted);
export const format=ms=>{const m=Math.floor(Math.max(0,ms)/60000),h=Math.floor(m/60);return h?`${h}h${String(m%60).padStart(2,'0')}m`:`${m}m`;};
export const clock=ms=>{const t=Math.floor(Math.max(0,ms)/1000);return [Math.floor(t/3600),Math.floor(t/60)%60,t%60].map(x=>String(x).padStart(2,'0')).join(':');};
export const activeEnd=(r,now=Date.now())=>Math.min(now,r.lastSeen+(r.clockMode==='server'?30000:60000));
export function activeMs(r,now=Date.now()){return r?r.segments.reduce((s,r)=>s+r.end-r.start,0)+(r.status==='running'?Math.max(0,activeEnd(r,now)-r.segmentStart):0):0;}
export function interval(day){const start=Date.parse(day+'T00:00:00+08:00');return [start,start+86400000];}
export function total(s,{start,end,domainId,problemId,planId,now=Date.now()}={}){
 const a=data(s),lo=start?interval(start)[0]:-Infinity,hi=end?interval(end)[1]:Infinity;
 let sum=0;
 const selected=r=>(!domainId||r.domainId===domainId)&&(!problemId||r.problemId===problemId)&&(!planId||r.planId===planId);
 const add=rows=>rows.reduce((n,r)=>n+Math.max(0,Math.min(r.end,hi)-Math.max(r.start,lo)),0);
 for(const r of a.sessions.filter(r=>!r.deleted&&selected(r))){
  if(r.manual){if((!start||r.date>=start)&&(!end||r.date<=end))sum+=r.durationMs;}
  else sum+=add(r.segments);
 }
 const r=a.active;
 if(r&&selected(r)){sum+=add(r.segments);if(r.status==='running')sum+=add([{start:r.segmentStart,end:activeEnd(r,now)}]);}
 return sum;
}
export function weekStart(day){const d=new Date(day+'T12:00:00');d.setDate(d.getDate()-(d.getDay()+6)%7);return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;}
export function current(s,d){const a=data(s),field=a.domains.find(x=>x.id===d);return a.issues.find(p=>p.id===field?.focusId&&!p.deleted&&p.status!=='resolved'&&p.status!=='parked')||issues(s,d).find(p=>p.status==='active')||issues(s,d).find(p=>p.status==='open');}

// An activity may fall back to the issue title; display that text only once.
export function timerText(timer,problem,plan){
 const subject=problem?.title?.trim()||timer?.title?.trim()||'自由推进';
 const activity=plan?.title?.trim()||timer?.title?.trim()||'';
 const normal=s=>s.replace(/\s+/g,' ').trim();
 return {subject,action:activity&&normal(activity)!==normal(subject)?activity:''};
}
