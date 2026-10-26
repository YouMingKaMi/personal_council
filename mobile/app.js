import {names,escape as esc,today,fields,payload,summary} from '/static/capture-form.js';
const $=s=>document.querySelector(s), KEY='personal-capture-v1';
let saved;try{saved=JSON.parse(localStorage.getItem(KEY)||'null');}catch{}
let state=saved||{drafts:{},queue:[],config:null};
let kind='expense',tab='write',authenticated=false,connected=false,sending=false,items=[],noticeTimer;
const config=()=>state.config||{version:1,kinds:{},categories:[],habits:[]};
function persist(){try{localStorage.setItem(KEY,JSON.stringify(state));}catch{throw Error('手机存储失败，请先复制正文保留，暂时不要关闭页面');}}
function message(text){$('#notice').textContent=text;clearTimeout(noticeTimer);noticeTimer=setTimeout(()=>$('#notice').textContent='',5500);}
async function api(path,data){let r;try{r=await fetch(path,{method:data===undefined?'GET':'POST',headers:data===undefined?{}:{'Content-Type':'application/json','X-Capture-Client':'1'},body:data===undefined?undefined:JSON.stringify(data)});}catch{throw Error('暂时无法连接，未发送记录仍保留在此设备');}let d;try{d=await r.json();}catch{throw Error('服务暂时不可用，请稍后重试');}if(!r.ok){if(r.status===401)authenticated=false;throw Error(d.error||'连接失败');}return d;}
function draft(){const form=$('#capture-form');if(form){state.drafts[kind]=Object.fromEntries(new FormData(form));state.drafts[kind]._checked=[...form.querySelectorAll('[type=checkbox]:checked')].map(e=>e.name);persist();}}
function restoreDraft(){const form=$('#capture-form'),d=state.drafts[kind];if(!form||!d)return;for(const e of form.elements){if(!e.name)continue;if(e.type==='checkbox')e.checked=(d._checked||[]).includes(e.name);else if(d[e.name]!==undefined)e.value=d[e.name];}}
function currentPayload(){try{return payload($('#capture-form'),kind);}catch{return {date:$('#capture-form [name=date]')?.value||today(),habitId:$('#capture-form [name=habitId]')?.value};}}
function formPayloadFromDraft(){const d=state.drafts[kind]||{},p={...d};if(d.amount&&/^\d+(\.\d{1,2})?$/.test(d.amount)){const [a,b='']=d.amount.split('.');p.amountCents=Number(a)*100+Number(b.padEnd(2,'0'));}if(kind==='habit'){p.checked=d._checked?.includes('checked');p.items=Object.fromEntries((d._checked||[]).filter(k=>k.startsWith('item:')).map(k=>[k.slice(5),true]));}return p;}
function render(){
 const count=state.queue.length,ready=Object.keys(config().kinds).length>0;
 $('#app').innerHTML=`<header><div><div class="wordmark">PERSONAL COUNCIL</div><h1>随手记</h1><small>先记下来，留给电脑确认。</small></div><small><i class="dot"></i>${connected?'已连接':'离线 / 待连接'}</small></header>`+
 ((!authenticated&&!ready)?`<section class="connection"><h2>连接你的收件箱</h2><p>输入专属连接码，开始记录。</p><form id="login"><input name="token" aria-label="连接码" type="password" autocomplete="current-password" placeholder="连接码" required><button class="primary">连接</button></form></section>`:
 `<nav class="tabs" aria-label="页面"><button data-tab="write" aria-selected="${tab==='write'}">记下来</button><button data-tab="queue" aria-selected="${tab==='queue'}">待发送${count?`<span class="count">${count}</span>`:''}</button><button data-tab="sent" aria-selected="${tab==='sent'}">已提交</button></nav>`+
 (tab==='write'?ready?`<div class="types">${Object.keys(names).filter(k=>config().kinds[k]).map(k=>`<button class="type" data-kind="${k}" aria-pressed="${k===kind}"><b>${{expense:'¥',task:'✓',chronicle:'≡',ideas:'✧',materials:'↳',habit:'○',problem:'?',progress:'→'}[k]}</b>${names[k]}</button>`).join('')}</div><section class="sheet"><div class="sheet-head"><h2>${names[kind]}</h2><small>草稿保存在此设备</small></div><form id="capture-form">${fields(kind,formPayloadFromDraft(),config())}<div class="submit"><small>${connected?'发送到电脑收件箱':'离线时先保存，联网后重试'}</small><button class="primary" type="submit">${connected?'发送':'保存待发送'} ↗</button></div></form></section>`:'<div class="empty">等待电脑首次连接并发布录入选项。<br>稍后点击更新选项。</div>':
 tab==='queue'?`<div class="toolbar"><small>${count} 条待发送</small><button data-action="retry">重新发送</button></div>${state.queue.map(r=>`<article class="row"><div class="row-head"><span>${names[r.submission.kind]} · ${esc(r.submission.payload.date)}</span><span>待发送</span></div><p>${esc(summary(r.submission,config()))}</p>${r.error?`<div class="error">${esc(r.error)}</div>`:''}<div class="actions"><button data-edit="${esc(r.submission.id)}">复制回表单</button></div></article>`).join('')||'<div class="empty">没有待发送的记录。</div>'}`:
 `<div class="toolbar"><small>最近提交</small><button data-action="refresh">刷新状态</button></div>${items.map(r=>`<article class="row"><div class="row-head"><span>${names[r.submission.kind]} · ${esc(r.submission.payload.date)}</span><span>${{pending:'等待电脑确认',imported:'已入库',rejected:'未采纳'}[r.status]}</span></div><p>${esc(summary(r.submission,config()))}</p></article>`).join('')||'<div class="empty">还没有提交记录，或尚未连接。</div>'}`)+
 `<div class="bottom"><button class="link" data-action="refresh">更新选项与状态</button><button class="link" data-action="connect">${authenticated?'重新连接':'输入连接码'}</button></div><div id="inline-login"></div>`);
 restoreDraft();
}
async function refresh(){
 try{const c=await api('/api/config');if(c.version!==1)throw Error('表单版本不兼容，请更新页面；原稿仍保留');
  state.config=c;persist();authenticated=true;connected=true;
  if(!c.kinds[kind])kind=Object.keys(c.kinds)[0]||'expense';
  items=(await api('/api/items')).items;
 }catch(e){connected=false;if(navigator.onLine)message(e.message);}
 render();
}
async function flush(){
 if(sending||!navigator.onLine)return;sending=true;
 try{for(const r of [...state.queue]){
  try{await api('/api/submit',r.submission);state.queue=state.queue.filter(x=>x.submission.id!==r.submission.id);persist();connected=true;}
  catch(e){r.error=e.message;persist();connected=false;break;}
 }}finally{sending=false;}
 await refresh();
}
document.addEventListener('input',e=>{if(e.target.closest('#capture-form'))try{draft();}catch(err){message(err.message);}});
document.addEventListener('change',e=>{if(e.target.name==='domainId'){draft();delete state.drafts[kind].problemId;persist();render();return;}if(kind==='habit'&&['date','habitId'].includes(e.target.name)){
 const p=currentPayload();state.drafts[kind]={date:p.date,habitId:p.habitId};try{persist();render();}catch(err){message(err.message);}
}});
document.addEventListener('click',async e=>{const b=e.target.closest('button');if(!b)return;try{
 if(b.dataset.tab){draft();tab=b.dataset.tab;render();if(tab==='sent')await refresh();}
 if(b.dataset.kind){draft();kind=b.dataset.kind;render();}
 if(b.dataset.action==='refresh'){draft();await refresh();await flush();}
 if(b.dataset.action==='retry')await flush();
 if(b.dataset.action==='connect'){$('#inline-login').innerHTML='<form id="login" class="connection"><label>专属连接码<input name="token" type="password" aria-label="连接码" required></label><button class="primary">连接</button></form>';$('#login input').focus();}
 if(b.dataset.edit){
  const r=state.queue.find(x=>x.submission.id===b.dataset.edit);
  if(!confirm('待发送的原记录仍会保留。修改后发送可能形成另一条记录，请先确认原记录是否已收到。继续复制？'))return;
  draft();kind=r.submission.kind;const p=r.submission.payload;
  state.drafts[kind]={...p,amount:p.amountCents===undefined?'':(p.amountCents/100).toFixed(2),_checked:[...(p.checked?['checked']:[]),...Object.entries(p.items||{}).filter(([,v])=>v).map(([k])=>'item:'+k)]};persist();tab='write';render();
 }
}catch(err){message(err.message);}});
document.addEventListener('submit',async e=>{e.preventDefault();const form=e.target;try{
 if(form.id==='login'){const button=form.querySelector('button');button.disabled=true;try{await api('/api/session',{token:new FormData(form).get('token')});await refresh();await flush();}finally{button.disabled=false;}return;}
 if(form.id!=='capture-form')return;
 const p=payload(form,kind),submission={version:1,id:crypto.randomUUID(),kind,createdAt:new Date().toISOString(),payload:p};
 draft();state.queue.push({submission});try{persist();}catch(err){state.queue.pop();throw err;}
 delete state.drafts[kind];persist();render();message('已保存在待发送列表');await flush();
 if(!state.queue.some(r=>r.submission.id===submission.id))message('已发送，等待电脑确认');
}catch(err){message(err.message);}});
window.addEventListener('online',()=>{draft();flush().catch(e=>message(e.message));});
window.addEventListener('offline',()=>{draft();connected=false;render();});
render();refresh().then(flush).catch(e=>message(e.message));
if('serviceWorker' in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>{});
