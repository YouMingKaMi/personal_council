import assert from 'node:assert/strict';
import {commonNoteTags,parseTagInput,noteTagOptions,extractNoteTags} from '../static/note-tags.js';
// Manual source labels coexist with content labels and arbitrary custom tags.
assert.deepEqual(parseTagInput('AI生成， 大纲, 自定义/课程,AI生成,, '),['AI生成','大纲','自定义/课程']);
assert.deepEqual(parseTagInput(''),[]);
const selected=['自己写的旧标签','AI生成'];const existing=['旧资料','自己写的旧标签'];
const before=JSON.stringify([selected,existing]);const options=noteTagOptions(selected,existing);
assert.equal(options.filter(t=>t==='AI生成').length,1);
assert.ok(options.includes('旧资料'));assert.equal(JSON.stringify([selected,existing]),before);
assert.ok(commonNoteTags.includes('AI辅助'));
// Suggestions must not infer source from prose or expose code-block hashtags as metadata.
assert.deepEqual(extractNoteTags('这是一份 AI 生成的大纲'),[]);
assert.deepEqual(extractNoteTags('```js\n// #AI生成\n```\n普通正文'),[]);
assert.deepEqual(extractNoteTags('---\ntags: [资料, 大纲]\n---\n正文 #自定义'),['资料','大纲','自定义']);
console.log('Note tags: source labels, custom input, deduplication and no provenance inference passed.');
