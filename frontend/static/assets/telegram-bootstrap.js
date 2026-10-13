// Capture launch parameters before the SDK or the application changes the URL.
// This can also run in the TurtleGuard challenge template, before its redirect.
(()=>{
  const key="lunet.telegram.launch";
  function capture(){
    const hash=location.hash.slice(1),query=new URLSearchParams(location.search);
    const params=new URLSearchParams(hash.includes("?")?hash.slice(hash.indexOf("?")+1):hash);
    const data=params.get("tgWebAppData")||query.get("tgWebAppData");
    if(!data||data.length>16384)return;
    try{sessionStorage.setItem(key,JSON.stringify({data,savedAt:Date.now()}));}catch{}
  }
  capture();window.addEventListener("hashchange",capture);window.addEventListener("pagehide",capture);
  // A same-origin challenge must preserve Telegram's fragment on its next URL.
  // Do not alter third-party redirects or an existing destination fragment.
  if(window.__tgChal?.next&&location.hash){
    try{const next=new URL(window.__tgChal.next,location.href);if(next.origin===location.origin&&!next.hash){next.hash=location.hash;window.__tgChal.next=next.pathname+next.search+next.hash;}}catch{}
  }
})();
