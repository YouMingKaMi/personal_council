// Keep one shared, sortable list. Half-width panels fill the shortest column;
// a wide panel starts below both columns and forms a boundary for the next group.
let disconnect=()=>{};
export function layoutDashboard(container){
 disconnect();disconnect=()=>{};
 if(!container)return;
 let frame=0,stopped=false;
 const cards=()=>[...container.children].filter(el=>el.hasAttribute('data-panel'));
 function layout(){
  if(stopped||!container.isConnected)return;
  const style=getComputedStyle(container),columns=style.gridTemplateColumns.split(/\s+/).length>1?2:1;
  const width=container.clientWidth,gapX=parseFloat(style.columnGap)||0,gapY=parseFloat(style.rowGap)||0;
  if(!width)return;
  const half=(width-gapX*(columns-1))/columns,bottoms=Array(columns).fill(0);
  for(const card of cards()){
   const wide=columns===1||card.classList.contains('wide'),cardWidth=wide?width:half;
   const desiredWidth=cardWidth+'px';if(card.style.width!==desiredWidth)card.style.width=desiredWidth;
   const column=wide?0:bottoms.indexOf(Math.min(...bottoms)),top=wide?Math.max(...bottoms):bottoms[column];
   const left=(half+gapX)*column;
   if(card.style.left!==left+'px')card.style.left=left+'px';
   if(card.style.top!==top+'px')card.style.top=top+'px';
   const next=top+card.offsetHeight+gapY;
   if(wide)bottoms.fill(next);else bottoms[column]=next;
  }
  const height=cards().length?Math.max(...bottoms)-gapY:0;
  if(container.style.height!==height+'px')container.style.height=height+'px';
 }
 function schedule(){if(stopped||frame)return;frame=requestAnimationFrame(()=>{frame=0;layout();});}
 container.classList.add('packed');
 layout();
 const resize=new ResizeObserver(schedule);resize.observe(container);cards().forEach(c=>resize.observe(c));
 const mutations=new MutationObserver(()=>{resize.disconnect();resize.observe(container);cards().forEach(c=>resize.observe(c));schedule();});
 mutations.observe(container,{childList:true});
 container.addEventListener('cards-reflow',layout);
 window.addEventListener('resize',schedule);
 disconnect=()=>{stopped=true;cancelAnimationFrame(frame);resize.disconnect();mutations.disconnect();container.removeEventListener('cards-reflow',layout);window.removeEventListener('resize',schedule);};
}
