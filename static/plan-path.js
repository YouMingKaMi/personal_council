// Additive path metadata: old flat plans remain root solutions.
export function planChain(rows,id){
 const byId=new Map(rows.map(q=>[q.id,q])),seen=new Set(),path=[];
 while(id&&!seen.has(id)&&path.length<12){seen.add(id);const q=byId.get(id);if(!q)break;path.unshift(q);id=q.parentId;}
 return path;
}
export const planLabel=(rows,id)=>planChain(rows,id).map(q=>q.title).join(' / ');
export const planAvailable=(rows,id)=>planChain(rows,id).every(q=>!q.deleted&&!['done','parked','abandoned'].includes(q.status));
export const inPlanBranch=(rows,id,parentId)=>planChain(rows,id).some(q=>q.id===parentId);
export function planTree(rows){
 const result=[],seen=new Set(),byId=new Set(rows.map(q=>q.id));
 function visit(q,depth){if(seen.has(q.id))return;seen.add(q.id);result.push({...q,depth});for(const child of rows.filter(c=>c.parentId===q.id))visit(child,depth+1);}
 for(const q of rows.filter(q=>!q.parentId||!byId.has(q.parentId)))visit(q,0);
 for(const q of rows)visit(q,0);
 return result;
}
