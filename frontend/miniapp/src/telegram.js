const CACHE_KEY="lunet.telegram.launch",MAX_AGE_MS=3600000;
let waiting;
const storage=key=>{try{return JSON.parse(sessionStorage.getItem(key)||"null")}catch{return null}};
function urlData(){
  const hash=location.hash.slice(1);
  return new URLSearchParams(hash.includes("?")?hash.slice(hash.indexOf("?")+1):hash).get("tgWebAppData")||new URLSearchParams(location.search).get("tgWebAppData")||"";
}
function fresh(data){
  if(typeof data!=="string"||data.length>16384)return false;
  const date=Number(new URLSearchParams(data).get("auth_date")),now=Date.now()/1000;
  return date>0&&date<=now+60&&now-date<MAX_AGE_MS/1000;
}
export function readTelegramData(){
  // The official SDK stores launch parameters under __telegram__initParams.
  // Use this cache only when the current URL and WebApp have no launch data.
  const current=urlData()||window.Telegram?.WebApp?.initData||window.Telegram?.WebView?.initParams?.tgWebAppData||"";
  if(current){try{sessionStorage.setItem(CACHE_KEY,JSON.stringify({data:current,savedAt:Date.now()}))}catch{}return current}
  const cached=storage(CACHE_KEY),sdkCached=storage("__telegram__initParams")?.tgWebAppData;
  if(cached?.data&&Date.now()-cached.savedAt<MAX_AGE_MS&&fresh(cached.data))return cached.data;
  if(fresh(sdkCached))return sdkCached;
  try{sessionStorage.removeItem(CACHE_KEY)}catch{}
  return "";
}
export function waitForTelegramData(timeout=30000){
  const current=readTelegramData();if(current)return Promise.resolve(current);
  if(!waiting)waiting=new Promise((resolve,reject)=>{
    const deadline=Date.now()+timeout;
    const check=()=>{const data=readTelegramData();if(data){cleanup();resolve(data)}else if(Date.now()>=deadline){cleanup();reject(Object.assign(new Error("Данные входа Telegram потеряны при загрузке страницы. Закройте мини-приложение и откройте его через бота."),{code:"telegram_missing"}))}};
    const cleanup=()=>{clearInterval(timer);window.removeEventListener("hashchange",check);window.removeEventListener("pageshow",check)};
    const timer=setInterval(check,100);window.addEventListener("hashchange",check);window.addEventListener("pageshow",check);
  }).finally(()=>{waiting=null});
  return waiting;
}
readTelegramData();
export async function api(path,body={}){
  const initData=await waitForTelegramData();
  const response=await fetch(path,{method:"POST",headers:{"Content-Type":"application/json",Accept:"application/json"},credentials:"same-origin",body:JSON.stringify({...body,initData})});
  if(!/application\/json/i.test(response.headers.get("content-type")||"")){
    // Do not repeat mutations: a purchase might already have completed.
    throw Object.assign(new Error("Запрос остановлен защитой сайта. Завершите проверку и нажмите «Повторить»."),{code:"protection_challenge"});
  }
  const data=await response.json();
  if(!response.ok){
    const missing=/init.?data.*missing/i.test(String(data.detail));
    const error=new Error(missing?"Данные входа Telegram не получены. Откройте мини-приложение через бота.":typeof data.detail==="string"?data.detail:"Не удалось выполнить запрос. Попробуйте ещё раз.");
    if(response.status===403&&data.detail==="banned")error.code="banned";
    if(missing)error.code="telegram_missing";
    throw error;
  }
  return data;
}
