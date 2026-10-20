// Decimal quantities and prices use fixed point integers; persisted values remain strings.
export const SCALE=10n**12n;
export const categories={cash:'人民币',crypto:'加密资产',investment:'外部投资',other:'股票'};
export function decimal(value){if(typeof value!=='string'||!/^(0|[1-9]\d{0,14})(\.\d{1,12})?$/.test(value))throw new Error('请输入非负数字，最多 12 位小数；不要输入逗号或科学计数法');const [a,b='']=value.split('.');return BigInt(a)*SCALE+BigInt(b.padEnd(12,'0'));}
export function quantity(value){const negative=value<0n;if(negative)value=-value;const tail=(value%SCALE).toString().padStart(12,'0').replace(/0+$/,'');return (negative?'-':'')+(value/SCALE).toString()+(tail?'.'+tail:'');}
export function money(value){if(value===null||value===undefined)return '—';const neg=value<0n;if(neg)value=-value;const cents=(value*100n+SCALE/2n)/SCALE;return (neg?'−':'')+'¥'+(cents/100n).toString().replace(/\B(?=(\d{3})+(?!\d))/g,',')+'.'+(cents%100n).toString().padStart(2,'0');}
export function signedMoney(value){return value===null?'待补齐估值':(value>0n?'+':'')+money(value);}
export function activeAccounts(p,id){return p.accounts.filter(a=>a.assetId===id&&!a.archived);}
export function assetValue(p,a){const accounts=activeAccounts(p,a.id),filled=accounts.filter(x=>x.amount!==null),amount=filled.reduce((sum,x)=>sum+decimal(x.amount),0n);const missingBalances=accounts.length?accounts.length-filled.length:1;const price=pricing(p,a).cny;const known=filled.length>0;const value=known&&(price!==null||amount===0n)?(amount*(price??0n)+SCALE/2n)/SCALE:null;return {accounts,amount,known,price,value,missing:missingBalances+(known&&amount>0n&&price===null?1:0),complete:missingBalances===0&&value!==null};}
export function total(p,category=null){const assets=p.assets.filter(a=>!a.archived&&(!category||(category==='controlled'?a.category!=='investment':a.category===category)));const rows=assets.map(a=>assetValue(p,a)),known=rows.filter(r=>r.value!==null);return {value:known.length?known.reduce((sum,r)=>sum+r.value,0n):assets.length?null:0n,missing:rows.filter(r=>!r.complete).length,assets:assets.length,complete:rows.every(r=>r.complete)};}
export function delta(before,after,category=null){const a=total(before,category),b=total(after,category);return a.complete&&b.complete?b.value-a.value:null;}
export function portfolio(t){return structuredClone({assets:t.assets,accounts:t.accounts,...(t.market?{market:t.market}:{})});}
export function recordChange(t,fn,label,id,at){const before=portfolio(t);fn(t);t.changes.push({id,at,label,before,after:portfolio(t)});if(t.changes.length>200)t.changes.splice(0,t.changes.length-200);}
export function capture(t,{id,date,label,note,createdAt}){if(!t.accounts.some(a=>!a.archived&&a.amount!==null))throw new Error('请先填写至少一个账户余额，再保存盘点');t.snapshots.push({id,date,label,note,createdAt,portfolio:portfolio(t)});}
export function snapshots(t){return [...t.snapshots].sort((a,b)=>b.date.localeCompare(a.date)||b.createdAt.localeCompare(a.createdAt));}
export function previousSnapshot(t,id){const list=snapshots(t),index=list.findIndex(s=>s.id===id);return index<0?null:list[index+1]||null;}
export function canArchive(p,id){return activeAccounts(p,id).every(a=>a.amount===null||decimal(a.amount)===0n);}

export function lastAssetChange(t,id){const slice=p=>JSON.stringify({asset:p.assets.find(a=>a.id===id),price:p.assets.find(a=>a.id===id)?pricing(p,p.assets.find(a=>a.id===id)).cny?.toString():null,accounts:p.accounts.filter(a=>a.assetId===id)});return [...t.changes].reverse().find(c=>slice(c.before)!==slice(c.after))||null;}

export const coinIds={BTC:'bitcoin',ETH:'ethereum',USDC:'usd-coin',USDT:'tether',SOL:'solana',DOGE:'dogecoin'};
export function pricing(p,a){
 const q=p.market?.prices?.[a.quoteId],fx=p.market?.fx?.USD;
 if(a.category==='crypto'&&a.pricingMode==='auto'&&q&&fx)return {cny:(decimal(q.usd)*decimal(fx.rate)+SCALE/2n)/SCALE,usd:decimal(q.usd),at:q.at,date:new Date(q.at).toLocaleDateString('sv-SE',{timeZone:'Asia/Shanghai'}),fx,automatic:true};
 return {cny:['cash','investment'].includes(a.category)?SCALE:a.priceCny===null?null:decimal(a.priceCny),usd:null,date:a.priceDate,automatic:false,fallback:a.pricingMode==='auto'};
}
export function dollars(value){return value===null?'—':value>=SCALE?money(value).replace('¥','$')+' USD':'$'+quantity(((value+5000n)/10000n)*10000n)+' USD';}

// Value the held quantity in USD, independently of whether CNY FX is available.
export function assetValueUsd(p,a){
 const accounts=activeAccounts(p,a.id),filled=accounts.filter(r=>r.amount!==null),amount=filled.reduce((sum,r)=>sum+decimal(r.amount),0n);
 const q=a.pricingMode==='auto'?p.market?.prices?.[a.quoteId]:null,fx=p.market?.fx?.USD;
 const converted=!q&&a.priceCny!==null&&!!fx;
 const price=q?decimal(q.usd):converted?(decimal(a.priceCny)*SCALE+decimal(fx.rate)/2n)/decimal(fx.rate):null;
 const value=filled.length&&(price!==null||amount===0n)?(amount*(price??0n)+SCALE/2n)/SCALE:null;
 return {value,converted,complete:accounts.length>0&&filled.length===accounts.length&&value!==null};
}
export function totalUsd(p){
 const assets=p.assets.filter(a=>a.category==='crypto'&&!a.archived),rows=assets.map(a=>assetValueUsd(p,a)),known=rows.filter(r=>r.value!==null);
 return {value:known.length?known.reduce((sum,r)=>sum+r.value,0n):assets.length?null:0n,assets:assets.length,missing:rows.filter(r=>!r.complete).length,converted:rows.some(r=>r.converted)};
}

// Apply exact quantity deltas to a known balance, never infer an unknown balance as zero.
export function adjustAccount(t,id,direction,input,at){
 const r=t.accounts.find(r=>r.id===id),a=t.assets.find(a=>a.id===r?.assetId);
 if(!r||!a||r.archived||a.archived)throw Error('请先恢复这个账户及其资产');
 if(r.amount===null)throw Error('请先填写当前余额，再记录增减');
 if(!['add','subtract'].includes(direction))throw Error('请选择增加或减少');
 const amount=decimal(input);if(amount<=0n)throw Error('增减数额必须大于零');
 const before=decimal(r.amount),next=before+(direction==='add'?amount:-amount);
 if(next<0n)throw Error('减少数额不能超过当前余额');
 const result=quantity(next);decimal(result);r.amount=result;r.updatedAt=at;
 return {before:quantity(before),after:result,amount:quantity(amount),unit:a.unit};
}
export function scopedValue(p,scope={kind:'total'}){
 if(scope.kind==='total'||scope.kind==='category'){const v=total(p,scope.kind==='category'?scope.id:null);return {value:v.complete?v.value:null,partial:v.value,complete:v.complete,amount:null};}
 const a=scope.kind==='asset'?p.assets.find(a=>a.id===scope.id):p.assets.find(a=>a.id===p.accounts.find(r=>r.id===scope.id)?.assetId);
 if(!a)return {value:null,complete:false,amount:null};
 if(scope.kind==='asset'){const v=assetValue(p,a);return {value:v.complete?v.value:null,complete:v.complete,amount:v.known?v.amount:null};}
 const r=p.accounts.find(r=>r.id===scope.id);if(!r||r.amount===null)return {value:null,complete:false,amount:null};
 const amount=decimal(r.amount),price=pricing(p,a).cny,value=price!==null||amount===0n?(amount*(price??0n)+SCALE/2n)/SCALE:null;
 return {value,complete:value!==null,amount};
}
export function treasuryTrend(t,scope={kind:'total'},{from=null,to=new Date().toISOString()}={}){
 const end=Date.parse(to),start=from?Date.parse(from):-Infinity,points=[];
 const add=(at,p,label,id)=>{const time=Date.parse(at);if(!Number.isFinite(time)||time>end)return;const v=scopedValue(p,scope);points.push({at,time,label,id,...v});};
 const changes=[...t.changes].filter(c=>Number.isFinite(Date.parse(c.at))).sort((a,b)=>Date.parse(a.at)-Date.parse(b.at));
 // A before point has no inferred earlier date: it is the balance immediately before the first retained change.
 if(changes.length)add(changes[0].at,changes[0].before,'最早保留变更 · 修改前','before');
 for(const c of changes)add(c.at,c.after,c.label,c.id);
 for(const s of t.snapshots){const day=new Date(s.createdAt).toLocaleDateString('sv-SE',{timeZone:'Asia/Shanghai'});add(day===s.date?s.createdAt:s.date+'T12:00:00+08:00',s.portfolio,'盘点：'+s.label,s.id);}
 add(to,t,'当前记录','current');points.sort((a,b)=>a.time-b.time);
 // Remove unchanged values but keep gaps for unfilled balances/prices.
 const filtered=points.filter(p=>p.time>=start),out=[];
 for(const p of filtered){const prev=out.at(-1);if(prev&&prev.value===p.value&&prev.amount===p.amount&&p.id!=='current'&&prev.id!=='before')continue;out.push(p);}
 return out;
}
