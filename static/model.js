import {taskRequired} from './task-model.js';
import {monthlyRoot,reportFor} from './monthly-model.js';
import {scheduled,metric,chronicleRule,chronicleComplete} from './tracking-model.js';
// Pure domain selectors. Date calculations use calendar dates, never UTC slicing.
export function today(now=new Date()){const parts=new Intl.DateTimeFormat('en-US',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(now);const part=type=>parts.find(p=>p.type===type).value;return `${part('year')}-${part('month')}-${part('day')}`;}
export function dayOfWeek(date){return new Date(date+'T12:00:00+08:00').getUTCDay();}
export function daysInMonth(date){const [y,m]=date.split('-').map(Number);return new Date(Date.UTC(y,m,0)).getUTCDate();}
export function due(rule,date){if(!rule.enabled)return false;if(rule.frequency==='daily')return true;if(rule.frequency==='weekly')return rule.days.includes(dayOfWeek(date));return +date.slice(8)===Math.min(rule.monthDay,daysInMonth(date));}
export function habitDue(h,date){return scheduled(h,date);}
export function period(rule,date){return rule.frequency==='monthly'?date.slice(0,7):date;}
export function recordFor(s,r,date){if(r.frequency==='monthly'&&monthlyRoot(s,r.folder))return reportFor(s,date.slice(0,7));return s.notes.find(n=>!n.trashed&&n.ruleId===r.id&&n.period===period(r,date));}
export function progress(s,date){const tasks=s.tasks.filter(t=>taskRequired(t,date));const habits=s.habits.filter(h=>habitDue(h,date));const rules=s.rules.filter(r=>due(r,date));const done=tasks.filter(t=>t.done).length+habits.filter(h=>metric(h,date).done).length+rules.filter(r=>chronicleRule(s,r)?chronicleComplete(s,date):recordFor(s,r,date)?.status==='done').length;const total=tasks.length+habits.length+rules.length;return {tasks,habits,rules,done,total,percent:total?Math.round(done/total*100):0};}
export function descendants(s,id){const ids=new Set([id]);let change=true;while(change){change=false;for(const f of s.folders)if(ids.has(f.parent)&&!ids.has(f.id)){ids.add(f.id);change=true;}}return ids;}
export function folderPath(s,id){let path=[];let seen=new Set();while(id&&!seen.has(id)){seen.add(id);let f=s.folders.find(x=>x.id===id);if(!f)break;path.unshift(f);id=f.parent;}return path;}
export function fieldsFor(s,id){return folderPath(s,id).flatMap(f=>f.fields||[]);}
export function scopeNotes(s,id,includeLegacy=false){const ids=descendants(s,id);return s.notes.filter(n=>!n.trashed&&(includeLegacy||!n.readOnlyArchive)&&ids.has(n.folder)).sort((a,b)=>b.date.localeCompare(a.date)||(Date.parse(b.updatedAt)-Date.parse(a.updatedAt)));}
export function meaningful(body){return body.replace(/^---[\s\S]*?---/,'').split('\n').filter(l=>!/^\s*(#{1,6}\s|[-*]\s*$)/.test(l)).join('').trim().length>0;}
export const panels=[{id:'metrics',name:'每日指标'},{id:'expenses',name:'花销'},{id:'materials',name:'未加工信息原料'},{id:'tasks',name:'今日任务'},{id:'task-backlog',name:'近期待办'},{id:'habits',name:'习惯打卡'},{id:'writing',name:'记录与回顾'},{id:'recent',name:'最近打开的世界'},{id:'weekly',name:'七日回顾',experimental:true}];
export const weekdays=['周日','周一','周二','周三','周四','周五','周六'];
export function scheduleText(r){if(r.frequency==='daily')return '每天';if(r.frequency==='monthly')return r.monthDay===31?'每月最后一天':`每月 ${r.monthDay} 日（短月取月末）`;return r.days.length?r.days.map(d=>weekdays[d]).join('、'):'未选择日期';}
