import assert from 'node:assert/strict';
import {departmentGroups} from '../static/workspace-model.js';
import {folderDomain,folderProgress} from '../static/advancement-folder-view.js';
const s={advancement:{domains:[{id:'legacy-id',folderId:'child-folder',name:'自动化',archived:false}],issues:[{id:'p',domainId:'legacy-id',title:'<问题>',status:'active',deleted:false,updatedAt:'2026-10-27'}],plans:[{id:'q',domainId:'legacy-id',problemId:'p',title:'方案',status:'active',deleted:false}],updates:[{id:'u',domainId:'legacy-id',problemId:'p',planId:'q',date:'2026-10-27',body:'保留原文\n<script>文本</script>',createdAt:'2026-10-27'}],sessions:[{id:'r',domainId:'legacy-id',manual:true,deleted:false,date:'2026-10-27',durationMs:600000,segments:[]}],active:null}};
assert.equal(folderDomain(s,'child-folder').id,'legacy-id');
assert.equal(folderProgress(s,'unrelated'),'');
const html=folderProgress(s,'child-folder');
assert.ok(html.includes('领域推进'));assert.ok(html.includes('1 个问题 · 1 个方案 · 累计 10m'));
assert.ok(html.includes('data-id="p" data-plan="q"'));assert.ok(html.includes('data-id="legacy-id"'));
assert.ok(html.includes('&lt;script&gt;'));assert.ok(!html.includes('<script>'));
s.advancement.domains[0].archived=true;
const archived=folderProgress(s,'child-folder');assert.ok(archived.includes('已收起'));assert.ok(archived.includes('保留原文'));assert.ok(!archived.includes('data-action="advance-folder-issue"'));
assert.ok(archived.includes('data-action="advance-folder-stats"'));
console.log('Linked folder overview: stable domain identity, problem/plan/progress links, time total, escaping and archived reading passed');

s.folders=[{id:'science',name:'中科院',parent:null},{id:'child-folder',name:'自动化',parent:'science'}];s.notes=[];s.pins=[];
assert.ok(departmentGroups(s).common.some(f=>f.id==='science'));
console.log('A department with linked advancement content remains a common workspace');
