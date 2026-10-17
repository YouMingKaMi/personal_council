// Stable insertion slots captured at lift. A small deadband avoids boundary chatter.
export function sortTarget(slots,x,y,current,hysteresis=12){
 if(!slots.length)return current;
 const distance=r=>Math.hypot(Math.max(r.left-x,0,x-r.left-r.width),Math.max(r.top-y,0,y-r.top-r.height))+Math.hypot(x-r.left-r.width/2,y-r.top-r.height/2)*.001;
 let best=current,bestDistance=slots[current]?distance(slots[current]):Infinity;
 for(let i=0;i<slots.length;i++){const d=distance(slots[i]);if(d<bestDistance){best=i;bestDistance=d;}}
 if(best!==current&&slots[current]&&distance(slots[current])-bestDistance<hysteresis)return current;
 return best;
}
