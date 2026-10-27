import {scopeNotes,folderPath} from './model.js';
import {esc,markdown} from './ui.js';
export function recentSpaceNotes(state,folder,query=''){
 const text=query.trim().toLocaleLowerCase();
 return scopeNotes(state,folder).filter(n=>!text||[n.title,n.body,...n.tags].join(' ').toLocaleLowerCase().includes(text));
}
export function noteLibraryRows(notes,selected){
 return notes.map(n=>`<button class="note-library-row" data-action="open-note" data-id="${esc(n.id)}" aria-pressed="${n.id===selected}" aria-label="阅读笔记：${esc(n.title)}"><span class="note-library-date">${esc(n.date)}${n.status==='draft'?' · 草稿':''}</span><strong>${esc(n.title)}</strong><span class="note-library-preview">${esc(n.body.replace(/^---[\s\S]*?---/,'').replace(/[#*|>`\[\]-]/g,'').replace(/\s+/g,' ').trim().slice(0,100))}</span>${n.tags.length?`<span class="tags">${n.tags.map(t=>`<span class="tag"># ${esc(t)}</span>`).join('')}</span>`:''}</button>`).join('')||'<p class="note-library-empty">没有匹配的笔记。</p>';
}

// Build the outline from the same escaped HTML as the reader, so code blocks,
// front matter and repeated headings cannot point to the wrong passage.
export function noteReadingHTML(body){let index=0;return markdown(body).replace(/<h([2-4])>/g,(_,level)=>`<h${level} id="note-section-${index++}" tabindex="-1">`);}
export function noteOutlineHTML(body){
 const rows=[...noteReadingHTML(body).matchAll(/<h([2-4]) id="(note-section-\d+)" tabindex="-1">([\s\S]*?)<\/h\1>/g)];
 return rows.map(([,level,id,label])=>`<button type="button" data-action="note-jump" data-id="${id}" data-level="${level}" title="跳到这一节">${label.replace(/<[^>]*>/g,'')}</button>`).join('')||'<span class="note-context-empty">暂无标题</span>';
}
export function noteSpaceContext(state,folder){
 const path=folderPath(state,folder),current=path.at(-1);
 if(!current)return {path:[],nearby:[]};
 const children=state.folders.filter(f=>f.parent===folder);
 return {path,nearby:children.length?children:state.folders.filter(f=>f.parent===current.parent&&f.id!==folder)};
}
