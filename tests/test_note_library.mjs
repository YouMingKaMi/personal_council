import assert from 'node:assert/strict';
import {recentSpaceNotes,noteLibraryRows,noteReadingHTML,noteOutlineHTML,noteSpaceContext} from '../static/note-library.js';
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

const body='---\ntags: [资料]\n---\n# 第一节\n## 重复标题\n```md\n# 代码不是目录\n```\n## 重复标题\n### <script>alert(1)</script> & **强调**\n';
const reading=noteReadingHTML(body),outline=noteOutlineHTML(body);
assert.equal((reading.match(/id="note-section-/g)||[]).length,4);
assert.ok(reading.includes('id="note-section-2"'));
assert.equal((outline.match(/data-action="note-jump"/g)||[]).length,4);
assert.ok(!outline.includes('代码不是目录'));
assert.ok(!outline.includes('<script>'));
assert.ok(outline.includes('&lt;script&gt;'));
assert.ok(outline.includes('data-id="note-section-3"'));
assert.ok(!outline.includes('<strong>')); // Navigation labels remain plain text.
assert.ok(noteOutlineHTML('只是正文').includes('暂无标题'));
assert.deepEqual(noteSpaceContext(state,'child').path.map(f=>f.id),['root','child']);
assert.deepEqual(noteSpaceContext(state,'root').nearby.map(f=>f.id),['child']);
assert.deepEqual(noteSpaceContext(state,'missing'),{path:[],nearby:[]});
const siblings={...state,folders:[...state.folders,{id:'peer',parent:'root'}]};
assert.deepEqual(noteSpaceContext(siblings,'child').nearby.map(f=>f.id),['peer']);
assert.equal(JSON.stringify(state),before);
console.log('Note workspace: stable repeated heading anchors, escaped outline, renderer parity and related folder navigation passed.');
