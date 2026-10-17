import {useEffect,useRef,useState} from "react";
import {createReadCache} from "../readCache.js";

export function useAccountResources({view,version,api,setPlans,setDevices}){
  const cache=useRef(null),lastVersion=useRef(version);
  if(!cache.current)cache.current=createReadCache();
  const [resourceLoading,setLoading]=useState(false),[resourceError,setError]=useState("");
  useEffect(()=>{
    if(lastVersion.current!==version){lastVersion.current=version;cache.current.clear()}
    const path=["plans","extras"].includes(view)?"/api/plans":view==="devices"?"/api/devices":null;
    setError("");if(!path){setLoading(false);return}
    let current=true;
    const apply=data=>{if(path==="/api/plans")setPlans(data.plans||[]);else setDevices(data.items||[])};
    const saved=cache.current.peek(path);
    if(saved!==undefined){apply(saved);setLoading(false);return}
    setLoading(true);
    cache.current.read(path,()=>api(path)).then(data=>{if(current)apply(data)})
      .catch(error=>{if(current)setError(error.message)}).finally(()=>{if(current)setLoading(false)});
    return()=>{current=false};
  },[view,version,api,setPlans,setDevices]);
  return {resourceLoading,resourceError};
}
