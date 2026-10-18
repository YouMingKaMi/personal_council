// Versioned habit rules. A later edit never reinterprets earlier entries.
export function configAt(h,date){if(!h.versions)return h;return [...h.versions].filter(v=>v.fromDate<=date).sort((a,b)=>b.fromDate.localeCompare(a.fromDate))[0]||null;}
export function metric(h,date){
 const c=configAt(h,date);if(!c)return {config:null,value:0,total:0,done:false,recorded:false,entry:null,quantityKnown:false};
 const e=h.entries?.[date]||(h.logs?.[date]!==undefined?{value:h.logs[date],...(c.kind==='check'?{checked:h.logs[date]>0}:{})}:null),quantityKnown=(!c.kind||c.kind==='number')&&!!e&&typeof e.value==='number';
 const value=c.kind==='check'?e?.checked?1:0:c.kind==='checklist'?c.items.filter(i=>e?.items?.[i.id]===true).length:quantityKnown?e.value:0;
 const total=c.kind==='check'?1:c.kind==='checklist'&&c.policy==='all'?c.items.length:c.target,recorded=!!e&&e.legacy?.status!=='unknown';
 const done=recorded&&(c.kind==='check'?e.checked===true:e.legacy?.status==='complete'||(!['rest','deferred','incomplete','partial'].includes(e.legacy?.status)&&value>=total));
 return {config:c,entry:e,value,total,done,recorded,quantityKnown};
}
export function toggleCheck(h,date,now){const c=configAt(h,date);if(c?.kind!=='check')throw new Error('这一天不是纯打卡习惯');h.entries[date]={checked:!metric(h,date).done,versionId:c.id,updatedAt:now};}
export function scheduled(h,date){const c=configAt(h,date);return !!c&&c.enabled&&!c.optional&&c.days.includes(new Date(date+'T12:00:00+08:00').getUTCDay());}
export function setNumber(h,date,value,now){const c=configAt(h,date);if(!c||c.kind!=='number')throw new Error('这一天不是数值习惯');if(!Number.isFinite(value)||value<0)throw new Error('请输入不小于零的数值');h.entries[date]={value,versionId:c.id,updatedAt:now};}
export function toggleItem(h,date,item,now){const c=configAt(h,date);if(!c||c.kind!=='checklist'||!c.items.some(i=>i.id===item))throw new Error('这一天没有这个项目');const previous=h.entries[date]?.items||{};h.entries[date]={items:{...previous,[item]:!previous[item]},versionId:c.id,updatedAt:now};}
export function addVersion(h,config){const latest=[...h.versions].sort((a,b)=>b.fromDate.localeCompare(a.fromDate))[0];if(config.fromDate<latest.fromDate)throw new Error('生效日期不能早于最新一版规则');if(Object.keys(h.entries).some(d=>d>=config.fromDate))throw new Error('所选日期及之后已有记录，请选择这些记录之后的生效日期；历史数据不会被改写');h.versions=h.versions.filter(v=>v.fromDate!==config.fromDate);h.versions.push(config);}
export function monthDates(month){const [y,m]=month.split('-').map(Number),count=new Date(Date.UTC(y,m,0)).getUTCDate();return Array.from({length:count},(_,i)=>`${month}-${String(i+1).padStart(2,'0')}`);}
export function eventsOn(s,date){return (s.chronicle?.events||[]).filter(e=>!e.deleted&&e.date===date);}
export function chronicleRule(s,r){return r.id==='chronicle'||s.folders?.some(f=>f.id===r.folder&&f.module==='chronicle');}
export function chronicleComplete(s,date){return !!s.chronicle?.days?.[date]?.complete&&eventsOn(s,date).length>0;}
export function completeDay(s,date,now){if(!eventsOn(s,date).length)throw new Error('先记录一件事，再完成今天');s.chronicle.days[date]={complete:!chronicleComplete(s,date),updatedAt:now};}
export function moveEvent(s,id,direction){const event=s.chronicle.events.find(e=>e.id===id);const list=eventsOn(s,event.date),index=list.findIndex(e=>e.id===id),other=list[index+direction];if(!other)return;const a=s.chronicle.events.indexOf(event),b=s.chronicle.events.indexOf(other);[s.chronicle.events[a],s.chronicle.events[b]]=[s.chronicle.events[b],s.chronicle.events[a]];}

// Completion affects the home list only; history and progress always retain the entry.
export function hiddenOnHome(h,date){const m=metric(h,date);return m.done&&(m.config.kind!=='number'||m.entry?.homeCollapsed===true);}
export function setHomeCollapsed(h,date,hidden){const m=metric(h,date);if(m.config?.kind!=='number'||!m.done||!m.entry)throw new Error('达到最低目标后才可收起数值习惯');m.entry.homeCollapsed=!!hidden;}
