import {useAccountResources} from "../../shared/account/useAccountResources.js";
import { DocumentLinks } from "../../shared/DocumentLinks.jsx";
import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, Menu, CreditCard, Gift, History as HistoryIcon, LogOut, Headphones, Plus, ShieldCheck, Smartphone, Wallet } from "lucide-react";
import { LunetLoader,LunetSkeleton, useActionLock } from "../../shared/controls.jsx";
import { api, tokenKey } from "./api.js";
import { AccountIdentitySkeleton, Button, CabinetToast, Notice, Card, date, Empty, money } from "../../shared/account/components.jsx";
import { CopyField, Devices, SubscriptionDetails, SubscriptionSummary } from "../../shared/account/SubscriptionViews.jsx";
import { Addons, Billing, Extras, History, Plans } from "../../shared/account/CommerceViews.jsx";

const nav=[["subscription","Моя подписка",ShieldCheck],["plans","Купить",CreditCard],["billing","Платежи",Wallet],["history","История",HistoryIcon],["devices","Устройства",Smartphone],["extras","Бонусы",Gift]];
const titles={subscription:["Моя подписка","Всё о твоём подключении Lunet"],details:["Моя подписка","Подключение, LTE-трафик и управление доступом"],plans:["Выбери тариф Lunet","Твой срок, твой LTE-трафик, твои устройства"],billing:["Пополнение баланса","Выбери сумму и удобный способ оплаты"],history:["История платежей","Твои операции и их актуальный статус"],devices:["Мои устройства","Управляй устройствами своей подписки"],extras:["Бонусы и подарки","Промокоды и доступ для близких"],profile:["Личный кабинет","Данные твоего аккаунта"],referral:["Реферальная программа","Твои приглашения и вознаграждения"]};
const initialView=()=>{const view=new URLSearchParams(location.search).get("view");return titles[view]?view:"subscription";};
const support="https://t.me/LunetVpnSupport";

function Avatar({user,small=false}) {return <span className={`account-avatar ${small?"small":""}`} aria-hidden="true"><img src="/miniapp/assets/profile.png" alt=""/></span>;}
function Footer(){return <footer className="cabinet-footer"><div className="cabinet-container footer-main"><div><a className="brand" href="https://lunet.pro/"><img src="/miniapp/assets/lunet-logo.png" alt="" width="34" height="34"/><b>Lunet<span>VPS</span></b></a><p>Твой интернет. Твои правила.<br/>Подписка и устройства в одном кабинете.</p></div><nav aria-label="Помощь"><a href={support} target="_blank" rel="noopener noreferrer">Поддержка</a><a href="https://lunet.pro/#how">Как подключиться</a><a href="https://lunet.pro/#faq">Частые вопросы</a><a href="https://t.me/LunetVpnBot" target="_blank" rel="noopener noreferrer">Telegram-бот</a></nav><nav aria-label="Документы"><DocumentLinks/></nav></div><div className="cabinet-container footer-bottom"><span>© {new Date().getFullYear()} Lunet</span><span>На связи. С любого устройства.</span></div></footer>;}

export default function Cabinet(){
  const [view,setView]=useState(initialView),[menuMode,setMenuMode]=useState("");
  const [profile,setProfile]=useState(null),[status,setStatus]=useState(null),[config,setConfig]=useState(null),[configError,setConfigError]=useState(false);
  const [loading,setLoading]=useState(true),[refreshing,setRefreshing]=useState(false);
  const [plans,setPlans]=useState([]),[devices,setDevices]=useState([]),[resourceVersion,setResourceVersion]=useState(0);
  const [notice,setNotice]=useState(null),[initialError,setInitialError]=useState(""),[busy,setBusy]=useState(false),[amount,setAmount]=useState(500),[promo,setPromo]=useState("");
  const panel=useRef(null), profileTrigger=useRef(null), sequence=useRef(0), mounted=useRef(true), currentProfile=useRef(null);
  const mutation=useActionLock();
  useEffect(()=>{
    if(!menuMode)return;
    const items=()=>Array.from(panel.current?.querySelectorAll('[role="menuitem"]:not(:disabled)')||[]);
    items()[0]?.focus();
    const outside=event=>{if(!panel.current?.contains(event.target)&&!profileTrigger.current?.contains(event.target))setMenuMode("");};
    const keyboard=event=>{
      if(event.key==="Escape"){event.preventDefault();setMenuMode("");profileTrigger.current?.focus();}
      else if(event.key==="Tab")setMenuMode("");
      else if(["ArrowDown","ArrowUp","Home","End"].includes(event.key)){
        event.preventDefault();const options=items(),index=options.indexOf(document.activeElement);
        const next=event.key==="Home"?0:event.key==="End"?options.length-1:(index+(event.key==="ArrowDown"?1:-1)+options.length)%options.length;
        options[next]?.focus();
      }
    };
    document.addEventListener("pointerdown",outside);document.addEventListener("keydown",keyboard);
    return()=>{document.removeEventListener("pointerdown",outside);document.removeEventListener("keydown",keyboard);};
  },[menuMode]);
  const user=profile?.user||{};
  const notify=(message,kind="success")=>setNotice({message,kind});
  const load=async()=>{
    const attempt=++sequence.current;
    if(!currentProfile.current)setLoading(true);else setRefreshing(true);
    setInitialError("");
    try{const [p,s]=await Promise.all([api("/api/profile"),api("/api/status")]);
      if(mounted.current&&attempt===sequence.current){currentProfile.current=p;setProfile(p);setStatus(s);}
    }catch(error){if(mounted.current&&attempt===sequence.current){if(!currentProfile.current)setInitialError(error.message);else notify(error.message,"error");}}
    finally{if(mounted.current&&attempt===sequence.current){setLoading(false);setRefreshing(false);}}
  };
  const loadConfig=async()=>{setConfigError(false);try{const data=await api("/api/ui-config");if(mounted.current)setConfig(data);}catch{if(mounted.current)setConfigError(true);}};
  useEffect(()=>{mounted.current=true;load();loadConfig();return()=>{mounted.current=false;sequence.current++;};},[]);
  const {resourceLoading,resourceError}=useAccountResources({view,version:resourceVersion,api,setPlans,setDevices});
  const navigate=next=>{setView(next);setMenuMode("");const url=new URL(location.href);url.searchParams.set("view",next);history.replaceState(null,"",url);};
  const action=(path,body,message)=>mutation(async()=>{
    setBusy(true);setNotice(null);
    try{await api(path,{body:JSON.stringify(body)});notify(message);await load();setResourceVersion(n=>n+1);return true;}
    catch(error){notify(error.message,"error");return false;}finally{if(mounted.current)setBusy(false);}
  });
  const topup=(method,type)=>mutation(async()=>{
    if(!Number.isFinite(Number(amount))||Number(amount)<=0)return;
    setBusy(true);setNotice(null);
    try{const data=await api("/api/balance/topup",{body:JSON.stringify({amount:Number(amount),method,platega_type:type})});
      if(data.provider_id){try{sessionStorage.setItem("lunet_pending_payment",JSON.stringify({method,provider_id:data.provider_id}));}catch{}}
      if(data.payment_url)location.assign(data.payment_url);else notify("Счёт создан. Проверь статус оплаты после завершения платежа.");
    }catch(error){notify(error.message,"error");}finally{if(mounted.current)setBusy(false);}
  });
  useEffect(()=>{const focus=()=>{if(currentProfile.current)load();};window.addEventListener("focus",focus);return()=>window.removeEventListener("focus",focus);},[]);
  const logout=()=>mutation(async()=>{
    setBusy(true);
    try{await api("/api/auth/logout");localStorage.removeItem(tokenKey);try{sessionStorage.removeItem("lunet_pending_payment");}catch{}location.assign("/cabinet/login");}
    catch(error){notify(error.message,"error");setBusy(false);}
  });
  return <div className="cabinet-shell">
    <a className="skip-link" href="#cabinet-content">К содержимому</a>
    <header className="cabinet-header cabinet-container"><a className="brand" href="https://lunet.pro/"><img src="/miniapp/assets/lunet-logo.png" alt="" width="34" height="34"/><b>Lunet<span>VPS</span></b></a><nav className="site-nav" aria-label="Сайт Lunet"><a href="https://lunet.pro/#about">О сервисе</a><a href="https://lunet.pro/#how">Инструкции</a><button onClick={()=>navigate("plans")}>Тарифы</button><a href={support} target="_blank" rel="noopener noreferrer">Поддержка</a></nav><div className="profile-dropdown"><button ref={profileTrigger} aria-haspopup="menu" className="profile-trigger" aria-label="Меню профиля" aria-expanded={menuMode==="profile"} aria-controls="cabinet-menu" onClick={()=>setMenuMode(menuMode==="profile"?"":"profile")}><Menu size={20}/></button>{menuMode&&<div className="account-menu" ref={panel} role="menu" aria-label="Меню профиля" id="cabinet-menu"><a className="menu-item" role="menuitem" href={support} onClick={()=>setMenuMode("")} target="_blank" rel="noopener noreferrer"><Headphones size={17}/>Поддержка</a><button className="menu-item" role="menuitem" onClick={logout} disabled={busy}><LogOut size={17}/>Выйти</button></div>}</div></header>

    <div className="cabinet-container account-strip">{loading?<AccountIdentitySkeleton/>:profile?<div className="account-identity"><Avatar user={user}/><div><button className="account-name" onClick={()=>navigate("profile")} title={user.email||user.username||"Аккаунт"}>{user.email||(user.username?`@${user.username}`:"Аккаунт Lunet")}</button><div className="balance-pill"><span>Баланс: <b>{`${money(user.balance)} ₽`}</b></span><button aria-label="Пополнить баланс" onClick={()=>navigate("billing")}><Plus size={17}/></button></div></div></div>:null}<nav className="account-nav" aria-label="Разделы кабинета">{nav.map(([key,label,Icon])=><button key={key} aria-current={(view==="details"?"subscription":view)===key?"page":undefined} className={(view==="details"?"subscription":view)===key?"active":""} onClick={()=>navigate(key)}><Icon size={17}/><span>{label}</span></button>)}</nav><Button variant="secondary" className="strip-logout" disabled={busy} onClick={logout}><LogOut size={15}/>Выйти</Button></div>
    <main className="cabinet-content cabinet-container" id="cabinet-content"><header className={`page-head ${["billing","plans","extras","history"].includes(view)?"centered":""}`}><div>{view==="details"&&<button className="text-button back-link" onClick={()=>navigate("subscription")}><ArrowLeft size={15}/>К подписке</button>}<h1>{titles[view][0]}</h1><p>{titles[view][1]}</p></div></header>
      {refreshing&&<p className="account-refresh-status" role="status"><LunetLoader size={14}/>Обновление данных…</p>}
      {notice&&<CabinetToast message={notice.message} kind={notice.kind} onClose={()=>setNotice(null)}/>}
      {configError&&<Notice className="config-warning" role="status" kind="error"><span>Не удалось загрузить условия покупки и способы оплаты.</span><Button variant="secondary" onClick={loadConfig}>Повторить загрузку условий</Button></Notice>}
      <div key={view} className="lunet-view" aria-busy={loading||resourceLoading||undefined}>{loading?<LunetSkeleton variant="overview"/>:!profile?<Empty Icon={ShieldCheck} title="Не удалось загрузить кабинет" action={<Button onClick={load}>Повторить</Button>}>{initialError}</Empty>:resourceError?<Empty title="Не удалось загрузить раздел" action={<Button onClick={()=>setResourceVersion(n=>n+1)}>Повторить</Button>}>{resourceError}</Empty>:resourceLoading?<LunetSkeleton/>:
        view==="subscription"?<SubscriptionSummary status={status} navigate={navigate}/>:
        view==="details"?<><SubscriptionDetails status={status} config={config} navigate={navigate} busy={busy} onAutoRenew={enabled=>action("/api/subscription/auto-renew",{auto_renew:enabled},enabled?"Автопродление включено":"Автопродление выключено")}/><Addons status={status} config={config} onAction={action} busy={busy}/></>:
        view==="plans"?<Plans plans={plans} status={status} config={config} balance={user.balance} busy={busy} navigate={navigate} buy={id=>action("/api/subscription/buy",{plan_id:id},"Подписка успешно оформлена")} onAction={action}/>:
        view==="billing"?<Billing amount={amount} setAmount={setAmount} config={config} topup={topup} navigate={navigate} busy={busy}/>:
        view==="history"?<History transactions={profile.transactions} navigate={navigate} busy={busy}/>:
        view==="devices"?<Devices devices={devices} status={status} remove={id=>action("/api/device/delete",{device_id:id},"Устройство удалено")} refresh={()=>setResourceVersion(n=>n+1)} busy={busy}/>:
        view==="extras"?<Extras plans={plans} promo={promo} setPromo={setPromo} apply={()=>action("/api/promocode/apply",{code:promo},"Промокод применён")} gift={(recipient,planId)=>action("/api/subscription/gift",{recipient,plan_id:planId},"Подарок отправлен")} busy={busy}/>:
        view==="profile"?<Card className="profile-card"><div className="card-heading"><Avatar user={user}/><div><h2>{user.username?`@${user.username}`:"Аккаунт Lunet"}</h2><p>{user.email||"Почта не указана"}</p></div></div><dl className="detail-list"><div><dt>Почта</dt><dd>{user.email||"Не указана"}</dd></div><div><dt>Username</dt><dd>{user.username||"Не указан"}</dd></div><div><dt>Telegram</dt><dd><span className={`badge ${user.tg_id?"ok":"neutral"}`}>{user.tg_id?"Привязан":"Не привязан"}</span></dd></div>{user.created_at&&<div><dt>Аккаунт создан</dt><dd>{date(user.created_at)}</dd></div>}</dl>{user.tg_id&&<CopyField value={user.tg_id} label="Telegram ID"/>}<div className="profile-links"><a href={support} target="_blank" rel="noopener noreferrer">Поддержка в Telegram <ArrowRight size={15}/></a><button className="text-button" onClick={()=>navigate("referral")}>Реферальная программа <ArrowRight size={15}/></button></div><Button variant="secondary" onClick={logout} disabled={busy}><LogOut size={16}/>Выйти из аккаунта</Button></Card>:
        <Card className="referral-card"><h2>Твои вознаграждения</h2><div className="referral-metrics"><div><span>Реферальный баланс</span><strong>{money(profile.referral?.balance)} ₽</strong></div><div><span>Приглашено друзей</span><strong>{profile.referral?.invited_count??0}</strong></div><div><span>Вознаграждение</span><strong>{profile.referral?.percent??0}%</strong></div></div></Card>}
      </div>
    </main><Footer/>
  </div>;
}
