import {esc,icon,btn,toast} from './ui.js';
import {today} from './model.js';
import {ideasRoot,ideaNotes,addIdea,editIdea,trashIdea} from './ideas-model.js';

export function createIdeas(ctx){
 let saving=false,composing=false;
 const root=()=>ideasRoot(ctx.state())?.id;
 const key=()=>`council-idea-draft:${ctx.space()}:${root()}`;
 function draft(){try{return localStorage.getItem(key())||'';}catch{return '';}}
 function stash(value){try{value?localStorage.setItem(key(),value):localStorage.removeItem(key());}catch{toast('草稿未能保存在浏览器，请及时保存这条想法',true);}}
 document.addEventListener('compositionstart',e=>{if(e.target.id==='idea-body')composing=true;});
 document.addEventListener('compositionend',e=>{if(e.target.id==='idea-body'){composing=false;stash(e.target.value);}});
 const attr=id=>`data-id="${esc(id)}"`;
 const now=()=>new Date().toISOString();
 function history(){
  const notes=ideaNotes(ctx.state(),root()),days=[...new Set(notes.map(n=>n.date))];
  return days.map(d=>`<section class="ideas-day"><header><h2>${d===today()?'今天 · ':''}${esc(d)}</h2><span>${notes.filter(n=>n.date===d).length} 条</span></header><div>${notes.filter(n=>n.date===d).map(n=>`<article class="idea-row" data-idea-id="${esc(n.id)}"><span class="idea-bullet" aria-hidden="true"></span><div class="idea-text">${esc(n.body)}</div><details class="page-menu"><summary aria-label="想法操作" title="更多操作">${icon('more')}</summary><div class="page-menu-panel">${btn('advance-from-note','转为问题','activity','',attr(n.id))}${btn('idea-edit','编辑','edit','',attr(n.id))}${btn('idea-remove','移入回收站','trash','danger',attr(n.id))}</div></details></article>`).join('')}</div></section>`).join('')||'<div class="ideas-empty">暂无想法</div>';
 }
 function page(){return `<div class="ideas-page"><div class="page-heading ideas-heading"><div><div class="eyebrow">执行部</div><h1>想法暂存</h1></div><div class="page-actions">${btn('idea-trash','回收站','trash','ghost small')}</div></div><form data-form="idea-add" class="ideas-composer"><textarea id="idea-body" name="body" aria-label="记下一个想法" placeholder="想到什么，先记下来…" rows="3" maxlength="100000">${esc(draft())}</textarea><div class="ideas-composer-foot"><small>Enter 保存 · Shift + Enter 换行</small><button type="submit" class="button primary">${icon('plus')}记下</button></div></form><div id="ideas-history" class="ideas-history" aria-live="polite">${history()}</div></div>`;}
 function refresh(){const feed=document.querySelector('#ideas-history');if(feed)feed.innerHTML=history();}
 async function add(form){
  if(saving)return;
  const input=form.elements.body,body=input.value;if(!body.trim())return;
  const folder=root(),space=ctx.space(),draftKey=key(),stamp=new Date(),date=today(stamp),id=ctx.uid(),button=form.querySelector('[type=submit]');
  saving=true;input.readOnly=true;if(button)button.disabled=true;
  try{
   await ctx.commit(s=>addIdea(s,{id,folder,date,body,now:stamp.toISOString()}),'',false);
   // Clear only the submitted draft, even if a different page is now visible.
   try{localStorage.removeItem(draftKey);}catch{toast('想法已保存，但浏览器草稿未能清理',true);}
   if(input.isConnected){input.value='';input.readOnly=false;input.focus();}
   if(ctx.space()===space&&root()===folder)refresh();
  }finally{saving=false;if(input.isConnected)input.readOnly=false;if(button?.isConnected)button.disabled=false;}
 }
 async function submit(form){
  if(form.dataset.form==='idea-add')return add(form);
  if(form.dataset.form==='idea-edit'){
   const body=String(new FormData(form).get('body')||'');
   await ctx.commit(s=>editIdea(s,root(),form.dataset.id,body,now()),'已保存',false);ctx.closeModal();refresh();
  }
 }
 async function action(a,e){
  if(a==='idea-trash'){
   const notes=ideaNotes(ctx.state(),root(),{trash:true});
   ctx.modal('想法回收站',notes.map(n=>`<div class="rule-row"><div><strong>${esc(n.body.slice(0,80))}</strong><small>${esc(n.date)}</small></div>${btn('idea-restore','恢复','undo','small',attr(n.id))}</div>`).join('')||'<p>回收站是空的。</p>');return;
  }
  const id=e.dataset.id,n=ctx.state().notes.find(n=>n.id===id&&n.folder===root());if(!n)return;
  if(a==='idea-edit'){ctx.modal('编辑想法',`<form class="form-stack" data-form="idea-edit" ${attr(id)}><label>想法<textarea name="body" rows="8" maxlength="100000" required>${esc(n.body)}</textarea></label>${ctx.buttons()}</form>`);return;}
  if(a==='idea-remove'||a==='idea-restore'){
   await ctx.commit(s=>trashIdea(s,root(),id,a==='idea-remove',now()),a==='idea-remove'?'已移入回收站':'已恢复',false);
   refresh();if(a==='idea-restore')ctx.closeModal();
  }
 }
 function input(e){if(e.id==='idea-body')stash(e.value);}
 async function keydown(e){
  if(e.target.id!=='idea-body'||e.key!=='Enter'||e.shiftKey||e.isComposing||e.keyCode===229||composing)return;
  e.preventDefault();if(!e.repeat)await add(e.target.closest('form'));
 }
 return {page,action,submit,input,keydown};
}
