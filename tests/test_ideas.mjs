import assert from 'node:assert/strict';
import {ensureIdeasSpace,ideasRoot,ideaNotes,addIdea,editIdea,trashIdea} from '../static/ideas-model.js';
import {progress} from '../static/model.js';

let s={folders:[{id:'executive',name:'执行部',parent:null,fields:[]},{id:'raw',name:'原料',module:'materials',fields:[]}],notes:[],tasks:[],habits:[],rules:[],pins:[],chronicle:{events:[],days:{}}};
const before=structuredClone(s);let seq=0;
const root=ensureIdeasSpace(s,()=>`id-${++seq}`);
assert.equal(root.parent,'executive');assert.equal(s.folders.length,before.folders.length+1);
assert.equal(ensureIdeasSpace(s,()=>{throw Error('must reuse');}),root);
assert.deepEqual(s.pins,[]);assert.deepEqual(s.rules,[]);
const empty={folders:[],notes:[]};ensureIdeasSpace(empty,()=>`new-${++seq}`);assert.equal(empty.folders.length,2);
const raw='  临时念头\n换行保留\n<script>不执行</script>  ';
addIdea(s,{id:'a',folder:root.id,date:'2026-10-23',body:raw,now:'2026-10-23T01:00:00Z'});
addIdea(s,{id:'b',folder:root.id,date:'2026-10-23',body:'第二个想法',now:'2026-10-23T02:00:00Z'});
addIdea(s,{id:'older',folder:root.id,date:'2026-10-22',body:'之前的想法',now:'2026-10-22T01:00:00Z'});
assert.equal(s.notes[0].body,raw);assert.equal(s.notes[0].ruleId,undefined);
assert.deepEqual(ideaNotes(s,root.id).map(n=>n.id),['a','b','older']);
assert.deepEqual(progress(s,'2026-10-23'),progress(before,'2026-10-23'));
assert.throws(()=>addIdea(s,{id:'a',folder:root.id,date:'2026-10-23',body:'duplicate'}));
assert.throws(()=>addIdea(s,{id:'bad',folder:'raw',date:'2026-10-23',body:'wrong module'}));
assert.throws(()=>addIdea(s,{id:'bad',folder:root.id,date:'2026-02-30',body:'invalid day'}));
assert.throws(()=>editIdea(s,root.id,'a','   ','now'));
editIdea(s,root.id,'a','新想法\n完整原话','2026-10-24T01:00:00Z');
assert.equal(s.notes[0].date,'2026-10-23');assert.equal(s.notes[0].createdAt,'2026-10-23T01:00:00Z');
trashIdea(s,root.id,'a',true,'2026-10-24T02:00:00Z');
assert.deepEqual(ideaNotes(s,root.id,{trash:true}).map(n=>n.id),['a']);
assert.throws(()=>editIdea(s,root.id,'a','hidden','now'));
trashIdea(s,root.id,'a',false,'2026-10-24T03:00:00Z');
assert.equal(ideaNotes(s,root.id)[0].body,'新想法\n完整原话');
assert.throws(()=>trashIdea(s,'raw','a',true,'now'));

// Exercise continuous entry, IME and the asynchronous save boundary.
const listeners=new Map(),drafts=new Map(),feed={innerHTML:''};
globalThis.document={addEventListener:(name,fn)=>listeners.set(name,fn),querySelector:()=>feed};
globalThis.localStorage={getItem:k=>drafts.get(k)||null,setItem:(k,v)=>drafts.set(k,v),removeItem:k=>drafts.delete(k)};
const {createIdeas}=await import('../static/ideas-feature.js');
let space='main',hold=null,rejectSave=false,calls=0,uid=0;
const ctx={state:()=>s,space:()=>space,uid:()=>`input-${++uid}`,render(){throw Error('Capture must not replace the input');},
 commit:async fn=>{calls++;if(hold)await hold;if(rejectSave)throw Error('模拟保存失败');const next=structuredClone(s);fn(next);s=next;},closeModal(){}};
const feature=createIdeas(ctx),button={disabled:false,isConnected:true},input={id:'idea-body',value:'',readOnly:false,isConnected:true,focus(){this.focused=true;},closest:()=>form};
const form={dataset:{form:'idea-add'},elements:{body:input},querySelector:()=>button};
function type(text){input.value=text;feature.input(input);}
function enter(extra={}){let prevented=false;const event={key:'Enter',target:input,preventDefault(){prevented=true;},...extra};return [event,()=>prevented];}
type('中文输入草稿');
for(const extra of [{isComposing:true},{keyCode:229},{shiftKey:true}]){const [e,p]=enter(extra);await feature.keydown(e);assert.equal(p(),false);}
listeners.get('compositionstart')({target:input});await feature.keydown(enter()[0]);assert.equal(calls,0);
listeners.get('compositionend')({target:input});
assert.ok(feature.page().includes('中文输入草稿'));
space='lab';assert.ok(!feature.page().includes('中文输入草稿'));space='main';
let release;hold=new Promise(resolve=>release=resolve);
const startCount=s.notes.length,[event,prevented]=enter(),pending=feature.keydown(event);
assert.equal(prevented(),true);assert.equal(input.readOnly,true);assert.equal(button.disabled,true);
await feature.submit(form);assert.equal(calls,1);release();await pending;hold=null;
assert.equal(s.notes.length,startCount+1);assert.equal(input.value,'');assert.equal(input.readOnly,false);assert.equal(button.disabled,false);assert.equal(input.focused,true);assert.equal(drafts.size,0);
type('失败时不要丢掉我');rejectSave=true;
await assert.rejects(feature.keydown(enter()[0]),/模拟保存失败/);
assert.equal(input.value,'失败时不要丢掉我');assert.equal(input.readOnly,false);assert.equal(button.disabled,false);assert.ok(feature.page().includes('失败时不要丢掉我'));
assert.equal(s.notes.length,startCount+1);rejectSave=false;
await feature.keydown(enter({repeat:true})[0]);assert.equal(s.notes.length,startCount+1);
// User text is never interpreted as HTML.
type('<img src=x onerror=alert(1)>');await feature.submit(form);
assert.ok(feature.page().includes('&lt;img src=x onerror=alert(1)&gt;'));assert.ok(!feature.page().includes('<img src=x'));
assert.equal(ideasRoot(s).id,root.id);
console.log('Ideas: stable executive entry, verbatim notes, date ordering, trash/restore, no progress effects, IME, drafts, duplicate-save guard, failures and safe rendering passed.');
