import { useTelegramViewport, selectionHaptic } from "./useTelegramViewport.js";
import { LunetLoader, LunetSkeleton, useActionLock } from "../../shared/controls.jsx";
import {useEffect,useRef,useState} from "react";
import {createRoot} from "react-dom/client";
import {ArrowLeft,CreditCard,Gift,History as HistoryIcon,ShieldCheck,Smartphone,Wallet,Plus} from "lucide-react";
import { AccountIdentitySkeleton, Button, CabinetToast, Notice, money } from "../../shared/account/components.jsx";
import "../../shared/brand.css";
import "../../shared/account/account.css";
import "./miniapp.css";
import "./layout.css";
import "../../shared/controls.css";
import { Addons, Billing, Extras, History, Plans } from "../../shared/account/CommerceViews.jsx";
import { Devices, SubscriptionDetails, SubscriptionSummary } from "../../shared/account/SubscriptionViews.jsx";
import { Profile } from "./ProfileView.jsx";

import { api } from "./telegram.js";
import { DocumentLinks } from "../../shared/DocumentLinks.jsx";
function App(){
  const [view,setView]=useState("subscription"),[data,setData]=useState({});
  const [busy,setBusy]=useState(false),[amount,setAmount]=useState(500),[promo,setPromo]=useState("");
  const [plans,setPlans]=useState([]),[devices,setDevices]=useState([]),[error,setError]=useState("");
  const [loading,setLoading]=useState(true),[resourceLoading,setResourceLoading]=useState(false),[resourceError,setResourceError]=useState("");
  const [resourceVersion,setResourceVersion]=useState(0),[refreshing,setRefreshing]=useState(false);
  const [noticeKind,setNoticeKind]=useState("error");
  const notify=(message,kind="info")=>{setNoticeKind(kind);setError(message);};
  const mutation=useActionLock();
  const mounted=useRef(true),loadSequence=useRef(0),currentProfile=useRef(null);
  const user=data.profile?.user||{},status=data.status||{};
  const go=v=>{if(v!==view)selectionHaptic();setView(v);};
  useTelegramViewport(view,()=>go("subscription"));
  const load=async()=>{
    const attempt=++loadSequence.current;
    if(currentProfile.current)setRefreshing(true);else setLoading(true);setError("");
    try{const [profile,s,config]=await Promise.all([api("/api/profile"),api("/api/status"),api("/api/ui-config").catch(()=>null)]);
      if(mounted.current&&attempt===loadSequence.current){currentProfile.current=profile;setData({profile,status:s,config});}
    }catch(e){if(mounted.current&&attempt===loadSequence.current)notify(e.message,"error");}
    finally{if(mounted.current&&attempt===loadSequence.current){setLoading(false);setRefreshing(false);}}
  };
  useEffect(()=>{mounted.current=true;load();return()=>{mounted.current=false;loadSequence.current++;};},[]);
  useEffect(()=>{
    const path=["plans","extras"].includes(view)?"/api/plans":view==="devices"?"/api/devices":null;
    if(!path){setResourceLoading(false);setResourceError("");return;}
    let current=true;setResourceLoading(true);setResourceError("");
    api(path).then(x=>{if(current){if(path==="/api/plans")setPlans(x.plans||[]);else setDevices(x.items||[]);}})
      .catch(e=>{if(current)setResourceError(e.message);}).finally(()=>{if(current)setResourceLoading(false);});
    return()=>{current=false;};
  },[view,resourceVersion]);
  const action=(path,body,message)=>mutation(async()=>{
    setBusy(true);setError("");
    try{await api(path,body);await load();if(path==="/api/device/delete")setResourceVersion(n=>n+1);notify(message,"success");return true;}
    catch(e){notify(e.message,"error");return false;}finally{setBusy(false);}
  });
  const topup=(method,type)=>mutation(async()=>{
    setBusy(true);setError("");
    try{const result=await api("/api/balance/topup",{amount:Number(amount),method,platega_type:type});
      if(result.payment_url){const tg=window.Telegram?.WebApp;if(tg?.openLink)tg.openLink(result.payment_url);else location.assign(result.payment_url);}
      else notify("Счёт создан. Статус оплаты появится в истории платежей.","success");
    }catch(e){notify(e.message,"error");}finally{setBusy(false);}
  });
  useEffect(()=>{const refresh=()=>load();window.addEventListener("focus",refresh);const tg=window.Telegram?.WebApp;const activated=event=>{if(event.isActive)refresh();};tg?.onEvent?.("activated",activated);return()=>{window.removeEventListener("focus",refresh);tg?.offEvent?.("activated",activated);};},[Boolean(data.profile)]);
  const links=[["subscription","Моя подписка",ShieldCheck],["plans","Купить",CreditCard],["billing","Платежи",Wallet],["history","История",HistoryIcon],["devices","Устройства",Smartphone],["extras","Бонусы",Gift]];
  const activeView=view==="details"?"subscription":view;
  const titles={subscription:["Моя подписка","Всё о твоём подключении Lunet"],details:["Моя подписка","Подключение, LTE-трафик и управление доступом"],plans:["Выбери тариф Lunet","Твой срок, твой LTE-трафик, твои устройства"],billing:["Пополнение баланса","Выбери сумму и удобный способ оплаты"],history:["История платежей","Твои операции и их актуальный статус"],devices:["Мои устройства","Управляй устройствами своей подписки"],extras:["Бонусы и подарки","Промокоды и доступ для близких"]};
  return <div className="mini-app">
    <div className="topbar mini-top-spacer" aria-hidden="true"/>
    <main className="mini-content">
      {(loading||data.profile)&&<section className="mini-account">{loading?<AccountIdentitySkeleton/>:<div className="account-identity"><span className="account-avatar"><img src="/miniapp/assets/profile.png" alt=""/></span><div><button className="account-name" onClick={()=>go("profile")}>{user.email|| (user.username?`@${user.username}`:"Пользователь Lunet")}</button><span className="balance-pill">Баланс: <b>{money(user.balance)} ₽</b><button aria-label="Пополнить баланс" onClick={()=>go("billing")}><Plus size={16}/></button></span></div></div>}<nav className="account-nav" aria-label="Основная навигация">{links.map(([k,l,I])=><button className={activeView===k?"active":""} aria-current={activeView===k?"page":undefined} onClick={()=>go(k)} key={k}><I size={18}/><span>{l}</span></button>)}</nav></section>}
      {error&&<CabinetToast message={error} kind={noticeKind} onClose={()=>setError("")}/>}
      {refreshing&&<p className="refresh-indicator" role="status"><LunetLoader/>Обновляем данные…</p>}
      <div key={view} className="lunet-view" aria-busy={loading||resourceLoading||undefined}>
        {loading?<LunetSkeleton variant="overview"/>:!data.profile?<div className="card card-pad mini-retry"><p>Не удалось загрузить данные.</p><Button onClick={load}>Повторить</Button></div>:resourceError?<div className="card card-pad mini-retry"><p role="alert">{resourceError}</p><Button onClick={()=>setResourceVersion(v=>v+1)}>Повторить</Button></div>:resourceLoading?<LunetSkeleton/>:<>
          {titles[view]&&<header className={`page-head ${["billing","plans","extras","history"].includes(view)?"centered":""}`}><div>{view==="details"&&<button className="text-button back-link" onClick={()=>go("subscription")}><ArrowLeft size={15}/>К подписке</button>}<h1 className="page-heading">{titles[view][0]}</h1><p>{titles[view][1]}</p></div></header>}
          {!data.config&&<Notice kind="error" className="config-warning"><span>Не удалось загрузить условия покупки и способы оплаты.</span><Button variant="secondary" onClick={load}>Повторить загрузку условий</Button></Notice>}
          {view==="subscription"&&<SubscriptionSummary status={status} navigate={go}/>}
          {view==="details"&&<><SubscriptionDetails status={status} config={data.config} navigate={go} busy={busy} onAutoRenew={enabled=>action("/api/subscription/auto-renew",{auto_renew:enabled},enabled?"Автопродление включено":"Автопродление выключено")}/><Addons status={status} config={data.config} onAction={action} busy={busy}/></>}
          {view==="plans"&&<Plans confirmationTitle="Подтверждение покупки" plans={plans} status={status} config={data.config} balance={user.balance} navigate={go} busy={busy} onAction={action} buy={id=>action("/api/subscription/buy",{plan_id:id},"Подписка успешно оформлена")}/>}
          {view==="devices"&&<Devices devices={devices} status={status} busy={busy} refresh={()=>setResourceVersion(n=>n+1)} remove={id=>action("/api/device/delete",{device_id:id},"Устройство удалено")}/>}
          {view==="billing"&&<Billing amount={amount} setAmount={setAmount} config={data.config} topup={topup} navigate={go} busy={busy}/>}
          {view==="history"&&<History transactions={data.profile.transactions} navigate={go}/>}
          {view==="extras"&&<Extras plans={plans} promo={promo} setPromo={setPromo} apply={()=>action("/api/promocode/apply",{code:promo},"Промокод применён")} gift={(recipient,planId)=>action("/api/subscription/gift",{recipient,plan_id:planId},"Подарок отправлен")} busy={busy}/>}
          {view==="profile"&&<Profile user={user} profile={data.profile}/>}
        </>}
      </div>
    </main>
    <footer className="mini-footer cabinet-footer">
      <div className="footer-main">
        <div className="footer-brand"><a className="brand" href="https://lunet.pro/" target="_blank" rel="noopener noreferrer"><img src="/miniapp/assets/lunet-logo.png" alt="" width="34" height="34"/><b>Lunet<span>VPS</span></b></a><p>Твой интернет. Твои правила.<br/>Подписка и устройства в одном кабинете.</p></div>
        <nav aria-label="Сервис"><button onClick={()=>go("subscription")}>Моя подписка</button><button onClick={()=>go("plans")}>Тарифы</button><a href="https://lunet.pro/#how" target="_blank" rel="noopener noreferrer">Как подключиться</a><a href="https://t.me/LunetVpnBot" target="_blank" rel="noopener noreferrer">Telegram-бот</a></nav>
        <nav aria-label="Помощь и документы"><a href="https://t.me/LunetVpnSupport" target="_blank" rel="noopener noreferrer">Поддержка</a><a href="https://lunet.pro/#faq" target="_blank" rel="noopener noreferrer">Частые вопросы</a><DocumentLinks external/></nav>
      </div>
      <div className="footer-bottom"><span>© {new Date().getFullYear()} Lunet VPS</span><span>На связи. С любого устройства.</span></div>
    </footer>
  </div>;
}
function BannedAccountGuard(){useEffect(()=>{const show=()=>{if(!document.body.innerText.toLowerCase().includes("banned"))return;const root=document.getElementById("root");if(root)root.innerHTML='<main class="blocked-screen"><h1>Аккаунт заблокирован</h1></main>'};const observer=new MutationObserver(show);observer.observe(document.body,{subtree:true,childList:true,characterData:true});show();return()=>observer.disconnect()},[]);return null}
createRoot(document.getElementById("root")).render(<><BannedAccountGuard/><App/></>);
