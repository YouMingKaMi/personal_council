import assert from 'node:assert/strict';
import {beginTimer,checkpoint,transition,elapsed,timerSubmission,timeClock,dayAt} from '../mobile/timer-model.js';
import {fields,summary} from '../static/capture-form.js';
import {total,interval} from '../static/advancement-model.js';

const start=Date.parse('2026-10-26T23:55:00+08:00'),minute=60000;
let t=beginTimer({domainId:'fit',problemId:'p',planId:'q',title:'跑步',names:{domain:'健身'}},start,'stable-phone-id');
// No background tick is needed: reopening after a locked-screen interval uses timestamps.
t=JSON.parse(JSON.stringify(t));assert.equal(elapsed(t,start+45*minute),45*minute);
t=transition(t,'pause',start+5*minute);
assert.equal(elapsed(t,start+35*minute),5*minute);
t=transition(JSON.parse(JSON.stringify(t)),'resume',start+10*minute);
t=transition(t,'finish',start+15*minute);t.note='原话\n第二行';
assert.equal(elapsed(t),10*minute);assert.equal(t.segments.length,2);
const submission=timerSubmission(t,start+16*minute);
assert.equal(submission.id,'stable-phone-id');assert.equal(submission.kind,'focus');
assert.equal(submission.payload.date,'2026-10-26');assert.equal(submission.payload.durationMs,10*minute);
assert.equal(submission.payload.note,'原话\n第二行');assert.equal(submission.payload.planId,'q');
t.segments[0].end+=500;assert.equal(submission.payload.segments[0].end,start+5*minute);
assert.equal(transition(t,'cancel',start+20*minute),null);
const state={advancement:{sessions:[{...submission.payload,id:'r',manual:false,deleted:false}],active:null}};
assert.equal(total(state,{start:'2026-10-26',end:'2026-10-26'}),5*minute);
assert.equal(total(state,{start:'2026-10-27',end:'2026-10-27'}),5*minute);
assert.equal(interval(dayAt(start))[0],Date.parse('2026-10-26T00:00:00+08:00'));
assert.equal(timeClock(3661000),'01:01:01');

let back=beginTimer({domainId:'fit'},start,'clock-back');
back=checkpoint(back,start+minute);back=checkpoint(back,start-60000);
assert.equal(back.status,'paused');assert.equal(back.clockChanged,true);assert.equal(elapsed(back),minute);
assert.throws(()=>transition(back,'resume',start-1000));
back=transition(back,'resume',start+2*minute);back=transition(back,'finish',start+3*minute);
assert.equal(elapsed(back),2*minute);
let jump=beginTimer({domainId:'fit'},start,'clock-forward');jump=checkpoint(jump,start+minute);jump=checkpoint(jump,start+31*86400000);
assert.equal(jump.status,'paused');assert.equal(elapsed(jump),minute);
assert.throws(()=>timerSubmission(beginTimer({domainId:'fit'},start,'running')));

const config={domains:[{id:'fit',name:'健身'}],problems:[{id:'p',domainId:'fit',title:'训练'}],plans:[{id:'q',domainId:'fit',problemId:'p',title:'方案'}]};
const review=fields('focus',submission.payload,config);
assert.ok(review.includes('原始时段'));assert.ok(review.includes('name="focusSegments"'));
assert.ok(summary(submission,config).includes('10m'));assert.ok(summary(submission,config).includes('方案：方案'));
const expired=fields('focus',{...submission.payload,note:'<script>文本</script>'},{domains:[],problems:[],plans:[]});
assert.ok(expired.includes('value="fit" selected'));assert.ok(expired.includes('value="q" selected'));
assert.ok(expired.includes('&lt;script&gt;'));assert.ok(!expired.includes('<script>'));
console.log('Phone timer: lock-screen/reload elapsed, pause exclusion, midnight totals, stable submission, clock changes, review references and escaping passed');
