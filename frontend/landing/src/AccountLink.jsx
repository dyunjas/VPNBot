import { useEffect, useState } from "react";

export function useLandingAccount() {
  const [user,setUser]=useState(null);
  useEffect(()=>{
    const remote = ["lunet.pro","www.lunet.pro"].includes(location.hostname);
    const endpoint = remote ? "https://app.lunet.pro/api/auth/session" : "/api/auth/session";
    let sequence=0;
    const controllers=new Set();
    const refresh=async()=>{
      const attempt=++sequence,controller=new AbortController();controllers.add(controller);
      const timeout=setTimeout(()=>controller.abort(),8000);
      try {
        let token=null; if(!remote){try{token=localStorage.getItem("cabinet_access_token");}catch{}}
        const response=await fetch(endpoint,{credentials:"include",cache:"no-store",signal:controller.signal,headers:token?{Authorization:`Bearer ${token}`}:{}});
        if(!response.ok)throw new Error("session");
        const data=await response.json();
        if(attempt===sequence)setUser(data.authenticated&&data.user?data.user:null);
      }catch{if(attempt===sequence)setUser(null);}finally{clearTimeout(timeout);controllers.delete(controller);}
    };
    const focus=()=>refresh(), visible=()=>{if(document.visibilityState==="visible")refresh();}, storage=event=>{if(event.key==="cabinet_access_token")refresh();};
    refresh();window.addEventListener("focus",focus);window.addEventListener("pageshow",focus);window.addEventListener("storage",storage);document.addEventListener("visibilitychange",visible);
    return()=>{sequence++;controllers.forEach(c=>c.abort());window.removeEventListener("focus",focus);window.removeEventListener("pageshow",focus);window.removeEventListener("storage",storage);document.removeEventListener("visibilitychange",visible);};
  },[]);
  return user;
}

export default function AccountLink({user,className="",onClick}) {
  const name=user?.username||user?.email||"Аккаунт";
  return user?<a className={`landing-account ${className}`} href="/cabinet/" onClick={onClick} aria-label={`Личный кабинет: ${name}`} title={name}><img src="/miniapp/assets/profile.png" alt="" width="32" height="32"/><span>{name}</span></a>:<a className={`button landing-login ${className}`} href="/cabinet/login" onClick={onClick}>Войти</a>;
}
