// Inclusive civil dates; whole fen are distributed by cumulative rounding.
const DAY=86400000;
export const allocationToday=()=>new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const prefix=(net,index,days)=>{const v=BigInt(net)*BigInt(index),d=BigInt(days);return Number(v<0n?(v-d+1n)/d:v/d);};
export function civil(d){if(!/^\d{4}-\d{2}-\d{2}$/.test(d)||d<'1901-01-01'||d>'2099-12-31')throw Error('使用日期无效');const n=Date.parse(d+'T00:00:00Z');if(!Number.isFinite(n)||new Date(n).toISOString().slice(0,10)!==d)throw Error('使用日期无效');return n/DAY;}
export function expectedEnd(start,months){civil(start);if(!Number.isInteger(months)||months<1||months>1200)throw Error('预计使用月数须为 1—1200');const [y,m,d]=start.split('-').map(Number),anchor=new Date(Date.UTC(y,m-1+months,1)),last=new Date(Date.UTC(anchor.getUTCFullYear(),anchor.getUTCMonth()+1,0)).getUTCDate();anchor.setUTCDate(Math.min(d,last));const end=new Date(anchor.getTime()-DAY).toISOString().slice(0,10);civil(end);return end;}
export function validateAllocation(a,purchaseDate){if(a==null)return null;if(typeof a!=='object'||Array.isArray(a)||Object.keys(a).some(k=>!['startDate','expectedEndDate','endDate','resaleCents','resaleDate'].includes(k)))throw Error('长期使用设置无效');const start=civil(a.startDate);if(civil(a.expectedEndDate)<start||purchaseDate&&a.startDate<purchaseDate)throw Error('请检查付款、开始使用和预计结束日期');if(a.endDate!=null&&civil(a.endDate)<start)throw Error('实际结束不能早于开始使用');if(!Number.isSafeInteger(a.resaleCents??0)||(a.resaleCents??0)<0||(a.resaleCents??0)>99999999999||!a.endDate&&a.resaleCents)throw Error('请检查实际结束日期和回收金额');if(a.resaleDate!=null){civil(a.resaleDate);if(!a.endDate||!a.resaleCents||purchaseDate&&a.resaleDate<purchaseDate)throw Error('请检查回收款到账日期');}return a;}
export function usageInfo(entry,entries){const a=validateAllocation(entry.allocation,entry.date);if(!a)return null;const refunds=entries.filter(r=>!r.deleted&&r.kind==='refund'&&r.refundOf===entry.id).reduce((n,r)=>n+r.amountCents,0),end=a.endDate||a.expectedEndDate,days=civil(end)-civil(a.startDate)+1,net=entry.amountCents-refunds-(a.endDate?a.resaleCents||0:0);return {start:a.startDate,end,days,net,daily:net/days,settled:!!a.endDate,refunds,resale:a.resaleCents||0};}
// Actual elapsed ownership days, not the estimated lifetime or selected month.
export function usageToDate(entry,entries,asOf=allocationToday()){
 const a=validateAllocation(entry.allocation,entry.date);if(!a)return null;
 const through=a.endDate&&a.endDate<=asOf?a.endDate:asOf;
 const days=Math.max(0,civil(through)-civil(a.startDate)+1);
 const refunds=entries.filter(r=>!r.deleted&&r.kind==='refund'&&r.refundOf===entry.id&&r.date<=asOf).reduce((n,r)=>n+r.amountCents,0);
 const settled=!!a.endDate&&a.endDate<=asOf,net=entry.amountCents-refunds-(settled?a.resaleCents||0:0);
 return {days,through,net,daily:days?net/days:null,settled};
}

export function resaleRows(entries){return entries.filter(e=>!e.deleted&&e.kind==='expense'&&e.allocation?.endDate&&e.allocation.resaleCents>0).map(e=>({...e,id:'resale-'+e.id,date:e.allocation.resaleDate||e.allocation.endDate,title:e.title+' · 回收款',amountCents:e.allocation.resaleCents,kind:'refund',refundOf:e.id,allocation:null,virtual:true,isResale:true}));}
export function allocatedRows(entries,month){
 if(!/^\d{4}-(0[1-9]|1[0-2])$/.test(month))throw Error('分摊统计需要有效月份');
 const original=new Map(entries.map(e=>[e.id,e])),rows=entries.filter(e=>!e.deleted&&!e.allocation&&!(e.kind==='refund'&&original.get(e.refundOf)?.allocation)&&e.date.startsWith(month));
 const [y,m]=month.split('-').map(Number),lo=Date.UTC(y,m-1,1)/DAY,hi=Date.UTC(y,m,1)/DAY;
 for(const e of entries){if(e.deleted||e.kind!=='expense'||!e.allocation)continue;const u=usageInfo(e,entries),start=civil(u.start),end=civil(u.end)+1;
  for(let day=Math.max(lo,start);day<Math.min(hi,end);day++){
   const i=day-start,amount=prefix(u.net,i+1,u.days)-prefix(u.net,i,u.days);
   rows.push({...e,id:e.id+':'+day,date:new Date(day*DAY).toISOString().slice(0,10),title:e.title+' · 分摊',amountCents:Math.abs(amount),kind:amount<0?'refund':'expense',virtual:true,allocated:true});
  }
 }
 return rows;
}
