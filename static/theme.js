// Apply before CSS paints. Appearance is a browser preference, separate from personal records.
(()=>{
 const key='personal-council-appearance',modes=['dark','system','light'];
 const root=document.documentElement,media=window.matchMedia('(prefers-color-scheme: dark)');
 const valid=value=>modes.includes(value)?value:'system';
 let preference='system';try{preference=valid(localStorage.getItem(key));}catch{}
 function apply(){
  const resolved=preference==='system'?(media.matches?'dark':'light'):preference;
  root.dataset.theme=resolved;root.dataset.themePreference=preference;root.style.colorScheme=resolved;
  document.querySelectorAll('[data-theme-mode]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.themeMode===preference)));
 }
 function setPreference(value){preference=valid(value);try{localStorage.setItem(key,preference);}catch{}apply();}
 window.personalTheme=Object.freeze({getPreference:()=>preference,setPreference});
 apply();
 media.addEventListener('change',()=>{if(preference==='system')apply();});
 window.addEventListener('storage',e=>{if(e.key===key||e.key===null){preference=valid(e.newValue);apply();}});
 document.addEventListener('click',e=>{const button=e.target.closest('[data-theme-mode]');if(button){setPreference(button.dataset.themeMode);}});
 document.addEventListener('keydown',e=>{
  const button=e.target.closest('[data-theme-mode]');if(!button||!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;
  e.preventDefault();const index=modes.indexOf(preference),next=e.key==='Home'?0:e.key==='End'?2:(index+(e.key==='ArrowRight'?1:2))%3;
  setPreference(modes[next]);button.parentElement.querySelector(`[data-theme-mode="${modes[next]}"]`)?.focus();
 });
})();
