import {esc,btn} from './ui.js';
import {data,states,planStates,total,format} from './advancement-model.js';
export const folderDomain=(state,id)=>data(state).domains.find(d=>d.folderId===id);
const attr=id=>`data-id="${esc(id)}"`;
export function folderProgress(state,folderId){
 const a=data(state),d=folderDomain(state,folderId);if(!d)return '';
 const problems=a.issues.filter(p=>p.domainId===d.id&&!p.deleted).sort((x,y)=>Number(['open','active'].includes(y.status))-Number(['open','active'].includes(x.status))||y.updatedAt.localeCompare(x.updatedAt));
 const qs=(a.plans||[]).filter(q=>q.domainId===d.id&&!q.deleted),updates=a.updates.filter(u=>u.domainId===d.id).sort((x,y)=>y.date.localeCompare(x.date)||y.createdAt.localeCompare(x.createdAt));
 const problemRows=problems.slice(0,4).map(p=>`<article>${d.archived?`<strong>${esc(p.title)}</strong>`:btn('advance-folder-issue',esc(p.title),'','ghost',attr(p.id))}<small>${states[p.status]}</small>${qs.filter(q=>q.problemId===p.id).slice(0,2).map(q=>`<div class="advance-folder-plan">${d.archived?esc(q.title):btn('advance-folder-issue',esc(q.title),'','ghost small',attr(p.id)+` data-plan="${esc(q.id)}"`)}<small>${planStates[q.status]}</small></div>`).join('')}</article>`).join('');
 const records=updates.slice(0,4).map(u=>{const p=a.issues.find(p=>p.id===u.problemId),q=qs.find(q=>q.id===u.planId);return `<article><time>${esc(u.date)}${q?' · '+esc(q.title):p?' · '+esc(p.title):''}</time><p>${esc(u.body.length>240?u.body.slice(0,240)+'…':u.body)}</p>${!d.archived?btn('advance-folder-progress','查看进展','arrow','ghost small',attr(u.id)):''}</article>`;}).join('');
 return `<section class="advance-folder-section" aria-label="领域推进"><header><div><h2>领域推进${d.archived?' <small>已收起</small>':''}</h2><span>${problems.length} 个问题 · ${qs.length} 个方案 · 累计 ${format(total(state,{domainId:d.id}))}</span></div><div>${btn('advance-folder-stats','时间统计','clock','ghost small',attr(d.id))}${!d.archived?btn('advance-open','进入推进台','arrow','small',attr(d.id)):''}</div></header><div class="advance-folder-columns"><section><h3>问题与方案</h3>${problemRows||'<p class="advance-folder-empty">还没有记录问题。</p>'}</section><section><h3>最近进展</h3>${records||'<p class="advance-folder-empty">推进过程会记录在这里。</p>'}</section></div></section>`;
}
