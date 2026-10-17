import {test} from "node:test";
import assert from "node:assert/strict";
import {createReadCache} from "../frontend/shared/readCache.js";
test("tab visits reuse reads until expiry",async()=>{
  let now=0,calls=0;const cache=createReadCache({now:()=>now}),load=async()=>({plans:[++calls]});
  await cache.read("plans",load);now=1000;assert.deepEqual(await cache.read("plans",load),{plans:[1]});
  assert.equal(calls,1);now=31000;await cache.read("plans",load);assert.equal(calls,2);
});
test("concurrent reads share one request",async()=>{
  const cache=createReadCache();let finish,calls=0;
  const load=()=>{calls++;return new Promise(resolve=>{finish=resolve})};
  const one=cache.read("devices",load),two=cache.read("devices",load);
  await Promise.resolve();assert.equal(calls,1);finish({items:[1]});assert.deepEqual(await one,await two);
});
test("old response cannot repopulate an invalidated cache",async()=>{
  const cache=createReadCache();let finish;
  const old=cache.read("devices",()=>new Promise(resolve=>{finish=resolve}));
  await Promise.resolve();cache.clear();await cache.read("devices",async()=>({items:["new"]}));
  finish({items:["old"]});await old;assert.deepEqual(cache.peek("devices"),{items:["new"]});
});
test("failed reads are retried and account caches are separate",async()=>{
  const one=createReadCache(),two=createReadCache();
  await assert.rejects(one.read("devices",async()=>{throw Error("offline")}));
  await one.read("devices",async()=>({items:["private"]}));assert.equal(two.peek("devices"),undefined);
});
