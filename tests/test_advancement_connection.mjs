import assert from 'node:assert/strict';
import {timerConnection} from '../static/advancement-connection.js';
import {activeMs,total} from '../static/advancement-model.js';
import {timeRows} from '../static/advancement-statistics.js';
const opened=[];let active=null,space='main',syncs=0;
class Source{constructor(url){this.url=url;this.closed=false;opened.push(this);}close(){this.closed=true;}}
const c=timerConnection({active:()=>active,space:()=>space,owner:'owner-a',sync:()=>syncs++,Source});
c.ensure();assert.equal(opened.length,0);
active={status:'running',clockMode:'server',owner:'owner-a',segmentStart:0,lastSeen:10000,segments:[]};
c.ensure();assert.equal(opened.length,1);assert.ok(opened[0].url.includes('space=main'));
opened[0].onopen();assert.equal(syncs,1);
c.ensure();assert.equal(opened.length,1); // changing app views does not close the stream
space='lab';c.ensure();assert.equal(opened.length,2);assert.ok(opened[0].closed);
active.owner='other';c.ensure();assert.ok(opened[1].closed);assert.equal(opened.length,2);
active.owner='owner-a';c.ensure();assert.equal(opened.length,3);
c.close();assert.ok(opened[2].closed);c.ensure();assert.equal(opened.length,4); // reload/pageshow reconnect
active.status='paused';c.ensure();assert.ok(opened[3].closed);
active.status='running';active.clockMode=undefined;c.ensure();assert.equal(opened.length,4); // legacy timer uses old protocol
active.clockMode='server';
assert.equal(activeMs(active,999999),40000);
const s={advancement:{sessions:[],active}};
assert.equal(total(s,{now:999999}),40000);assert.equal(timeRows(s,999999)[0].segments[0].end,40000);
console.log('Timer connection ownership, navigation/reconnect, space isolation, legacy compatibility and consistent bounded statistics passed');
