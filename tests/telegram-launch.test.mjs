import {readFile} from "node:fs/promises";
import {test} from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";

const client=(await readFile("frontend/miniapp/src/telegram.js","utf8")).replace(/export /g,"");
const bootstrap=await readFile("frontend/static/assets/telegram-bootstrap.js","utf8");
const guard=await readFile("deploy/turtleguard-preserve-telegram.js","utf8");
const signed=id=>`user=${encodeURIComponent(JSON.stringify({id}))}&auth_date=${Math.floor(Date.now()/1000)}&hash=fixture-signature`;
function browser(url="https://miniapp.example/miniapp/",values={}){
  const map=new Map(Object.entries(values)),events=new EventTarget();
  const context=vm.createContext({URL,URLSearchParams,Date,Promise,Error,JSON,Number,setInterval,clearInterval,setTimeout,
    location:new URL(url),sessionStorage:{getItem:k=>map.get(k)||null,setItem:(k,v)=>map.set(k,v),removeItem:k=>map.delete(k)},
    window:{addEventListener:events.addEventListener.bind(events),removeEventListener:events.removeEventListener.bind(events)},
    fetch:async()=>{throw Error("Unexpected request")}});
  return {context,map,run:code=>vm.runInContext(code,context)};
}
test("TurtleGuard first visit preserves signed fragment before SDK or app exists",()=>{
  const data=signed(1),b=browser("https://miniapp.example/miniapp/?test=1#tgWebAppData="+encodeURIComponent(data));
  b.context.window.__tgChal={next:"/miniapp/?test=1"};b.run(guard);
  const redirected=new URL(b.context.window.__tgChal.next,b.context.location);
  assert.equal(new URLSearchParams(redirected.hash.slice(1)).get("tgWebAppData"),data);
  const after=browser(redirected.href);after.run(client);assert.equal(after.run("readTelegramData()"),data);
});
test("challenge patch does not forward credentials to another origin",()=>{
  const b=browser("https://miniapp.example/miniapp/#tgWebAppData=secret");
  b.context.window.__tgChal={next:"https://other.example/"};b.run(guard);
  assert.equal(b.context.window.__tgChal.next,"https://other.example/");
});
test("early capture survives fragment stripping on reload",()=>{
  const data=signed(2),b=browser("https://miniapp.example/miniapp/#/subscription?tgWebAppData="+encodeURIComponent(data));
  b.run(bootstrap);b.context.location.hash="";b.run(client);assert.equal(b.run("readTelegramData()"),data);
});
test("official SDK cache recovers after a challenge removes the fragment",()=>{
  const data=signed(3),b=browser(undefined,{__telegram__initParams:JSON.stringify({tgWebAppData:data})});
  b.run(client);assert.equal(b.run("readTelegramData()"),data);
});
test("current launch overrides a previous account's cache",()=>{
  const current=signed(4),b=browser("https://miniapp.example/miniapp/#tgWebAppData="+encodeURIComponent(current),{"lunet.telegram.launch":JSON.stringify({data:signed(99),savedAt:Date.now()})});
  b.run(client);assert.equal(b.run("readTelegramData()"),current);
});
test("expired SDK and app caches never supply authentication",()=>{
  const data="auth_date=1&hash=old",b=browser(undefined,{__telegram__initParams:JSON.stringify({tgWebAppData:data}),"lunet.telegram.launch":JSON.stringify({data,savedAt:Date.now()})});
  b.run(client);assert.equal(b.run("readTelegramData()"),"");
});
test("blocked sessionStorage still allows current signed launch",()=>{
  const data=signed(5),b=browser("https://miniapp.example/miniapp/#tgWebAppData="+encodeURIComponent(data));
  b.context.sessionStorage={getItem(){throw Error("blocked")},setItem(){throw Error("blocked")},removeItem(){throw Error("blocked")}};
  b.run(client);assert.equal(b.run("readTelegramData()"),data);
});
test("delayed SDK sends signed data and never an empty API request",async()=>{
  const b=browser();b.run(client);let calls=0;
  b.context.fetch=async(path,options)=>{calls++;assert.equal(JSON.parse(options.body).initData,signedData);return{ok:true,headers:{get:()=>"application/json"},json:async()=>({ok:true})}};
  const signedData=signed(6),request=b.run("api('/api/profile')");
  await new Promise(resolve=>setTimeout(resolve,30));assert.equal(calls,0);
  b.context.window.Telegram={WebApp:{initData:signedData}};await request;assert.equal(calls,1);
});
test("missing launch data rejects without sending a request",async()=>{
  const b=browser();b.run(client);await assert.rejects(b.run("waitForTelegramData(1)"),e=>e.code==="telegram_missing");
});
test("HTML challenge does not retry a purchase",async()=>{
  const b=browser();b.context.window.Telegram={WebApp:{initData:signed(7)}};b.run(client);let calls=0;
  b.context.fetch=async()=>{calls++;return{ok:true,headers:{get:()=>"text/html"}}};
  await assert.rejects(b.run("api('/api/subscription/buy',{plan_id:1})"),e=>e.code==="protection_challenge");assert.equal(calls,1);
});
