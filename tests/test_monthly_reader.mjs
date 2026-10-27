import assert from 'node:assert/strict';
import {createMonthly} from '../static/monthly-feature.js';
const s={folders:[{id:'month',name:'月报',module:'monthly'}],notes:[{id:'report',folder:'month',title:'一个月的回顾',body:'## 保留原文\n这段文章应直接阅读',status:'done',date:'2024-02-01',period:'2024-02',tags:[]}],rules:[],templates:[]};
const before=structuredClone(s);let render=0,opened=null;
const f=createMonthly({state:()=>s,folder:()=>s.folders[0],heading:()=>'',manage:()=>'',render(){render++;},openNote(id,write){opened={id,write};}});
f.restore({year:2024,pickerYear:2024,chosen:'2024-02'});let html=f.page();assert.match(html,/monthly-reading-layout/);assert.match(html,/这段文章应直接阅读/);assert.match(html,/data-action="monthly-select"/);assert.equal(s.notes.length,1);
await f.action('monthly-select',{dataset:{month:'2024-03'}});html=f.page();assert.match(html,/这个月还没有月报/);assert.equal(s.notes.length,1); // Browsing an empty month must not create a report.
await f.action('monthly-select',{dataset:{month:'2024-02'}});await f.action('monthly-edit',{dataset:{id:'report'}});assert.deepEqual(opened,{id:'report',write:true});
await f.action('monthly-year',{dataset:{year:'2023'}});assert.doesNotThrow(()=>f.page());assert.deepEqual(s,before);assert.equal(render,3);
console.log('Monthly reader: existing originals, empty months without creation, editing, empty years and old navigation snapshots passed');
