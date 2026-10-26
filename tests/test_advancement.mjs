import assert from 'node:assert/strict';
import {total,activeMs,clock,weekStart,interval,timerText,currentPlan,target} from '../static/advancement-model.js';
const [a,b]=interval('2026-10-26');
const s={advancement:{sessions:[{domainId:'ai',segments:[{start:b-1800000,end:b+1800000}],manual:false,deleted:false},{domainId:'ai',date:'2026-10-26',durationMs:600000,segments:[],manual:true,deleted:false}],active:null}};
assert.equal(total(s,{start:'2026-10-26',end:'2026-10-26'}),2400000);
assert.equal(total(s,{start:'2026-10-27',end:'2026-10-27'}),1800000);
assert.equal(total(s,{domainId:'other'}),0);
assert.equal(weekStart('2026-10-25'),'2026-10-19');
assert.equal(clock(3661000),'01:01:01');
assert.equal(activeMs({segments:[],status:'running',segmentStart:a,lastSeen:a+15000},a+10000000),75000);
s.advancement.sessions[0].deleted=true;assert.equal(total(s),600000);
console.log('Advancement totals, midnight allocation, deleted and manual records passed');

assert.deepEqual(timerText({title:'同一个问题'},{title:'同一个问题'}),{subject:'同一个问题',action:''});
assert.deepEqual(timerText({title:' 查清  接口 '},{title:'查清 接口'}),{subject:'查清 接口',action:''});
assert.deepEqual(timerText({title:'先查官方文档'},{title:'接口为什么失败？'}),{subject:'接口为什么失败？',action:'先查官方文档'});
assert.deepEqual(timerText({title:'自由学习'},null),{subject:'自由学习',action:''});
s.advancement.sessions=[{domainId:'ai',date:'2026-10-26',durationMs:3000,segments:[],manual:true,deleted:true,cancelled:true}];
assert.equal(total(s),0);s.advancement.sessions[0].deleted=false;assert.equal(total(s),3000);
console.log('Duplicate timer captions and cancelled/restored totals passed');

const planned={advancement:{domains:[],issues:[{id:'p',focusPlanId:'q'}],plans:[{id:'q',problemId:'p',title:'问 GPT',status:'active',deleted:false}],sessions:[{domainId:'ai',problemId:'p',planId:'q',date:'2026-10-26',durationMs:60000,segments:[],manual:true,deleted:false},{domainId:'ai',problemId:'p',date:'2026-10-26',durationMs:120000,segments:[],manual:true,deleted:false}],active:null}};
assert.equal(currentPlan(planned,'p').id,'q');assert.equal(total(planned,{planId:'q'}),60000);assert.equal(total(planned,{problemId:'p'}),180000);
assert.deepEqual(target(planned,'plan:q'),{problemId:'p',planId:'q'});assert.throws(()=>target(planned,'plan:missing'));
assert.deepEqual(timerText({title:'本次事项'},{title:'问题'},{title:'问 GPT'}),{subject:'问题',action:'问 GPT'});
console.log('Persistent plan selection, totals and session captions passed');
