import {rebaseTimerSave} from './advancement-rebase.js';
export let state,revision,space=sessionStorage.getItem('personal-space')||'main';
export let busy=false;
export async function api(path,body){const r=await fetch(path+(path.includes('?')?'&':'?')+'space='+space,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json','X-Personal-Client':'1'}:{},body:body?JSON.stringify(body):undefined});const data=await r.json();if(!r.ok){const error=new Error(data.error||'无法连接本机服务');error.status=r.status;throw error;}return data;}
export async function load(next=space){if(busy)throw new Error('正在更新，请稍候再切换空间');const old=space;space=next;try{const d=await api('/api/state');state=d.state;revision=d.revision;sessionStorage.setItem('personal-space',space);}catch(e){space=old;throw e;}}
export async function change(fn){
 if(busy)throw new Error('正在保存，请稍候');busy=true;
 try{
  let base=state,next=structuredClone(state),expected=revision;fn(next);
  for(let attempt=0;;attempt++){
   try{const d=await api('/api/state',{revision:expected,state:next});state=d.state||next;revision=d.revision;return d;}
   catch(error){
    if(error.status!==409||attempt>=2)throw error;
    const latest=await api('/api/state'),rebased=rebaseTimerSave(base,next,latest.state);
    if(!rebased)throw error;
    base=latest.state;next=rebased;expected=latest.revision;
   }
  }
 }finally{busy=false;}
}
export async function replace(next){if(busy)throw new Error('正在更新，请稍候');const d=await api('/api/import-backup',{revision,state:next});state=d.state;revision=d.revision;}
export async function restore(id){if(busy)throw new Error('正在更新，请稍候');const d=await api('/api/restore',{revision,id});state=d.state;revision=d.revision;}
export function uid(){return crypto.randomUUID();}

export async function refreshMarket(force=false){
 if(busy)throw new Error('正在保存，请稍候');
 busy=true;
 try{const d=await api('/api/market/refresh',{revision,force});state=d.state;revision=d.revision;return d;}
 catch(error){if(error.status!==409)throw error;const d=await api('/api/state');state=d.state;revision=d.revision;return {...d,refreshed:false,conflict:true};}
 finally{busy=false;}
}

export async function advance(command){
 if(busy)throw new Error('正在保存，请稍候');busy=true;
 try{const d=await api('/api/advancement',command);state=d.state;revision=d.revision;return d;}
 finally{busy=false;}
}

export async function metrics(command){
 if(busy)throw new Error('正在保存，请稍候');busy=true;
 try{const d=await api('/api/daily-metrics',command);state=d.state;revision=d.revision;return d;}
 finally{busy=false;}
}
