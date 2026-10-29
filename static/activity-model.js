// Stable daily projects are independent of problem/solution paths.
export const recordingMode=d=>d?.recordingMode||(d?.name==='健身'||d?.name==='运动'?'activities':'problems');
export const activityRows=(a,domainId)=> (a.activities||[]).filter(x=>x.domainId===domainId&&!x.archived);
export const activityName=(a,id)=> (a.activities||[]).find(x=>x.id===id)?.name||'';
