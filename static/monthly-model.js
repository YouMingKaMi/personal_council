// Reporting month is explicit; modification and writing dates never sort reports.
export const validMonth=m=>typeof m==='string'&&/^[1-9]\d{3}-(0[1-9]|1[0-2])$/.test(m);
export function monthlyRoot(s,folder){let f=s.folders.find(f=>f.id===folder),seen=new Set();while(f&&!seen.has(f.id)){if(f.module==='monthly'||f.name==='月报')return f;seen.add(f.id);f=s.folders.find(x=>x.id===f.parent);}return null;}
export function reportMonth(s,n){
 if(validMonth(n.period))return n.period;
 const full=(n.source+'/'+n.title).match(/(?:^|[^\d])([1-9]\d{3})[-年/](0?[1-9]|1[0-2])(?:月|[-/：:\s]|$)/);
 if(full)return `${full[1]}-${full[2].padStart(2,'0')}`;
 const month=n.title.match(/^\s*(0?[1-9]|1[0-2])月/);let year=n.source?.match(/(?:^|\/)([1-9]\d{3})(?:\/|$)/)?.[1],f=s.folders.find(f=>f.id===n.folder),seen=new Set();
 while(!year&&f&&!seen.has(f.id)){seen.add(f.id);if(/^[1-9]\d{3}$/.test(f.name))year=f.name;f=s.folders.find(x=>x.id===f.parent);}
 if(month&&year)return `${year}-${month[1].padStart(2,'0')}`;
 return n.dateBasis==='月份归档'?n.date.slice(0,7):null;
}
export function monthlyNotes(s){return s.notes.filter(n=>!n.trashed&&monthlyRoot(s,n.folder)).sort((a,b)=>(reportMonth(s,b)||'').localeCompare(reportMonth(s,a)||'')||a.id.localeCompare(b.id));}
export function reportFor(s,month,except){return monthlyNotes(s).find(n=>n.id!==except&&reportMonth(s,n)===month);}
export function reportDone(n){return !!n&&(n.status==='done'||n.status==='imported')&&!!n.body.trim();}
export function monthLabel(m){return validMonth(m)?`${Number(m.slice(0,4))}年${Number(m.slice(5))}月`:'待设置月份';}
export function previousMonth(m){let [y,n]=m.split('-').map(Number);return `${n===1?y-1:y}-${String(n===1?12:n-1).padStart(2,'0')}`;}
export function makeReport(s,month,id,now){
 if(!validMonth(month))throw new Error('请选择有效的月报月份');
 if(reportFor(s,month))throw new Error('这个月份已有月报，请继续已有记录');
 const folder=s.folders.find(f=>f.module==='monthly'||f.name==='月报');if(!folder)throw new Error('月报空间不存在');
 const rule=s.rules.find(r=>r.folder===folder.id&&r.frequency==='monthly'),tpl=s.templates.find(t=>t.folder===folder.id);
 return {id,folder:folder.id,title:monthLabel(month)+' · 月报',date:month+'-01',dateBasis:'月报所属月份',period:month,...(rule?{ruleId:rule.id}:{}),body:tpl?.body||'',templateBody:tpl?.body||'',tags:[],values:{},status:'draft',createdAt:now,updatedAt:now};
}
