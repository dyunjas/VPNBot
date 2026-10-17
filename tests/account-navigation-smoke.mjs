import {createServer} from "node:http";
import {readFile,mkdir,writeFile} from "node:fs/promises";
import {spawn} from "node:child_process";
import path from "node:path";
import assert from "node:assert/strict";

const root=process.cwd(),counts=new Map(),wait=ms=>new Promise(r=>setTimeout(r,ms));
const profile={user:{email:"demo@example.test",balance:500,tg_id:1},transactions:[],referral:{}};
const server=createServer(async(req,res)=>{
  try{
    const url=new URL(req.url,"http://127.0.0.1:8894");
    if(url.pathname.startsWith("/api/")){
      counts.set(url.pathname,(counts.get(url.pathname)||0)+1);
      const values={"/api/profile":profile,"/api/status":{has_subscription:false},"/api/ui-config":{payment_methods:[],renewal_window_days:3},"/api/plans":{plans:[{id:1,name:"Basic",price:100,period_days:30,gb_limit:10,device_limit:3}]},"/api/devices":{items:[]},"/api/auth/session":{authenticated:true},"/api/auth/me":{user:profile.user}};
      res.setHeader("Content-Type","application/json");res.end(JSON.stringify(values[url.pathname]||{ok:true}));return;
    }
    let file;
    if(url.pathname.startsWith("/miniapp/assets/"))file=path.join(root,"frontend/static",url.pathname.slice(9));
    else{const kind=url.pathname.startsWith("/miniapp")?"miniapp":"cabinet";file=path.join(root,`frontend/build/${kind}`,url.pathname.replace(new RegExp(`^/${kind}/?`),""));if(!path.extname(file))file=path.join(root,`frontend/build/${kind}/index.html`)}
    if(!file.startsWith(root+path.sep))throw Error("invalid path");
    const data=await readFile(file);res.setHeader("Content-Type",file.endsWith(".js")?"text/javascript":file.endsWith(".css")?"text/css":file.endsWith(".html")?"text/html":"application/octet-stream");res.end(data);
  }catch{res.writeHead(404);res.end()}
});
await new Promise(r=>server.listen(8894,"127.0.0.1",r));
const chrome=spawn("C:/Program Files/Google/Chrome/Application/chrome.exe",["--headless=new","--no-first-run","--disable-extensions","--remote-debugging-port=9235","--user-data-dir="+path.join(root,"artifacts/performance-chrome"),"about:blank"],{windowsHide:true,stdio:"ignore"});
let ws,command;
try{
  let page;for(let i=0;i<50;i++){try{page=(await fetch("http://127.0.0.1:9235/json/list").then(r=>r.json())).find(p=>p.type==="page");if(page)break}catch{}await wait(100)}
  assert(page);ws=new WebSocket(page.webSocketDebuggerUrl);await new Promise(r=>ws.onopen=r);
  let id=0;const pending=new Map(),errors=[];
  ws.onmessage=event=>{const data=JSON.parse(event.data);if(data.id){const item=pending.get(data.id);pending.delete(data.id);data.error?item.reject(Error(JSON.stringify(data.error))):item.resolve(data.result)}else if(data.method==="Runtime.exceptionThrown")errors.push(data.params.exceptionDetails.exception?.description||data.params.exceptionDetails.text)};
  command=(method,params={})=>new Promise((resolve,reject)=>{const key=++id;pending.set(key,{resolve,reject});ws.send(JSON.stringify({id:key,method,params}))});
  const evaluate=async expression=>{const r=await command("Runtime.evaluate",{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description);return r.result.value};
  await command("Page.enable");await command("Runtime.enable");
  await command("Page.addScriptToEvaluateOnNewDocument",{source:"localStorage.setItem('cabinet_access_token','fixture');"});
  await command("Emulation.setDeviceMetricsOverride",{width:390,height:844,deviceScaleFactor:1,mobile:true});
  for(const kind of ["cabinet","miniapp"]){
    counts.clear();const signed=`auth_date=${Math.floor(Date.now()/1000)}&hash=fixture`;
    await command("Page.navigate",{url:`http://127.0.0.1:8894/${kind}/#tgWebAppData=${encodeURIComponent(signed)}`});await wait(600);
    assert((await evaluate("document.body.innerText")).includes("demo@example.test"));
    const nav=kind==="cabinet"?'nav[aria-label="Разделы кабинета"]':'nav[aria-label="Основная навигация"]';
    const click=async index=>{await evaluate(`document.querySelectorAll(${JSON.stringify(nav+" button")})[${index}].click()`);await wait(120)};
    await click(1);await click(5);await click(1);
    assert.equal(counts.get("/api/plans"),1,kind+": plans/extras should share the loaded catalog");
    await click(4);await click(1);await click(4);
    assert.equal(counts.get("/api/devices"),1,kind+": tab revisits should reuse devices");
    await evaluate("[...document.querySelectorAll('button')].find(b=>b.textContent.includes('Обновить список')).click()");await wait(150);
    assert.equal(counts.get("/api/devices"),2,kind+": manual refresh must bypass cache");
    assert(await evaluate("document.documentElement.scrollWidth<=innerWidth"));
    await mkdir("artifacts/performance-ui",{recursive:true});const shot=await command("Page.captureScreenshot",{format:"png"});await writeFile(`artifacts/performance-ui/${kind}.png`,Buffer.from(shot.data,"base64"));
  }
  assert.deepEqual(errors,[]);console.log("Cabinet and Mini App passed: cached navigation, forced device refresh, mobile viewport, no runtime errors.");
}finally{if(command&&ws?.readyState===1){try{await command("Browser.close")}catch{}}ws?.close();chrome.kill();server.closeAllConnections();await new Promise(r=>server.close(r))}
