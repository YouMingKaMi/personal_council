export const TIMER_LIMIT=30*86400000;
export const dayAt=ms=>{const p=new Intl.DateTimeFormat('en-US',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date(ms));return ['year','month','day'].map(k=>p.find(x=>x.type===k).value).join('-');};
export const timeClock=ms=>{const s=Math.floor(Math.max(0,ms)/1000);return [Math.floor(s/3600),Math.floor(s/60)%60,s%60].map(n=>String(n).padStart(2,'0')).join(':');};
export function elapsed(timer,now=Date.now()){
 return timer?timer.segments.reduce((n,s)=>n+s.end-s.start,0)+(timer.status==='running'?Math.max(0,now-timer.segmentStart):0):0;
}
export function beginTimer(value,now,id){
 if(!value.domainId)throw Error('请先选择领域');
 return {...value,id,status:'running',startedAt:now,segmentStart:now,lastSeen:now,segments:[],note:'',clockChanged:false};
}
export function checkpoint(timer,now){
 const t=structuredClone(timer);
 if(t.status!=='running')return t;
 if(now<t.lastSeen||elapsed(t,now)>TIMER_LIMIT){
  if(t.lastSeen>t.segmentStart)t.segments.push({start:t.segmentStart,end:t.lastSeen});
  t.segmentStart=null;t.status='paused';t.clockChanged=true;
 }else t.lastSeen=now;
 return t;
}
export function transition(timer,op,now){
 if(!timer)throw Error('没有正在记录的计时');
 if(op==='cancel')return null;
 const t=checkpoint(timer,now);
 if(!['running','paused'].includes(t.status))throw Error('这次计时已结束');
 if(op==='resume'){
  if(t.status==='running')return t;
  if(now<t.lastSeen)throw Error('设备时间早于上一时刻，请校准时间后继续');
  t.status='running';t.segmentStart=now;t.lastSeen=now;t.clockChanged=false;return t;
 }
 if(!['pause','finish'].includes(op))throw Error('计时操作无效');
 if(t.status==='running'){
  if(now>t.segmentStart)t.segments.push({start:t.segmentStart,end:now});
  t.segmentStart=null;t.lastSeen=now;t.status='paused';
 }
 if(op==='finish'){
  if(!elapsed(t))throw Error('还没有可记录的用时');
  t.status='finished';t.endedAt=t.segments.at(-1).end;
 }
 return t;
}
export function timerSubmission(timer,now=Date.now()){
 if(timer.status!=='finished')throw Error('请先结束计时');
 return {version:1,id:timer.id,kind:'focus',createdAt:new Date(now).toISOString(),payload:{
  date:dayAt(timer.segments[0].start),domainId:timer.domainId,problemId:timer.problemId||null,planId:timer.planId||null,
  ...(timer.activityId?{activityId:timer.activityId}:{}),title:timer.title||'',note:timer.note||'',segments:structuredClone(timer.segments),durationMs:elapsed(timer),
 }};
}
