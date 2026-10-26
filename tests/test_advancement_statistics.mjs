import assert from 'node:assert/strict';
import {monthSummary,monthComparison,duration,shiftMonth,validMonth} from '../static/advancement-statistics.js';
import {statisticsView} from '../static/advancement-statistics-view.js';
import {interval,total} from '../static/advancement-model.js';

const ms=s=>Date.parse(s+'+08:00'),minute=60000;
const manual=(id,domainId,date,n,more={})=>({id,domainId,date,durationMs:n*minute,segments:[],manual:true,deleted:false,...more});
const state={advancement:{domains:[{id:'ai',name:'AI'},{id:'fit',name:'健身',archived:true}],issues:[{id:'p',title:'问题'}],plans:[{id:'q',title:'方案'}],updates:[],sessions:[
 {id:'cross',domainId:'ai',problemId:'p',planId:'q',date:'2026-09-30',manual:false,deleted:false,segments:[{start:ms('2026-09-30T23:30:00'),end:ms('2026-10-01T00:30:00')},{start:ms('2026-10-01T01:00:00'),end:ms('2026-10-01T01:15:00')}],durationMs:75*minute},
 manual('m','fit','2026-10-01',20),manual('zero','fit','2026-10-02',0),manual('delete','ai','2026-10-01',100,{deleted:true,cancelled:true}),
 manual('year','ai','2025-12-31',10),manual('jan','fit','2026-01-01',15)
],active:null}};
const options={asOf:'2026-10-10',now:ms('2026-10-10T12:00:00')};
const oct=monthSummary(state,'2026-10',options);
assert.equal(oct.total,65*minute);
assert.equal(oct.average,6.5*minute);
assert.equal(oct.elapsedDays,10);
assert.equal(oct.recordedDays,2);
assert.equal(oct.peak.date,'2026-10-01');
assert.equal(oct.days[0].records.find(r=>r.id==='cross').dayMs,45*minute);
assert.equal(oct.domains.find(d=>d.id==='ai').ms,45*minute);
assert.equal(oct.domains.find(d=>d.id==='fit').ms,20*minute);
assert.equal(oct.days[1].recorded,true);assert.equal(oct.days[1].ms,0);
assert.equal(oct.days[2].recorded,false);assert.equal(oct.days[20].elapsed,false);
assert.equal(monthSummary(state,'2026-09',options).total,30*minute);
assert.equal(monthSummary(state,'2026-10',{...options,domainId:'fit'}).total,20*minute);
assert.equal(oct.days.reduce((n,d)=>n+d.ms,0),oct.domains.reduce((n,d)=>n+d.ms,0));
assert.equal(oct.total,total(state,{start:'2026-10-01',end:'2026-10-10',now:options.now}));
const comparisons=monthComparison(state,'2026-01',{...options,count:2});
assert.deepEqual(comparisons.map(m=>m.month),['2025-12','2026-01']);
assert.deepEqual(comparisons.map(m=>m.total/minute),[10,15]);
assert.equal(monthSummary(state,'2026-11',options).elapsedDays,0);
assert.equal(monthSummary(state,'2024-02',options).elapsedDays,29);
assert.equal(shiftMonth('2026-01',-1),'2025-12');assert.equal(shiftMonth('2026-12',1),'2027-01');
assert.equal(shiftMonth('0001-01',-1),'0001-01');assert.equal(shiftMonth('9999-12',1),'9999-12');
assert.equal(validMonth('2026-13'),false);assert.equal(validMonth('0000-01'),false);
assert.throws(()=>monthSummary(state,'invalid',options));
assert.equal(duration(3000),'3s');assert.equal(duration(1),'<1s');assert.equal(duration(0),'0m');assert.equal(duration(65*minute),'1h 05m');
// Restoration includes the original amount once; no plan/parent duplication.
state.advancement.sessions.find(r=>r.id==='delete').deleted=false;
assert.equal(monthSummary(state,'2026-10',options).total,165*minute);
state.advancement.sessions.find(r=>r.id==='delete').deleted=true;

state.advancement.active={id:'active',domainId:'ai',date:'2026-10-09',segments:[{start:ms('2026-10-09T23:50:00'),end:ms('2026-10-09T23:55:00')}],status:'running',segmentStart:ms('2026-10-09T23:59:30'),lastSeen:ms('2026-10-10T00:00:00')};
const live=monthSummary(state,'2026-10',options);
assert.equal(live.days[8].ms,5.5*minute);assert.equal(live.days[9].ms,minute);
assert.equal(live.total,71.5*minute);
assert.equal(live.days[9].records[0].live,true);
state.advancement.active.status='paused';
assert.equal(monthSummary(state,'2026-10',options).total,70*minute);
state.advancement.active=null;
// UI has independent month/domain filters, escaped user text, and calendar/details.
state.advancement.domains[0].name='<img onerror="bad">';
const html=statisticsView(state,{month:'2026-10',day:'2026-10-01'},options.now);
assert.ok(html.includes('id="advance-stats-domain"'));
assert.ok(html.includes('id="advance-stats-month"'));
assert.ok(html.includes('2026-10-01 · 明细'));
assert.ok(html.includes('已收起'));
assert.ok(html.includes('&lt;img'));assert.ok(!html.includes('<img onerror'));
assert.ok(!html.includes('NaN'));
assert.equal(interval('2026-10-01')[0],Date.parse('2026-09-30T16:00:00Z'));
console.log('Time statistics: daily/monthly/field totals, midnight, manual zero, active cap, history, restoration, leap year, escaping passed');
