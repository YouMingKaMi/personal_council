// Public v1 field names are stable. Both desktop approval and phone use this form adapter.
export const names={expense:'花销',task:'任务',chronicle:'编年史',ideas:'想法',materials:'原料',habit:'习惯',problem:'新问题',progress:'推进进展'};
export const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const today=()=>{const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;};
const option=(id,label,selected)=>`<option value="${escape(id)}" ${id===selected?'selected':''}>${escape(label)}</option>`;
export function habitConfig(config,id,date){return [...(config.habits.find(h=>h.id===id)?.versions||[])].filter(v=>v.fromDate<=date).sort((a,b)=>b.fromDate.localeCompare(a.fromDate))[0];}
export function fields(kind,p={},config){
 const date=p.date||today();
 let html=`<label>日期<input name="date" aria-label="日期" type="date" min="1901-01-01" max="2099-12-31" value="${escape(date)}" required></label>`;
 if(['problem','progress'].includes(kind)){
  const did=p.domainId||config.domains?.[0]?.id;
  html+=`<label>领域<select name="domainId" aria-label="领域">${(config.domains||[]).map(d=>option(d.id,d.name,did)).join('')}</select></label>`;
  if(kind==='problem')html+=`<label>问题<input name="title" aria-label="问题" value="${escape(p.title)}" maxlength="300" required></label><label>具体情况（可选）<textarea name="body" aria-label="具体情况" maxlength="100000">${escape(p.body)}</textarea></label><label>下一步（可选）<textarea name="next" aria-label="下一步" maxlength="100000">${escape(p.next)}</textarea></label>`;
  else html+=`<label>关联问题（可选）<select name="problemId" aria-label="关联问题"><option value="">领域进展</option>${(config.problems||[]).filter(x=>x.domainId===did).map(x=>option(x.id,x.title,p.problemId)).join('')}</select></label><label>进展<textarea name="body" aria-label="进展" maxlength="100000" required>${escape(p.body)}</textarea></label>`;
 }
 if(['task','expense'].includes(kind))html+=`<label>${kind==='expense'?'消费内容':'任务内容'}<input name="title" aria-label="内容" maxlength="120" value="${escape(p.title)}" placeholder="${kind==='expense'?'例如：午餐':'准备做些什么'}" required></label>`;
 if(kind==='expense')html+=`<label>金额 · 元<input name="amount" aria-label="金额" inputmode="decimal" autocomplete="off" value="${p.amountCents!==undefined?(p.amountCents/100).toFixed(2):''}" placeholder="0.00" required></label><label>用途<select name="categoryId" aria-label="用途">${config.categories.map(c=>option(c.id,c.name,p.categoryId||config.categories[0]?.id)).join('')}</select></label><label>必要性<select name="necessity" aria-label="必要性">${[['necessary','必要'],['optional','可选'],['undecided','待判断']].map(([id,n])=>option(id,n,p.necessity||'necessary')).join('')}</select></label>`;
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
 if(['problem','progress'].includes(kind)){
  p.domainId=s('domainId');p.body=s('body');
  if(kind==='problem'){p.title=s('title').trim();p.next=s('next');}
  else p.problemId=s('problemId')||null;
 }
 if(['task','expense'].includes(kind))p.title=s('title').trim();
 if(kind==='expense'){
  const raw=s('amount').trim();if(!/^\d{1,9}(\.\d{1,2})?$/.test(raw))throw Error('金额请填写最多两位小数');
  const [a,b='']=raw.split('.');p.amountCents=Number(a)*100+Number(b.padEnd(2,'0'));if(p.amountCents<=0)throw Error('金额须大于零');
  p.categoryId=s('categoryId');p.necessity=s('necessity');
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
 if(s.kind==='expense')return `${p.title} · ¥${(p.amountCents/100).toFixed(2)} · ${config.categories.find(c=>c.id===p.categoryId)?.name||'原分类已停用'} · ${{necessary:'必要',optional:'可选',undecided:'待判断'}[p.necessity]}`;
 if(s.kind==='habit')return `${config.habits.find(h=>h.id===p.habitId)?.name||'习惯'} · ${p.kind==='check'?(p.checked?'已完成':'未完成'):p.kind==='number'?p.value+'（当日总数）':Object.values(p.items).filter(Boolean).length+' 项已勾选'}`;
 if(['problem','progress'].includes(s.kind))return `${config.domains?.find(d=>d.id===p.domainId)?.name||'领域已变更'} · ${p.title||p.body}${p.next?'\n下一步：'+p.next:''}`;
 return p.title||p.text||p.body;
}
