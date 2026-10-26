export const states={open:'待推进',active:'推进中',resolved:'已解决',parked:'暂放'};
export const data=s=>s.advancement||{domains:[],issues:[],updates:[],sessions:[],active:null};
export const domains=s=>data(s).domains.filter(d=>!d.archived);
export const issues=(s,d)=>data(s).issues.filter(p=>p.domainId===d&&!p.deleted);
export const format=ms=>{const m=Math.floor(Math.max(0,ms)/60000),h=Math.floor(m/60);return h?`${h}h${String(m%60).padStart(2,'0')}m`:`${m}m`;};
export const clock=ms=>{const t=Math.floor(Math.max(0,ms)/1000);return [Math.floor(t/3600),Math.floor(t/60)%60,t%60].map(x=>String(x).padStart(2,'0')).join(':');};
export function activeMs(r,now=Date.now()){return r?r.segments.reduce((s,r)=>s+r.end-r.start,0)+(r.status==='running'?Math.max(0,Math.min(now,r.lastSeen+60000)-r.segmentStart):0):0;}
export function interval(day){const start=new Date(day+'T00:00:00');const end=new Date(start);end.setDate(end.getDate()+1);return [start.getTime(),end.getTime()];}
export function total(s,{start,end,domainId,problemId,now=Date.now()}={}){
 const a=data(s),lo=start?interval(start)[0]:-Infinity,hi=end?interval(end)[1]:Infinity;
 let sum=0;
 const selected=r=>(!domainId||r.domainId===domainId)&&(!problemId||r.problemId===problemId);
 const add=rows=>rows.reduce((n,r)=>n+Math.max(0,Math.min(r.end,hi)-Math.max(r.start,lo)),0);
 for(const r of a.sessions.filter(r=>!r.deleted&&selected(r))){
  if(r.manual){if((!start||r.date>=start)&&(!end||r.date<=end))sum+=r.durationMs;}
  else sum+=add(r.segments);
 }
 const r=a.active;
 if(r&&selected(r)){sum+=add(r.segments);if(r.status==='running')sum+=add([{start:r.segmentStart,end:Math.min(now,r.lastSeen+60000)}]);}
 return sum;
}
export function weekStart(day){const d=new Date(day+'T12:00:00');d.setDate(d.getDate()-(d.getDay()+6)%7);return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;}
export function current(s,d){const a=data(s),field=a.domains.find(x=>x.id===d);return a.issues.find(p=>p.id===field?.focusId&&!p.deleted&&p.status!=='resolved'&&p.status!=='parked')||issues(s,d).find(p=>p.status==='active')||issues(s,d).find(p=>p.status==='open');}
