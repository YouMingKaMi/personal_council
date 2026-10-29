import {recordingMode} from '/static/activity-model.js';
import {planLabel} from '/static/plan-path.js';
import {escape as esc,durationLabel} from '/static/capture-form.js';
import {beginTimer,checkpoint,transition,timerSubmission,elapsed,timeClock} from './timer-model.js';

const KEY='personal-capture-timer-v1';
const option=(x,id)=>`<option value="${esc(x.id)}" ${x.id===id?'selected':''}>${esc(x.title||x.name)}</option>`;
const button=(action,label,cls='')=>`<button type="button" class="${cls}" data-action="timer-${action}">${label}</button>`;
const stamp=ms=>new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(ms));
export function createPhoneWorkbench(ctx){
 let acting=false;
 function read(){const w=JSON.parse(localStorage.getItem(KEY)||'null');return w||{version:1,timer:null,draft:{}};}
 function write(w){try{localStorage.setItem(KEY,JSON.stringify(w));}catch{throw Error('计时未能保存到手机，请保留页面并检查浏览器存储空间');}}
 const lock=fn=>navigator.locks?.request?navigator.locks.request(KEY,fn):Promise.resolve().then(fn);
 function hasTimer(){try{return !!read().timer;}catch{return true;}}
 function setup(w,c){
  const ds=c.domains||[],v=w.draft||{},focused=ds.filter(d=>(c.focusDomainIds||[]).includes(d.id));
  const did=ds.some(d=>d.id===v.domainId)?v.domainId:focused[0]?.id||ds[0]?.id;
  const ps=(c.problems||[]).filter(p=>p.domainId===did),pid=ps.some(p=>p.id===v.problemId)?v.problemId:'';
  const qs=(c.plans||[]).filter(q=>q.domainId===did&&q.problemId===pid),xs=(c.activities||[]).filter(x=>x.domainId===did),aid=pid?'':Object.hasOwn(v,'activityId')?(xs.some(x=>x.id===v.activityId)?v.activityId:''):recordingMode(ds.find(d=>d.id===did))==='activities'?xs[0]?.id||'':'';
  if(!ds.length)return '<p class="empty">先在电脑建立领域，再更新手机选项。</p>';
  return `<form id="focus-start" class="focus-config"><label>领域<select name="domainId" aria-label="计时领域">${focused.length?`<optgroup label="专注领域">${focused.map(d=>option(d,did)).join('')}</optgroup><optgroup label="其他领域">${ds.filter(d=>!focused.some(x=>x.id===d.id)).map(d=>option(d,did)).join('')}</optgroup>`:ds.map(d=>option(d,did)).join('')}</select></label>${xs.length?`<label>训练项目<select name="activityId" aria-label="计时训练项目"><option value="">不选项目 / 自由记录</option>${xs.map(x=>option(x,aid)).join('')}</select></label>`:''}<label>这次做什么（可选）<input name="title" aria-label="这次做什么" maxlength="300" value="${esc(v.title)}" placeholder="例如：跑步、训练、读资料"></label><details ${pid?'open':''}><summary>关联问题或方案（可选）</summary><label>问题<select name="problemId" aria-label="计时问题"><option value="">自由推进</option>${ps.map(p=>option(p,pid)).join('')}</select></label><label>方案<select name="planId" aria-label="计时方案"><option value="">不关联方案</option>${qs.map(q=>option({...q,title:planLabel(c.plans||[],q.id)},v.planId)).join('')}</select></label></details><button type="submit" class="primary focus-start">▷ ${recordingMode(ds.find(d=>d.id===did))==='activities'?'开始训练':'开始推进'}</button>${c.kinds?.time?button('manual','补记时间','link'):''}</form>${w.cancelledTimer?button('restore','撤销上次取消','link focus-undo'):''}`;
 }
 function view(){
  try{
   const w=read(),t=w.timer,c=ctx.config();
   if(!t)return `<section class="sheet phone-workbench"><div class="sheet-head"><h2>此时</h2><small>准备开始</small></div>${setup(w,c)}</section>`;
   const names=t.names||{},subject=t.title||names.plan||names.problem||names.domain;
   const header=`<div class="sheet-head"><h2>此时</h2><small>${{running:'正在做',paused:'已暂停',finished:'已结束',queued:'待保存发送'}[t.status]}</small></div><div class="phone-focus-domain">${esc(names.domain||'领域')}</div>${subject&&subject!==names.domain?`<h2 class="phone-focus-title">${esc(subject)}</h2>`:''}${names.problem&&subject!==names.problem?`<p class="phone-focus-context">${esc(names.problem)}</p>`:''}<div class="phone-focus-clock" data-phone-clock>${timeClock(elapsed(t))}</div>`;
   if(t.status==='queued')return `<section class="sheet phone-workbench">${header}<p class="hint">计时已结束，正在保留待发送记录。</p>${button('recover','重试保存','primary')}</section>`;
   const warning=t.clockChanged?'<p class="timer-warning">设备时间发生变化，已暂停。请校准时间，并在发送前核对用时。</p>':'';
   if(t.status==='finished')return `<section class="sheet phone-workbench">${header}<p class="phone-focus-range">${stamp(t.startedAt)} — ${stamp(t.endedAt)}</p>${warning}<label>这次的进展（可选）<textarea id="focus-note" aria-label="计时进展" maxlength="100000" rows="3" placeholder="做了什么，有什么发现…">${esc(t.note)}</textarea></label><div class="phone-focus-actions">${button('send','发送到电脑 ↗','primary')}${button('cancel','取消本次','link')}</div><p class="hint">电脑确认后，加入时间统计与对应进展。</p></section>`;
   return `<section class="sheet phone-workbench">${header}${warning}<div class="phone-focus-actions">${button(t.status==='running'?'pause':'resume',t.status==='running'?'Ⅱ 暂停':'▷ 继续')}${button('finish','✓ 结束','primary')}</div>${button('cancel','取消本次','link focus-cancel')}<p class="hint">锁屏期间继续计时，结束后再发送。</p></section>`;
  }catch{return '<section class="sheet"><p>计时草稿暂时无法读取，请保留页面并检查浏览器存储。</p></section>';}
 }
 function stage(w){
  const t=w.timer;if(!t||t.status!=='queued')return null;
  ctx.enqueue(t.submission);w.timer=null;write(w);return t.submission.id;
 }
 async function recover(){return lock(()=>stage(read()));}
 async function submit(form){
  if(form.id!=='focus-start')return false;
  await lock(()=>{const w=read();if(w.timer)throw Error('请先结束当前计时');const f=Object.fromEntries(new FormData(form)),c=ctx.config(),d=c.domains?.find(d=>d.id===f.domainId),p=c.problems?.find(p=>p.id===f.problemId&&p.domainId===d?.id),q=c.plans?.find(q=>q.id===f.planId&&q.problemId===p?.id&&q.domainId===d?.id),x=c.activities?.find(x=>x.id===f.activityId&&x.domainId===d?.id);
   if(f.activityId&&(f.problemId||f.planId))throw Error('请分别选择训练项目或问题方案');
   if(!d||f.problemId&&!p||f.planId&&!q||f.activityId&&!x)throw Error('选项已变化，请更新后重选');
   w.draft=f;w.timer=beginTimer({domainId:d.id,problemId:p?.id||null,planId:q?.id||null,...(x?{activityId:x.id}:{}),title:f.title.trim()||x?.name||q?.title||p?.title||'',names:{domain:d.name,activity:x?.name||'',problem:p?.title||'',plan:q?.title||''}},Date.now(),crypto.randomUUID());write(w);
  });ctx.render();return true;
 }
 async function action(name){
  if(!name?.startsWith('timer-'))return false;
  if(acting)return true;acting=true;let id;
  try{await lock(()=>{
   const w=read(),op=name.slice(6),note=document.querySelector('#focus-note')?.value;
   if(op==='recover'){id=stage(w);return;}
   if(op==='restore'){if(w.timer||!w.cancelledTimer)throw Error('当前有计时或没有可恢复的记录');w.timer=w.cancelledTimer;w.cancelledTimer=null;write(w);return;}
   if(op==='cancel'){if(!w.timer)return;if(w.timer.status==='queued')throw Error('这次已进入待发送，请在电脑处理');w.cancelledTimer=w.timer.status==='finished'?w.timer:transition(w.timer,'pause',Date.now());if(note!==undefined)w.cancelledTimer.note=note;w.timer=null;write(w);return;}
   if(op==='send'){
    if(w.timer?.status==='queued'){id=stage(w);return;}
    if(!w.timer||w.timer.status!=='finished')throw Error('请先结束计时');
    if(note!==undefined)w.timer.note=note;
    w.timer={...w.timer,status:'queued',submission:timerSubmission(w.timer)};write(w);id=stage(w);return;
   }
   w.timer=transition(w.timer,op,Date.now());write(w);
  });}finally{acting=false;ctx.render();}
  if(id){ctx.message('已保存在待发送列表');await ctx.flush();if(!ctx.isQueued(id))ctx.message('已发送，等待电脑确认');}
  return true;
 }
 function input(e){
  const form=e.closest('#focus-start');if(!form&&e.id!=='focus-note')return;
  const values=form?Object.fromEntries(new FormData(form)):null,note=e.value;
  lock(()=>{const w=read();if(values&&!w.timer)w.draft=values;else if(e.id==='focus-note'&&w.timer?.status==='finished')w.timer.note=note;else return;write(w);}).catch(err=>ctx.message(err.message));
 }
 async function change(e){
  const form=e.closest('#focus-start');if(!form||!['domainId','problemId','activityId'].includes(e.name))return false;
  const values=Object.fromEntries(new FormData(form));if(e.name==='domainId'){values.problemId='';delete values.activityId;values.title='';}if(e.name==='activityId'){values.problemId='';values.title='';}if(e.name==='problemId'&&values.problemId){values.activityId='';values.title='';}values.planId='';
  await lock(()=>{const w=read();if(!w.timer){w.draft=values;write(w);}});ctx.render();return true;
 }
 function tick(){try{const t=read().timer;for(const e of document.querySelectorAll('[data-phone-clock]'))e.textContent=timeClock(elapsed(t));}catch{}}
 function saveClock(){lock(()=>{const w=read();if(w.timer?.status==='running'){const was=w.timer.status;w.timer=checkpoint(w.timer,Date.now());write(w);if(w.timer.status!==was)ctx.render();}}).catch(e=>ctx.message(e.message));}
 setInterval(tick,1000);setInterval(saveClock,15000);
 document.addEventListener('visibilitychange',()=>{saveClock();tick();});window.addEventListener('pagehide',saveClock);
 window.addEventListener('storage',e=>{if(e.key===KEY)ctx.render();});
 return {view,submit,action,input,change,recover,hasTimer};
}
