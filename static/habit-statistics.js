import {configAt,metric,monthDates} from './tracking-model.js';
export function monthSeries(h,month,itemId='',today){return monthDates(month).map(date=>{
 const m=metric(h,date),c=m.config,e=m.entry,elapsed=date<=today;
 if(!elapsed)return {date,config:c,entry:e,unit:c?.unit,value:null,state:'future',recorded:false,elapsed};
 if(!c)return {date,state:'not-applicable',recorded:false,value:null,elapsed};
 const base={date,config:c,entry:e,unit:c.unit,value:m.quantityKnown?m.value:null,recorded:m.recorded,elapsed};
 if(itemId){
  if(c.kind!=='checklist'||!c.items.some(i=>i.id===itemId))return {...base,state:'not-applicable',recorded:false,value:null};
  const known=Object.hasOwn(e?.items||{},itemId);return {...base,value:null,recorded:known,assumed:!known,state:known&&e.items[itemId]?'complete':'missed'};
 }
 if(e?.legacy?.status==='rest'||e?.legacy?.status==='deferred')return {...base,state:e.legacy.status};
 if(!m.recorded)return {...base,state:'missed',assumed:true};
 return {...base,state:m.done?'complete':c.kind==='check'?'missed':c.kind==='checklist'?m.value?'partial':'missed':m.value>0?'partial':'missed'};
});}
export function monthSummary(rows,unit){
 const past=rows.filter(r=>r.state!=='future'&&r.state!=='not-applicable'),known=past.filter(r=>r.recorded),numeric=known.filter(r=>r.value!==null&&r.value!==undefined&&(!unit||r.unit===unit)),calendarDays=rows.filter(r=>r.elapsed??r.state!=='future').length,total=numeric.reduce((s,r)=>s+r.value,0);
 return {recorded:known.length,complete:past.filter(r=>r.state==='complete').length,missed:past.filter(r=>r.state!=='complete').length,assumed:past.filter(r=>r.assumed).length,total,numericDays:numeric.length,average:numeric.length?total/numeric.length:null,calendarDays,monthlyAverage:calendarDays?total/calendarDays:null,quantityUnknownDays:past.filter(r=>r.state==='complete'&&r.value===null&&r.config?.kind==='number').length};
}
export function monthItems(h,month){const items=new Map();for(const date of monthDates(month))for(const i of configAt(h,date)?.items||[])items.set(i.id,i);return [...items.values()];}
export function chartValue(row,unit){if(row.unit!==unit||row.state==='future'||row.state==='not-applicable')return null;return row.value!==null&&row.value!==undefined?row.value:row.assumed?0:null;}
