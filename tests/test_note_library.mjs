import assert from 'node:assert/strict';
import {recentSpaceNotes,noteLibraryRows} from '../static/note-library.js';
const state={folders:[{id:'root'},{id:'child',parent:'root'},{id:'other'}],notes:[
{id:'old',folder:'root',date:'2026-10-01',title:'旧日志',body:'保留正文',tags:[]},
{id:'new',folder:'child',date:'2026-10-20',title:'<资料>',body:'课程大纲',tags:['AI生成']},
{id:'other',folder:'other',date:'2026-10-22',title:'无关空间',body:'课程',tags:[]},
{id:'trash',folder:'root',date:'2026-10-23',title:'回收站',body:'课程',tags:[],trashed:true},
{id:'archive',folder:'root',date:'2026-10-24',title:'只读原文',body:'课程',tags:[],readOnlyArchive:true},
]};
const before=JSON.stringify(state);
assert.deepEqual(recentSpaceNotes(state,'root').map(n=>n.id),['new','old']);
assert.deepEqual(recentSpaceNotes(state,'root',' AI生成 ').map(n=>n.id),['new']);
assert.deepEqual(recentSpaceNotes(state,'root','保留正文').map(n=>n.id),['old']);
assert.equal(recentSpaceNotes(state,'root','找不到').length,0);
const html=noteLibraryRows(recentSpaceNotes(state,'root'),'new');
assert.ok(html.includes('&lt;资料&gt;'));assert.ok(!html.includes('<资料>'));
assert.ok(html.includes('aria-pressed="true"'));assert.ok(html.includes('# AI生成'));
assert.ok(noteLibraryRows([],null).includes('没有匹配'));
assert.equal(JSON.stringify(state),before);
console.log('Recent notes: scope, chronological order, source tag search, trash/privacy boundaries and escaped rendering passed.');
