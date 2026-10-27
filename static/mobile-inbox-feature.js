import {updateAllocationForm,updateTaskPlanFields,fields,payload,summary,escape as esc,names} from './capture-form.js';
import {api,load} from './store.js';
export function createMobileInbox(ctx){
 let data=null,error='',loading=false;
 async function refresh(){if(loading)return;loading=true;try{data=await api('/api/mobile-inbox');error='';}catch(e){error=e.message;}finally{loading=false;if(ctx.view().page==='inbox')ctx.render();}}
 function page(){
  if(ctx.space()!=='main')return ctx.heading('MOBILE INBOX','手机收件箱','请切换正式空间处理手机记录。');
  if(!data&&!loading&&!error)setTimeout(refresh,0);
  const connection=data?.connection, pending=data?.items.filter(r=>r.status==='pending')||[];
  return ctx.heading('MOBILE INBOX','手机收件箱','检查后确认，直接加入对应记录。', '<button class="button" data-action="inbox-sync">接收新记录</button>')+
   `<p class="help">${esc(error||connection?.error||(connection?.configured?'已连接中转站 · '+(connection.lastSuccess?'最近连接 '+new Date(connection.lastSuccess).toLocaleString():'等待首次连接'):'尚未配置中转站'))}</p>`+
   (connection?.phoneUrl?`<p><a href="${esc(connection.phoneUrl)}" target="_blank" rel="noopener noreferrer">打开手机录入网页 ↗</a></p>`:'')+
   `<section class="panel"><div class="panel-header"><h2>待确认 <small>${pending.length}</small></h2></div><div class="panel-body">${pending.map(r=>`<article class="inbox-record"><div class="section-heading"><strong>${names[r.submission.kind]} <small>${esc(r.submission.payload.date)}</small></strong><div class="actions"><button class="button small" data-action="inbox-edit" data-id="${r.id}">检查 / 修改</button><button class="button small primary" data-action="inbox-approve" data-id="${r.id}">确认入库</button></div></div><p class="inbox-body">${esc(summary(r.submission,data.config))}</p></article>`).join('')||'<div class="empty">'+(loading?'正在接收…':'暂时没有待确认记录。')+'</div>'}</div></section>`+
   (data?.items.some(r=>r.status!=='pending')?`<details class="inbox-history"><summary>已处理记录</summary>${data.items.filter(r=>r.status!=='pending').map(r=>`<div class="inbox-record"><small>${esc(r.submission.payload.date)} · ${r.status==='imported'?'已入库':'未采纳'}</small><p class="inbox-body">${esc(summary(r.accepted||r.submission,data.config))}</p></div>`).join('')}</details>`:'');
 }
 async function action(a,e){
  if(a==='inbox-sync'){await api('/api/mobile-inbox/sync',{});return refresh();}
  const row=data?.items.find(r=>r.id===e.dataset.id);if(!row)return;
  if(a==='inbox-edit')ctx.modal('检查手机记录',`<form data-form="inbox-approve" data-id="${row.id}" class="form-stack">${fields(row.submission.kind,row.submission.payload,data.config)}<div class="form-actions"><button type="button" class="button" data-action="inbox-reject" data-id="${row.id}">不采纳</button><button class="button primary">确认入库</button></div></form>`);
  if(a==='inbox-approve'){e.disabled=true;try{await api('/api/mobile-inbox/approve',{id:row.id});await load();await refresh();}finally{e.disabled=false;}}
  if(a==='inbox-reject'){if(!confirm('不采纳这条手机记录？原提交仍保留在已处理列表。'))return;await api('/api/mobile-inbox/reject',{id:row.id});ctx.closeModal();await refresh();}
 }
 async function submit(form){const r=data.items.find(r=>r.id===form.dataset.id),button=form.querySelector('[type=submit]')||form.querySelector('.primary');button.disabled=true;try{await api('/api/mobile-inbox/approve',{id:r.id,payload:payload(form,r.submission.kind)});ctx.closeModal();await load();await refresh();}finally{button.disabled=false;}}
 function change(e){if(updateAllocationForm(e))return;if(e.name==='schedule'){updateTaskPlanFields(e.closest('form'));return;}const form=e.closest('[data-form="inbox-approve"]');if(!form||!['date','habitId','domainId','problemId'].includes(e.name))return;const r=data.items.find(r=>r.id===form.dataset.id);if(['domainId','problemId'].includes(e.name)){const p=payload(form,r.submission.kind);if(e.name==='domainId')p.problemId=null;delete p.planId;const actions=form.querySelector('.form-actions').outerHTML;form.innerHTML=fields(r.submission.kind,p,data.config)+actions;return;}if(r.submission.kind!=='habit')return;const p={date:form.elements.date.value,habitId:form.elements.habitId.value};const actions=form.querySelector('.form-actions').outerHTML;form.innerHTML=fields('habit',p,data.config)+actions;}
 setInterval(()=>{if(ctx.view().page==='inbox'&&ctx.space()==='main'&&!document.querySelector('dialog[open]'))refresh();},10000);
 return {page,action,submit,change,refresh};
}
