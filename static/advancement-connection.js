// Network liveness is independent of background JavaScript interval throttling.
// Only the owning page confirms time; other tabs are read-only observers.
export function timerConnection({active,space,owner,sync,Source=globalThis.EventSource}){
 let source=null,key='';
 function close(){source?.close();source=null;key='';}
 function ensure(){
  const r=active(),next=r?.status==='running'&&r.clockMode==='server'&&r.owner===owner?space()+':'+owner:'';
  if(next===key)return;
  close();if(!next||!Source)return;
  key=next;
  source=new Source(`/api/advancement/watch?space=${encodeURIComponent(space())}&owner=${encodeURIComponent(owner)}`);
  source.onopen=sync;
 }
 return {ensure,close};
}
