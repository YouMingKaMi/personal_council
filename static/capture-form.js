import {allocationFields,allocationFromForm,updateAllocationForm} from './expense-allocation-form.js';
import {defaultMetrics,metricInputs,metricValues,metricFormat} from './daily-metrics-model.js';
import {planLabel} from './plan-path.js';
import {taskPlanFields,taskPlan,updateTaskPlanFields} from './task-model.js';
export {updateAllocationForm,updateTaskPlanFields};
// Public v1 field names are stable. Both desktop approval and phone use this form adapter.
export const names={expense:'花销',task:'任务',taskPlan:'任务',chronicle:'编年史',ideas:'想法',materials:'原料',habit:'习惯',problem:'新问题',progress:'推进进展',plan:'解决方案',focus:'推进计时',metrics:'每日指标'};
export const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const today=()=>{const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;};
const option=(id,label,selected)=>`<option value="${escape(id)}" ${id===selected?'selected':''}>${escape(label)}</option>`;
export function habitConfig(config,id,date){return [...(config.habits.find(h=>h.id===id)?.versions||[])].filter(v=>v.fromDate<=date).sort((a,b)=>b.fromDate.localeCompare(a.fromDate))[0];}
export const durationLabel=ms=>{const s=Math.floor(ms/1000),m=Math.floor(s/60),h=Math.floor(m/60);return h?`${h}h ${m%60}m`:m?`${m}m ${s%60}s`:`${s}s`;};
export function fields(kind,p={},config){
 const date=p.date||today();
 let html=`<label ${kind==='taskPlan'?'hidden':''}>日期<input name="date" aria-label="日期" type="date" min="1901-01-01" max="2099-12-31" value="${escape(date)}" ${kind==='focus'?'readonly':''} required></label>`;
 if(kind==='metrics'){const defs=(config.metricDefinitions||defaultMetrics).filter(d=>!d.archived||Object.hasOwn(p.values||{},d.id)||String(p['metric:'+d.id]??'').trim()!=='');html+=`<input type="hidden" name="metricDefinitions" value="${escape(JSON.stringify(defs))}">`+metricInputs(defs,p.values||{},p)+`<label>备注（可选）<textarea name="note" aria-label="指标备注" rows="2" maxlength="10000">${escape(p.note)}</textarea></label><details ${p.replaceExisting?'open':''}><summary>已有记录的更新</summary><label class="check"><input type="checkbox" name="replaceExisting" ${p.replaceExisting?'checked':''}>更新当天同项已有值</label></details>`;}
 if(kind==='focus'){
  const options=(rows,id,missing)=>`${id&&!rows.some(r=>r.id===id)?option(id,missing,id):''}${rows.map(r=>option(r.id,r.problemId?planLabel(config.plans||[],r.id):r.title||r.name,id)).join('')}`;
  const ds=config.domains||[],ps=(config.problems||[]).filter(x=>x.domainId===p.domainId),qs=(config.plans||[]).filter(x=>x.domainId===p.domainId&&x.problemId===p.problemId);
  html+=`<label>领域<select name="domainId" aria-label="领域">${options(ds,p.domainId,'原领域已变化')}</select></label><label>关联问题（可选）<select name="problemId" aria-label="关联问题"><option value="">自由推进</option>${options(ps,p.problemId,'原问题已变化')}</select></label><label>方案（可选）<select name="planId" aria-label="方案"><option value="">不关联方案</option>${options(qs,p.planId,'原方案已变化')}</select></label><label>做了什么<input name="title" aria-label="计时内容" maxlength="300" value="${escape(p.title)}"></label><p class="hint">原始用时 ${durationLabel(p.durationMs||0)} · 按实际时段分配到每天</p><details><summary>原始时段 · ${(p.segments||[]).length} 段</summary><div class="capture-time-segments">${(p.segments||[]).slice(0,20).map(r=>`${escape(new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(new Date(r.start)))} — ${escape(new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(new Date(r.end)))}`).join('<br>')}${(p.segments||[]).length>20?'<br>更多时段保留在原始记录中':''}</div></details><input type="hidden" name="focusSegments" value="${escape(JSON.stringify(p.segments||[]))}"><input type="hidden" name="focusDuration" value="${escape(p.durationMs)}"><details ${p.adjustedDurationMs!==undefined?'open':''}><summary>修正用时（可选）</summary><label>分钟<input name="adjustedMinutes" aria-label="修正用时（分钟）" type="number" min="0" max="1440" step="any" value="${escape(p.adjustedDurationMs===undefined?'':p.adjustedDurationMs/60000)}"></label><small>留空保留原始时段；填写后按所选日期补记，原始计时仍保留。</small></details><label>推进记录（可选）<textarea name="note" aria-label="计时进展" maxlength="100000">${escape(p.note)}</textarea></label>`;
 }
 if(['problem','progress','plan'].includes(kind)){
  const did=p.domainId||config.domains?.[0]?.id;
  html+=`<label>领域<select name="domainId" aria-label="领域">${(config.domains||[]).map(d=>option(d.id,d.name,did)).join('')}</select></label>`;
  if(kind==='problem')html+=`<label>问题<input name="title" aria-label="问题" value="${escape(p.title)}" maxlength="300" required></label><label>具体情况（可选）<textarea name="body" aria-label="具体情况" maxlength="100000">${escape(p.body)}</textarea></label><label>下一步（可选）<textarea name="next" aria-label="下一步" maxlength="100000">${escape(p.next)}</textarea></label>`;
  else {
   const ps=(config.problems||[]).filter(x=>x.domainId===did),pid=p.problemId||(kind==='plan'?ps[0]?.id:'');
   html+=`<label>${kind==='plan'?'所属问题':'关联问题（可选）'}<select name="problemId" aria-label="关联问题" ${kind==='plan'?'required':''}>${kind==='plan'?'':'<option value="">领域进展</option>'}${ps.map(x=>option(x.id,x.title,pid)).join('')}</select></label>`;
   if(kind==='plan')html+=`<label>上级路径<select name="parentId" aria-label="上级路径"><option value="">主问题</option>${p.parentId&&!(config.plans||[]).some(q=>q.id===p.parentId)?option(p.parentId,'原上级路径已变化',p.parentId):''}${(config.plans||[]).filter(q=>q.domainId===did&&q.problemId===pid).map(q=>option(q.id,planLabel(config.plans||[],q.id),p.parentId)).join('')}</select></label><label>类型<select name="nodeType"><option value="solution">解决方案</option><option value="question" ${p.nodeType==='question'?'selected':''}>遇到的子问题</option></select></label><label>解决方案<input name="title" aria-label="解决方案" value="${escape(p.title)}" maxlength="300" required></label><label>说明（可选）<textarea name="body" aria-label="方案说明" maxlength="100000">${escape(p.body)}</textarea></label>`;
   else html+=`<label>方案（可选）<select name="planId" aria-label="方案"><option value="">问题或领域的整体进展</option>${(config.plans||[]).filter(q=>q.domainId===did&&q.problemId===pid).map(q=>option(q.id,planLabel(config.plans||[],q.id),p.planId)).join('')}</select></label><label>进展<textarea name="body" aria-label="进展" maxlength="100000" required>${escape(p.body)}</textarea></label>`;
  }
 }
 if(['task','taskPlan','expense'].includes(kind))html+=`<label>${kind==='expense'?'消费内容':'任务内容'}<input name="title" aria-label="内容" maxlength="120" value="${escape(p.title)}" placeholder="${kind==='expense'?'例如：午餐':'准备做些什么'}" required></label>`;
 if(kind==='expense')html+=`<label>金额 · 元<input name="amount" aria-label="金额" inputmode="decimal" autocomplete="off" value="${p.amountCents!==undefined?(p.amountCents/100).toFixed(2):''}" placeholder="0.00" required></label><label>用途<select name="categoryId" aria-label="用途">${config.categories.map(c=>option(c.id,c.name,p.categoryId||config.categories[0]?.id)).join('')}</select></label><label>必要性<select name="necessity" aria-label="必要性">${[['necessary','必要'],['optional','非必要'],['undecided','待判断']].map(([id,n])=>option(id,n,p.necessity||'necessary')).join('')}</select></label>`;
 if(kind==='expense')html+=allocationFields(p.allocation,date,p);
 if(kind==='taskPlan')html+=taskPlanFields({schedule:p.schedule||'recent',date:p.scheduledDate,deadline:p.deadline,deadlineTime:p.deadlineTime},date);
 if(['ideas','materials','chronicle'].includes(kind))html+=`<label class="body-field"><span>${kind==='chronicle'?'记录':'正文'}</span><textarea name="${kind==='chronicle'?'text':'body'}" aria-label="正文" rows="8" maxlength="100000" placeholder="写下来…" required>${escape(p.body??p.text??'')}</textarea></label>`;
 if(kind==='chronicle')html+=`<details ${p.endDate?'open':''}><summary>跨日期事件</summary><label>结束日期<input name="endDate" aria-label="结束日期" type="date" min="1901-01-01" max="2099-12-31" value="${escape(p.endDate||'')}"></label></details>`;
 if(kind==='habit'){
  const hs=config.habits.filter(h=>habitConfig(config,h.id,date)?.enabled),id=p.habitId||hs[0]?.id,c=habitConfig(config,id,date);
  html+=`<label>习惯<select name="habitId" aria-label="习惯">${hs.map(h=>option(h.id,habitConfig(config,h.id,date)?.name||h.name,id)).join('')}</select></label>`;
  if(c){html+=`<input type="hidden" name="versionId" value="${escape(c.id)}"><input type="hidden" name="kind" value="${escape(c.kind)}">`;
   if(c.kind==='number')html+=`<label>当日总数量${c.unit?' · '+escape(c.unit):''}<input name="value" aria-label="当日总数量" type="number" min="0" max="1000000000" step="any" value="${escape(p.value??'')}" required></label>`;
   if(c.kind==='check')html+=`<label class="check"><input name="checked" type="checkbox" ${p.checked!==false?'checked':''}> 已完成</label>`;
   if(c.kind==='checklist')html+=`<div class="checks">${c.items.map(i=>`<label class="check"><input type="checkbox" name="item:${escape(i.id)}" ${p.items?.[i.id]?'checked':''}>${escape(i.name)}</label>`).join('')}</div>`;
   html+='<small>已有当天记录时会保留原记录，不直接覆盖。</small>';
  }else html+='<p>这一天没有可记录的习惯，请选择其他日期或更新选项。</p>';
 }
 return html;
}
export function payload(form,kind){
 const f=new FormData(form),s=k=>String(f.get(k)||'');let p={date:s('date')};
 if(kind==='metrics'){const defs=JSON.parse(s('metricDefinitions'));p.values=metricValues(form,defs);if(s('note').trim())p.note=s('note');if(f.has('replaceExisting'))p.replaceExisting=true;if(!Object.keys(p.values).length&&!p.note)throw Error('至少填写一项指标或备注');}
 if(kind==='focus'){
  Object.assign(p,{domainId:s('domainId'),problemId:s('problemId')||null,planId:s('planId')||null,title:s('title'),note:s('note'),segments:JSON.parse(s('focusSegments')),durationMs:Number(s('focusDuration'))});
  if(s('adjustedMinutes').trim()){const n=Number(s('adjustedMinutes'));if(!Number.isFinite(n)||n<0||n>1440)throw Error('修正用时须在 0—1440 分钟内');p.adjustedDurationMs=Math.round(n*60000);}
 }
 if(['problem','progress','plan'].includes(kind)){
  p.domainId=s('domainId');p.body=s('body');
  if(kind==='problem'){p.title=s('title').trim();p.next=s('next');}
  else {p.problemId=s('problemId')||null;if(kind==='plan'){p.title=s('title').trim();if(s('parentId'))p.parentId=s('parentId');if(s('nodeType')==='question')p.nodeType='question';}else if(s('planId'))p.planId=s('planId');}
 }
 if(['task','taskPlan','expense'].includes(kind))p.title=s('title').trim();
 if(kind==='taskPlan'){const plan=taskPlan({schedule:s('schedule'),scheduledDate:s('scheduledDate'),deadline:s('deadline'),deadlineTime:s('deadlineTime')});p.schedule=plan.schedule;if(plan.date)p.scheduledDate=plan.date;if(plan.deadline)p.deadline=plan.deadline;if(plan.deadlineTime)p.deadlineTime=plan.deadlineTime;}
 if(kind==='expense'){
  const raw=s('amount').trim();if(!/^\d{1,9}(\.\d{1,2})?$/.test(raw))throw Error('金额请填写最多两位小数');
  const [a,b='']=raw.split('.');p.amountCents=Number(a)*100+Number(b.padEnd(2,'0'));if(p.amountCents<=0)throw Error('金额须大于零');
  p.categoryId=s('categoryId');p.necessity=s('necessity');const allocation=allocationFromForm(form);if(allocation)p.allocation=allocation;
 }
 if(['ideas','materials'].includes(kind))p.body=s('body');
 if(kind==='chronicle'){p.text=s('text');p.endDate=s('endDate')||null;}
 if(kind==='habit'){
  Object.assign(p,{habitId:s('habitId'),versionId:s('versionId'),kind:s('kind')});
  if(p.kind==='number'){if(!s('value'))throw Error('请填写数量');p.value=Number(s('value'));if(!Number.isFinite(p.value)||p.value<0)throw Error('数量无效');}
  if(p.kind==='check')p.checked=f.has('checked');
  if(p.kind==='checklist'){p.items={};for(const e of form.querySelectorAll('[name^="item:"]'))p.items[e.name.slice(5)]=e.checked;}
 }
 return p;
}
export function summary(s,config){
 const p=s.payload;
 if(s.kind==='metrics'){const defs=config.metricDefinitions||defaultMetrics;return Object.entries(p.values).map(([id,n])=>{const d=defs.find(d=>d.id===id);return d?d.name+'：'+metricFormat(d,n):id+'：'+n;}).join(' · ')+(p.note?'\n'+p.note:'')+(p.replaceExisting?'\n已确认更新当天同项已有值':'');}
 if(s.kind==='focus')return `${config.domains?.find(d=>d.id===p.domainId)?.name||'原领域已变化'} · ${durationLabel(p.adjustedDurationMs??p.durationMs)}${p.title?' · '+p.title:''}${p.planId?'\n方案：'+(planLabel(config.plans||[],p.planId)||'原方案已变化'):''}${p.note?'\n'+p.note:''}`;
 if(s.kind==='expense')return `${p.title} · ¥${(p.amountCents/100).toFixed(2)} · ${config.categories.find(c=>c.id===p.categoryId)?.name||'原分类已停用'} · ${{necessary:'必要',optional:'非必要',undecided:'待判断'}[p.necessity]}${p.allocation?' · 长期使用 '+p.allocation.startDate+' — '+p.allocation.expectedEndDate:''}`;
 if(s.kind==='taskPlan')return `${p.title} · ${p.schedule==='day'?'安排 '+p.scheduledDate:p.schedule==='deadline'?'截至 '+p.deadline+(p.deadlineTime?' '+p.deadlineTime:''):'近期完成'}`;
 if(s.kind==='habit')return `${config.habits.find(h=>h.id===p.habitId)?.name||'习惯'} · ${p.kind==='check'?(p.checked?'已完成':'未完成'):p.kind==='number'?p.value+'（当日总数）':Object.values(p.items).filter(Boolean).length+' 项已勾选'}`;
 if(['problem','progress','plan'].includes(s.kind))return `${config.domains?.find(d=>d.id===p.domainId)?.name||'领域已变更'} · ${p.title||p.body}${s.kind==='plan'?('\n'+(p.nodeType==='question'?'子问题':'解决方案')+' · 上级：'+(p.parentId?(planLabel(config.plans||[],p.parentId)||'原上级路径已变化'):'主问题')):''}${p.next?'\n下一步：'+p.next:''}${p.planId?'\n方案：'+(planLabel(config.plans||[],p.planId)||'原方案已变化'):''}`;
 return p.title||p.text||p.body;
}
