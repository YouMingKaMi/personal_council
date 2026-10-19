import assert from 'node:assert/strict';
import {cents,emptyExpenses,saveEntry,summary,dayTotal,refunded,removeEntry,restoreEntry,billDate,saveBill,recordBill,csv} from '../static/expenses-model.js';
const s={expenses:emptyExpenses(),treasury:{accounts:[{amount:'100'}]}},now='2026-10-18T00:00:00Z';
const e=(id,amount,date='2026-10-18',extra={})=>({id,title:'午饭',date,amountCents:amount,necessity:'necessary',categoryId:'food',kind:'expense',refundOf:null,subscriptionId:null,billedOccurrence:null,deleted:false,createdAt:now,updatedAt:now,...extra});
assert.equal(cents('0.10')+cents('0.20'),30);
for(const bad of ['-1','0','1e3','Infinity','1.001','1,000','9999999999'])assert.throws(()=>cents(bad));
assert.equal(cents('0',{zero:true}),0);
saveEntry(s,e('a',2000));saveEntry(s,e('b',3000,'2026-10-17',{necessity:'optional',categoryId:'leisure'}));
assert.equal(dayTotal(s,'2026-10-18'),2000);assert.equal(summary(s,'2026-10').total,5000);
saveEntry(s,e('r',500,'2026-11-01',{kind:'refund',refundOf:'a'}));
assert.equal(summary(s,'2026-10').total,5000);assert.equal(summary(s,'2026-11').total,-500);assert.equal(refunded(s,'a'),500);
assert.throws(()=>saveEntry(s,e('r2',1600,'2026-11-02',{kind:'refund',refundOf:'a'})));
assert.throws(()=>saveEntry(s,e('r2',500,'2026-09-02',{kind:'refund',refundOf:'a'})));
assert.throws(()=>saveEntry(s,e('a',400)));assert.throws(()=>removeEntry(s,'a'));
saveEntry(s,e('a',2100,'2026-10-18',{categoryId:'tools',necessity:'optional'}));
assert.equal(s.expenses.entries.find(e=>e.id==='r').categoryId,'tools');
removeEntry(s,'r');removeEntry(s,'a');assert.equal(summary(s,'2026-10').total,3000);
assert.throws(()=>restoreEntry(s,'r'));restoreEntry(s,'a');restoreEntry(s,'r');assert.equal(summary(s,'2026-11').total,-500);
const bill={id:'bill',title:'VPS',amountCents:3500,categoryId:'tools',necessity:'necessary',cycle:'monthly',anchorDate:'2026-01-31',nextIndex:0,enabled:true,deleted:false};
saveBill(s,bill);assert.equal(billDate(bill),'2026-01-31');assert.equal(billDate({...bill,nextIndex:1}),'2026-02-28');assert.equal(billDate({...bill,nextIndex:2}),'2026-03-31');assert.equal(billDate({...bill,cycle:'yearly',anchorDate:'2024-02-29',nextIndex:1}),'2025-02-28');
assert.equal(summary(s,'2026-01').total,0); // scheduled bills do not count as paid
recordBill(s,'bill',e('paid',3600,'2026-02-01',{billedOccurrence:'2026-01-31'}));
assert.equal(summary(s,'2026-02').total,3600);assert.equal(billDate(bill),'2026-02-28');
assert.throws(()=>recordBill(s,'bill',e('dup',3600,'2026-02-01',{billedOccurrence:'2026-01-31'})));
assert.equal(s.treasury.accounts[0].amount,'100');
saveEntry(s,e('csv',10,'2026-10-18',{title:'=HYPERLINK("x")'}));assert.match(csv(s,'2026-10'),/'=HYPERLINK/);
console.log('expense cents, month boundaries, refunds, updates, removal/restore, recurring payments, duplicate guard and treasury isolation passed');

// Descendant filters and sibling breakdowns must never double-count leaf entries.
const {categoryPath,categoryLabel,categoryMatches,categoryActive,saveCategory,monthlyTrend}=await import('../static/expenses-model.js');
const tree={expenses:emptyExpenses()};
assert.deepEqual(tree.expenses.categories.filter(c=>c.parentId).map(c=>c.name),['咖啡','正餐']);
saveCategory(tree,{id:'food-breakfast',name:'早餐',parentId:'food-meals'}); // Custom nesting remains supported, without preset meal periods.
saveEntry(tree,e('coffee',1800,'2026-10-19',{categoryId:'food-coffee'}));
saveEntry(tree,e('breakfast',800,'2026-10-18',{categoryId:'food-breakfast'}));
saveEntry(tree,e('unsplit',1000,'2026-10-18'));
saveEntry(tree,e('lastcoffee',1600,'2026-09-05',{categoryId:'food-coffee'}));
assert.equal(categoryLabel(tree,'food-breakfast'),'餐饮 / 正餐 / 早餐');
assert.equal(categoryMatches(tree,'food-breakfast','food'),true);
assert.equal(summary(tree,'2026-10',{categoryId:'food'}).total,3600);
assert.equal(summary(tree,'2026-10',{categoryId:'food-meals'}).total,800);
assert.equal(summary(tree,'2026-10',{categoryId:'food-coffee'}).total,1800);
assert.equal(summary(tree,'2026-10').categories.reduce((n,c)=>n+c.total,0),3600);
assert.equal(summary(tree,'2026-10',{categoryId:'food'}).categories.reduce((n,c)=>n+c.total,0),3600);
assert.equal(tree.expenses.entries.find(e=>e.id==='unsplit').categoryId,'food');
const trend=monthlyTrend(tree,'2026-10',6,{categoryId:'food-coffee'});
assert.equal(trend.length,6);assert.equal(trend[0].count,0);assert.equal(trend.at(-2).total,1600);assert.equal(trend.at(-1).total,1800);
saveEntry(tree,e('refundcoffee',300,'2026-11-01',{kind:'refund',refundOf:'coffee'}));
assert.equal(summary(tree,'2026-11',{categoryId:'food-coffee'}).total,-300);
saveCategory(tree,{id:'custom',name:'下午茶',parentId:'food'});assert.equal(categoryPath(tree,'custom').length,2);
assert.throws(()=>saveCategory(tree,{id:'duplicate',name:'下午茶',parentId:'food'}));
saveCategory(tree,{id:'other-tea',name:'下午茶',parentId:'leisure'}); // Names may repeat in different branches.
tree.expenses.categories.find(c=>c.id==='food-meals').archived=true;
assert.equal(categoryActive(tree,'food-breakfast'),false);
assert.equal(summary(tree,'2026-10',{categoryId:'food-meals'}).total,800);
assert.match(csv(tree,'2026-10'),/餐饮 \/ 正餐 \/ 早餐/);
console.log('Optional category hierarchy, parent aggregation, unsplit history, monthly comparisons, refunds and archived history passed');
