import {data,interval,activeEnd} from './advancement-model.js';
import {today,daysInMonth} from './model.js';

export const validMonth=value=>/^\d{4}-(0[1-9]|1[0-2])$/.test(value)&&Number(value.slice(0,4))>0;
export function shiftMonth(month,amount){
 const [year,m]=month.split('-').map(Number),index=Math.max(12,Math.min(119999,year*12+m-1+amount));
 return `${String(Math.floor(index/12)).padStart(4,'0')}-${String(index%12+1).padStart(2,'0')}`;
}
export function duration(ms){
 const seconds=Math.floor(Math.max(0,ms)/1000),minutes=Math.floor(seconds/60),hours=Math.floor(minutes/60);
 if(hours)return `${hours}h ${String(minutes%60).padStart(2,'0')}m`;
 if(minutes)return `${minutes}m`;
 return seconds?`${seconds}s`:ms>0?'<1s':'0m';
}
export function timeRows(state,now=Date.now()){
 const a=data(state),rows=a.sessions.filter(r=>!r.deleted).map(r=>({...r,live:false})),r=a.active;
 if(r){
  const segments=[...r.segments];
  if(r.status==='running'&&r.segmentStart!=null){
   const end=activeEnd(r,now);
   if(end>r.segmentStart)segments.push({start:r.segmentStart,end});
  }
  rows.push({...r,segments,manual:false,live:true});
 }
 return rows;
}

// One session contributes once. Automatic records are split at Shanghai midnight;
// manual corrections belong to their declared date, including an explicit zero.
export function monthSummary(state,month,{domainId='',now=Date.now(),asOf=today(new Date(now))}={}){
 if(!validMonth(month))throw Error('请选择有效月份');
 const a=data(state),fields=a.domains||[],end=daysInMonth(month+'-01');
 const days=Array.from({length:end},(_,i)=>({date:`${month}-${String(i+1).padStart(2,'0')}`,ms:0,recorded:false,byDomain:{},records:[]}));
 const rows=timeRows(state,now).filter(r=>!domainId||r.domainId===domainId);
 for(const day of days){
  day.elapsed=day.date<=asOf;
  if(!day.elapsed)continue;
  const [lo,hi]=interval(day.date);
  for(const r of rows){
   const ms=r.manual?(r.date===day.date?r.durationMs:0):r.segments.reduce((sum,s)=>sum+Math.max(0,Math.min(s.end,hi)-Math.max(s.start,lo)),0);
   const explicitZero=!r.live&&r.date===day.date&&(r.manual||r.segments.length===0)&&r.durationMs===0;
   if(ms<=0&&!explicitZero)continue;
   day.recorded=true;day.ms+=ms;day.byDomain[r.domainId]=(day.byDomain[r.domainId]||0)+ms;
   day.records.push({...r,dayMs:ms});
  }
 }
 const elapsedDays=days.filter(d=>d.elapsed).length,total=days.reduce((sum,d)=>sum+d.ms,0);
 const totals=fields.filter(d=>!domainId||d.id===domainId).map(d=>({...d,ms:days.reduce((sum,day)=>sum+(day.byDomain[d.id]||0),0),recorded:days.some(day=>day.records.some(r=>r.domainId===d.id))}));
 const peak=days.filter(d=>d.recorded).reduce((best,d)=>!best||d.ms>best.ms?d:best,null);
 return {month,days,domains:totals,total,elapsedDays,average:elapsedDays?total/elapsedDays:0,recordedDays:days.filter(d=>d.recorded).length,peak};
}
export function monthComparison(state,month,{count=6,...options}={}){
 count=Math.min(12,Math.max(1,count));
 return Array.from({length:count},(_,i)=>monthSummary(state,shiftMonth(month,i-count+1),options));
}
