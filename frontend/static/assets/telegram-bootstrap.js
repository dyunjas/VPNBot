// Runs before the SDK. Keep signed launch data in this tab across challenge reloads.
(()=>{
  const data=new URLSearchParams(location.hash.replace(/^#/,'')).get('tgWebAppData');
  if(data){try{sessionStorage.setItem('lunet.telegram.launch',JSON.stringify({data,savedAt:Date.now()}));}catch{}}
})();
