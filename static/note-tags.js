// Read tag metadata as text, never evaluate YAML objects or note instructions.
function scalar(text){
 text=text.trim();
 if(text.startsWith('"')){try{return JSON.parse(text);}catch{return '';}}
 if(text.startsWith("'"))return /^'(?:[^']|'')*'$/.test(text)?text.slice(1,-1).replaceAll("''", "'"):'';
 return text.replace(/\s+#.*$/,'').trim();
}
function values(text){
 if(text.trim().startsWith('[')){
  const raw=text.trim().replace(/\s+#.*$/,'');if(!raw.endsWith(']'))return [];
  return (raw.slice(1,-1).match(/"(?:\\.|[^"\\])*"|'(?:''|[^'])*'|[^,]+/g)||[]).map(scalar);
 }
 const value=scalar(text);return typeof value==='string'?value.split(/[,，\s]+/):[];
}
export function extractNoteTags(body){
 const tags=[],add=t=>{if(typeof t!=='string')return;t=t.trim().replace(/^#/,'');if(t&&/^[\p{L}\p{N}_/-]+$/u.test(t)&&!/^[\d/]+$/.test(t)&&!tags.includes(t))tags.push(t);};
 let content=body.replace(/^\uFEFF/,'');
 const front=content.match(/^---\s*\r?\n([\s\S]*?)\r?\n(?:---|\.\.\.)\s*(?:\r?\n|$)/);
 if(front){
  const lines=front[1].split(/\r?\n/);
  for(let i=0;i<lines.length;i++){
   const m=lines[i].match(/^(?:tags|tag):\s*(.*)$/i);if(!m)continue;
   if(m[1]&&!m[1].startsWith('#'))values(m[1]).forEach(add);
   else for(let j=i+1;j<lines.length;j++){
    if(!lines[j].trim()||/^\s*#/.test(lines[j]))continue;
    const item=lines[j].match(/^\s*-\s+(.+)$/);if(!item)break;values(item[1]).forEach(add);
   }
  }
  content=content.slice(front[0].length);
 }
 let fence=null;
 content=content.split(/\r?\n/).map(line=>{const m=line.match(/^\s{0,3}(`{3,}|~{3,})/);if(m){if(!fence)fence={ch:m[1][0],length:m[1].length};else if(m[1][0]===fence.ch&&m[1].length>=fence.length)fence=null;return '';}return fence?'':line;}).join('\n');
 content=content.replace(/<!--[\s\S]*?-->/g,'').replace(/(`+)[\s\S]*?\1/g,'').replace(/!?\[[^\]]*\]\([^)]*\)/g,'').replace(/<[^>]*>/g,'');
 for(const m of content.matchAll(/(^|[\s（(【\[])#([\p{L}\p{N}_/-]+)/gu))add(m[2]);
 return tags;
}
export function tagSummary(notes){
 const counts=new Map();for(const note of notes)for(const tag of new Set(note.tags))counts.set(tag,(counts.get(tag)||0)+1);
 return [...counts].map(([tag,count])=>({tag,count})).sort((a,b)=>b.count-a.count||a.tag.localeCompare(b.tag,'zh'));
}
export function mergeOriginalTags(note){return [...new Set([...note.tags,...extractNoteTags(note.body)])];}
