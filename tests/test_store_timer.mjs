import assert from 'node:assert/strict';
import {rebaseTimerSave} from '../static/advancement-rebase.js';
const initial={tasks:[],advancement:{commands:[],active:{id:'timer',clockMode:'server',status:'running',owner:'a',lastSeen:10,segments:[]}}};
const next=structuredClone(initial);next.tasks.push({id:'new',title:'保留输入'});
const pulse=structuredClone(initial);pulse.advancement.active.lastSeen=20;
assert.equal(rebaseTimerSave(initial,next,pulse).advancement.active.lastSeen,20);
assert.equal(rebaseTimerSave(initial,next,pulse).tasks[0].id,'new');
for(const edit of [s=>s.tasks.push({id:'other'}),s=>s.advancement.active.status='paused',s=>s.advancement.active.owner='b',s=>s.advancement.commands.push('user-command'),s=>s.advancement.active.lastSeen=9]){
 const other=structuredClone(pulse);edit(other);assert.equal(rebaseTimerSave(initial,next,other),null);
}
const timerEdit=structuredClone(next);timerEdit.advancement.active.status='paused';assert.equal(rebaseTimerSave(initial,timerEdit,pulse),null);
globalThis.sessionStorage={getItem:()=>null,setItem:()=>{}};
const response=(state,revision,status=200)=>({ok:status===200,status,json:async()=>status===200?{state:structuredClone(state),revision}:{error:'concurrent edit'}});
globalThis.fetch=async()=>response(initial,1);
const store=await import('../static/store.js');await store.load();
let posts=0,calls=0;
globalThis.fetch=async(url,options)=>{
 if(options.method==='GET')return response(pulse,2);
 const b=JSON.parse(options.body);posts++;
 if(posts===1)return response(null,0,409);
 assert.equal(b.revision,2);assert.equal(b.state.advancement.active.lastSeen,20);assert.equal(b.state.tasks[0].title,'保留输入');return response(b.state,3);
};
await store.change(s=>{calls++;s.tasks.push({id:'new',title:'保留输入'});});
assert.equal(calls,1);assert.equal(posts,2);assert.equal(store.revision,3);assert.equal(store.busy,false);
const independent=structuredClone(store.state);independent.tasks.push({id:'other'});
globalThis.fetch=async(url,options)=>options.method==='GET'?response(independent,4):response(null,0,409);
await assert.rejects(()=>store.change(s=>s.tasks.push({id:'pending'})),/concurrent edit/);
assert.equal(store.revision,3);assert.equal(store.busy,false);
console.log('Timer-only save retry preserves drafts and latest checkpoints, runs edits once, and refuses competing user edits, pause, ownership changes and rollback passed');
