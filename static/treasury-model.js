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
