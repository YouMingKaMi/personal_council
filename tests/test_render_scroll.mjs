import assert from 'node:assert/strict';
import {preserveScroll,createScrollRenderer} from '../static/render-scroll.js';
function viewport(x=0,y=0,max=4000){return{scrollX:x,scrollY:y,max,calls:[],scrollTo(value){this.calls.push(value);this.scrollX=value.left;this.scrollY=Math.max(0,Math.min(this.max,value.top));}};}
const page=viewport(8,1700);
const result=preserveScroll(page,()=>{page.scrollY=0;return 'saved';});
assert.equal(result,'saved');assert.equal(page.scrollY,1700);assert.equal(page.scrollX,8);
assert.deepEqual(page.calls,[{left:8,top:1700,behavior:'instant'}]);
// A save may be in flight while the reader moves elsewhere. Snapshot when
// redraw actually starts, not when an asynchronous save was requested.
page.scrollY=2200;preserveScroll(page,()=>{page.scrollY=0;});assert.equal(page.scrollY,2200);
// Real shorter content must respect the new bottom instead of inventing space.
page.scrollY=2200;preserveScroll(page,()=>{page.max=1400;page.scrollY=0;});assert.equal(page.scrollY,1400);
const error=new Error('render failed');page.scrollY=900;
assert.throws(()=>preserveScroll(page,()=>{page.scrollY=0;throw error;}),e=>e===error);
assert.equal(page.scrollY,900);
const top=viewport();preserveScroll(top,()=>{});assert.equal(top.scrollY,0);
// Explicit route navigation wins immediately. There is no queued scroll reset.
preserveScroll(page,()=>{page.scrollY=0;});page.scrollTo({left:0,top:0});
await Promise.resolve();assert.equal(page.scrollY,0);
console.log('Render scroll: transient height collapse, actual redraw position, shorter pages, failures and explicit navigation passed.');

const routePage=viewport(0,1600),render=createScrollRenderer(routePage);
render('main:today',()=>{});assert.equal(routePage.scrollY,0);
routePage.scrollY=1800;render('main:today',()=>{routePage.scrollY=0;});assert.equal(routePage.scrollY,1800);
render('main:note:new-note',()=>{});assert.equal(routePage.scrollY,0);
routePage.scrollY=750;render('main:note:new-note',()=>{routePage.scrollY=0;});assert.equal(routePage.scrollY,750);
render('main:note:other-note',()=>{});assert.equal(routePage.scrollY,0);
routePage.scrollY=600;render('lab:note:other-note',()=>{});assert.equal(routePage.scrollY,0);
console.log('Render identity: in-place saves preserve position, new pages/articles/spaces start at top.');
