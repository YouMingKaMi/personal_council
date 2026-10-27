import {scopeNotes} from './model.js';
import {esc} from './ui.js';
export function recentSpaceNotes(state,folder,query=''){
 const text=query.trim().toLocaleLowerCase();
 return scopeNotes(state,folder).filter(n=>!text||[n.title,n.body,...n.tags].join(' ').toLocaleLowerCase().includes(text));
}
export function noteLibraryRows(notes,selected){
 return notes.map(n=>`<button class="note-library-row" data-action="open-note" data-id="${esc(n.id)}" aria-pressed="${n.id===selected}" aria-label="阅读笔记：${esc(n.title)}"><span class="note-library-date">${esc(n.date)}${n.status==='draft'?' · 草稿':''}</span><strong>${esc(n.title)}</strong><span class="note-library-preview">${esc(n.body.replace(/^---[\s\S]*?---/,'').replace(/[#*|>`\[\]-]/g,'').replace(/\s+/g,' ').trim().slice(0,100))}</span>${n.tags.length?`<span class="tags">${n.tags.map(t=>`<span class="tag"># ${esc(t)}</span>`).join('')}</span>`:''}</button>`).join('')||'<p class="note-library-empty">没有匹配的笔记。</p>';
}
