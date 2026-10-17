import {esc,icon} from './ui.js';
export function pageMenu(content,label='更多页面操作'){return `<details class="page-menu"><summary aria-label="${esc(label)}" title="${esc(label)}">${icon('more')}</summary><div class="page-menu-panel" role="group" aria-label="${esc(label)}">${content}</div></details>`;}
export function installPageMenus(){
 const close=except=>document.querySelectorAll('.page-menu[open]').forEach(m=>{if(m!==except)m.open=false;});
 document.addEventListener('click',e=>{const m=e.target.closest('.page-menu');close(m);if(m&&e.target.closest('[data-action]'))m.open=false;});
 document.addEventListener('keydown',e=>{const m=e.target.closest('.page-menu');if(e.key==='Escape'){const open=document.querySelector('.page-menu[open]');if(open){e.preventDefault();close();open.querySelector('summary').focus();}return;}if(!m||!['ArrowDown','ArrowUp','Home','End'].includes(e.key))return;e.preventDefault();m.open=true;close(m);const all=[...m.querySelectorAll('button')],i=all.indexOf(document.activeElement);all[e.key==='Home'?0:e.key==='End'?all.length-1:(i+(e.key==='ArrowUp'?-1:1)+all.length)%all.length]?.focus();});
}
