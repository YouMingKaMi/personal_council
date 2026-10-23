// Ideas are ordinary notes: the existing database, trash and backups retain them.
export const ideasRoot=s=>s.folders.find(f=>f.module==='ideas')||null;
export function ensureIdeasSpace(s,uid){
 if(ideasRoot(s))return ideasRoot(s);
 let parent=s.folders.find(f=>f.name==='执行部'&&!f.parent);
 if(!parent){parent={id:uid(),name:'执行部',parent:null,icon:'folder',fields:[],description:'',experimental:false};s.folders.push(parent);}
 const folder={id:uid(),name:'想法暂存',parent:parent.id,module:'ideas',icon:'spark',fields:[],description:'',experimental:false};
 s.folders.push(folder);return folder;
}
export function ideaNotes(s,root,{trash=false}={}){
 return s.notes.filter(n=>n.folder===root&&!n.readOnlyArchive&&!!n.trashed===trash)
  .sort((a,b)=>b.date.localeCompare(a.date)||(a.createdAt||'').localeCompare(b.createdAt||'')||a.id.localeCompare(b.id));
}
function validBody(body){if(typeof body!=='string'||!body.trim())throw Error('先写下一点想法');if(body.length>100000)throw Error('内容过长，请分成几条保存');}
function title(body){return body.split('\n').find(line=>line.trim())?.trim().slice(0,80)||'想法';}
function editable(s,root,id){const n=s.notes.find(n=>n.id===id&&n.folder===root&&!n.readOnlyArchive);if(!n)throw Error('这条想法不存在');return n;}
export function addIdea(s,{id,folder,date,body,now}){
 if(!s.folders.some(f=>f.id===folder&&f.module==='ideas'))throw Error('找不到想法暂存空间');
 validBody(body);
 if(!/^\d{4}-\d{2}-\d{2}$/.test(date)||new Date(date+'T12:00:00Z').toISOString().slice(0,10)!==date)throw Error('记录日期无效');
 if(s.notes.some(n=>n.id===id))throw Error('记录标识重复');
 const note={id,folder,date,title:title(body),body,tags:[],values:{},status:'done',createdAt:now,updatedAt:now,dateBasis:'记录日期'};
 s.notes.push(note);return note;
}
export function editIdea(s,root,id,body,now){validBody(body);const n=editable(s,root,id);if(n.trashed)throw Error('请先恢复这条想法');n.body=body;n.title=title(body);n.updatedAt=now;}
export function trashIdea(s,root,id,trashed,now){const n=editable(s,root,id);n.trashed=trashed;n.updatedAt=now;}
