// Per-mounted-account cache. No persistence and no caching of mutations or auth.
export function createReadCache({ttl=30000,now=Date.now}={}){
  const values=new Map(),pending=new Map();let generation=0;
  const peek=key=>{const item=values.get(key);return item&&now()-item.at<ttl?item.value:undefined};
  return {peek,clear(){generation++;values.clear();pending.clear()},read(key,loader){
    const cached=peek(key);if(cached!==undefined)return Promise.resolve(cached);
    if(pending.has(key))return pending.get(key);
    const started=generation;
    const request=Promise.resolve().then(loader).then(value=>{if(started===generation)values.set(key,{value,at:now()});return value}).finally(()=>{if(pending.get(key)===request)pending.delete(key)});
    pending.set(key,request);return request;
  }};
}
