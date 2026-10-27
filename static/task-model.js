export const scheduleOf=t=>t.schedule||'day';
export const taskRecordDate=t=>t.date||t.completedDate||t.deadline||null;
export function taskVisible(t,date){return scheduleOf(t)==='day'&&t.date===date;}
export const taskRequired=taskVisible;
export function backlogTasks(state,{done=false,day}={}){return state.tasks.filter(t=>scheduleOf(t)!=='day'&&t.done===done&&(!done||!day||t.completedDate===day)).sort((a,b)=>done?(b.completedDate||'').localeCompare(a.completedDate||''):(a.deadline||'9999').localeCompare(b.deadline||'9999')||(a.deadlineTime||'23:59').localeCompare(b.deadlineTime||'23:59'));}
export function ensureBacklogPanel(state){if(state.layout.some(p=>p.id==='task-backlog'))return false;const i=state.layout.findIndex(p=>p.id==='tasks');state.layout.splice(i<0?state.layout.length:i+1,0,{id:'task-backlog',size:'half',visible:true});return true;}
export function updateTaskDetails(task,{title,...plan}){if(!title?.trim()||title.trim().length>200)throw Error('请填写任务内容（不超过200字）');Object.assign(task,{title:title.trim(),...taskPlan(plan)});return task;}
export function taskLabel(t){return scheduleOf(t)==='recent'?(t.done&&t.completedDate?'近期 · '+t.completedDate+' 完成':'近期'):scheduleOf(t)==='deadline'?`截至 ${t.deadline}${t.deadlineTime?' '+t.deadlineTime:''}`:'';}
export function taskPlan({schedule='day',scheduledDate='',deadline='',deadlineTime=''}){
 if(!['day','recent','deadline'].includes(schedule))throw Error('请选择安排方式');
 const day=v=>{if(!/^\d{4}-\d{2}-\d{2}$/.test(v)||v<'1901-01-01'||v>'2099-12-31'||new Date(v+'T12:00:00Z').toISOString().slice(0,10)!==v)throw Error('请选择有效日期');return v;};
 if(deadlineTime&&!/^([01]\d|2[0-3]):[0-5]\d$/.test(deadlineTime))throw Error('请选择有效截止时间');
 return {schedule,date:schedule==='day'?day(scheduledDate):null,deadline:schedule==='deadline'?day(deadline):null,deadlineTime:schedule==='deadline'?(deadlineTime||null):null};
}
export function toggleTask(t,date){t.done=!t.done;if(scheduleOf(t)!=='day')t.completedDate=t.done?date:null;}
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function taskPlanFields(t={},date=''){
 const mode=scheduleOf(t);
 return `<div class="task-plan-fields"><label>安排方式<select name="schedule" aria-label="任务安排方式">${[['recent','近期完成'],['day','安排到某天'],['deadline','截止日期']].map(([v,n])=>`<option value="${v}" ${mode===v?'selected':''}>${n}</option>`).join('')}</select></label><label data-task-day ${mode==='day'?'':'hidden'}>安排日期<input name="scheduledDate" aria-label="任务安排日期" type="date" min="1901-01-01" max="2099-12-31" value="${esc(t.date||date)}" ${mode==='day'?'required':''}></label><div data-task-deadline ${mode==='deadline'?'':'hidden'}><label>截止日期<input name="deadline" aria-label="任务截止日期" type="date" min="1901-01-01" max="2099-12-31" value="${esc(t.deadline||date)}" ${mode==='deadline'?'required':''}></label><label>时间（可选）<input name="deadlineTime" aria-label="任务截止时间" type="time" value="${esc(t.deadlineTime||'')}"></label></div></div>`;
}
export function updateTaskPlanFields(form){if(!form)return;const mode=form.elements.schedule?.value;if(!mode)return;form.querySelector('[data-task-day]').hidden=mode!=='day';form.querySelector('[data-task-deadline]').hidden=mode!=='deadline';form.elements.scheduledDate.required=mode==='day';form.elements.deadline.required=mode==='deadline';form.elements.scheduledDate.disabled=mode!=='day';form.elements.deadline.disabled=mode!=='deadline';form.elements.deadlineTime.disabled=mode!=='deadline';}
