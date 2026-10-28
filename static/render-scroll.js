// Rebuilding the page can temporarily collapse its height (notably with packed
// dashboard cards). Restore synchronously, before paint. Navigation may still
// choose its own position afterwards; no delayed scroll can override it.
export function preserveScroll(viewport,redraw){
 const left=viewport.scrollX,top=viewport.scrollY;
 try{return redraw();}
 finally{viewport.scrollTo({left,top,behavior:'instant'});}
}

export function createScrollRenderer(viewport){
 let previousKey;
 return (key,redraw)=>{
  const result=key===previousKey?preserveScroll(viewport,redraw):redraw();
  if(key!==previousKey)viewport.scrollTo({left:0,top:0,behavior:'instant'});
  previousKey=key;
  return result;
 };
}
