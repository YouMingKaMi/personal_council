// Retry only an automatic lastSeen checkpoint, never a competing user edit.
export function rebaseTimerSave(base,next,latest){
 const r=base?.advancement?.active,q=latest?.advancement?.active;
 if(r?.clockMode!=='server'||r.status!=='running'||q?.status!=='running'||q.id!==r.id||q.lastSeen<r.lastSeen)return null;
 if(JSON.stringify(next.advancement?.active)!==JSON.stringify(r))return null;
 const business=s=>JSON.stringify({...s,advancement:{...s.advancement,active:{...s.advancement.active,lastSeen:null}}});
 if(business(base)!==business(latest))return null;
 return {...next,advancement:{...next.advancement,active:{...q}}};
}
