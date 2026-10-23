import {ordered} from './order-model.js';
// Presentation selectors reuse stable folder/note identities; no migration or copying.
export function trail(s,id){const result=[],seen=new Set();let f=s.folders.find(x=>x.id===id);while(f&&!seen.has(f.id)){result.unshift(f);seen.add(f.id);f=s.folders.find(x=>x.id===f.parent);}return result;}
export function subtree(s,id){const ids=new Set([id]);for(let i=0;i<s.folders.length;i++)for(const f of s.folders)if(ids.has(f.parent))ids.add(f.id);return ids;}
export function notesIn(s,id){const ids=subtree(s,id);return s.notes.filter(n=>ids.has(n.folder)&&!n.trashed&&!n.readOnlyArchive);}
export function reflectionRoot(s,id){return trail(s,id).find(f=>f.module==='reflection'||f.name==='个人思考')||null;}
export function isProject(s,f){return !!f&&(f.module==='project'||(['RAG Knowledge','Deep Research'].includes(f.name)&&trail(s,f.parent).some(p=>p.name==='编程')));}
export function projectRoot(s,id){return trail(s,id).find(f=>isProject(s,f))||null;}
export function projects(s){return ordered(s,'projects',s.folders.filter(f=>isProject(s,f)));}
export const isLogFolder=f=>f?.module==='project-log'||/^(?:daily[ _-]?logs?|logs?|日志|项目日志)$/i.test(f?.name||'');
export function projectData(s,id){const root=projectRoot(s,id);if(!root)return null;const ids=subtree(s,root.id),folders=s.folders.filter(f=>ids.has(f.id)),logRoots=folders.filter(isLogFolder),logIds=new Set(logRoots.flatMap(f=>[...subtree(s,f.id)])),all=notesIn(s,root.id),logs=all.filter(n=>logIds.has(n.folder)).sort((a,b)=>b.date.localeCompare(a.date)||a.title.localeCompare(b.title)),resources=all.filter(n=>!logIds.has(n.folder)).sort((a,b)=>b.date.localeCompare(a.date)||a.title.localeCompare(b.title));return {root,folders,logRoots,logIds,logs,resources};}
export function departmentGroups(s){const roots=s.folders.filter(f=>!f.parent),pinnedRoots=new Set((s.pins||[]).map(id=>trail(s,id)[0]?.id)),active=f=>pinnedRoots.has(f.id)||notesIn(s,f.id).length||s.folders.some(x=>subtree(s,f.id).has(x.id)&&['habits','tasks','chronicle','monthly','treasury','expenses','ideas'].includes(x.module));return {all:roots,common:roots.filter(active).sort((a,b)=>Number(pinnedRoots.has(b.id))-Number(pinnedRoots.has(a.id))||notesIn(s,b.id).length-notesIn(s,a.id).length)};}
export function makeLog(s,projectId,date,text,id,now){
 const p=projectData(s,projectId);if(!p)throw new Error('项目不存在');if(!/^\d{4}-\d{2}-\d{2}$/.test(date)||new Date(date+'T12:00:00Z').toISOString().slice(0,10)!==date)throw new Error('请选择有效日期');if(!text.trim())throw new Error('请写下实际的项目记录');
 if(p.logs.some(n=>n.date===date))throw new Error('这一天已有日志，请编辑已有日志，避免覆盖');
 const folder=p.logRoots[0]||{id:id+'-logs',name:'项目日志',parent:p.root.id,icon:'book',description:'',fields:[],experimental:false,module:'project-log'};
 return {folder:p.logRoots.length?null:folder,note:{id,folder:folder.id,title:date,date,dateBasis:'记录日期',body:text.trim(),tags:[],values:{},status:'done',createdAt:now,updatedAt:now}};
}
export function filterReflection(s,root,{section='',tag='',untagged=false,query=''}={}){return notesIn(s,section||root).filter(n=>(!tag||n.tags.includes(tag))&&(!untagged||!n.tags.length)&&(!query||(n.title+' '+n.body).toLowerCase().includes(query.toLowerCase()))).sort((a,b)=>b.date.localeCompare(a.date)||a.title.localeCompare(b.title));}
