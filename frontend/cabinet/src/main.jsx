import { NotFound } from "../../shared/NotFound.jsx";
import { useState } from "react";
import { createRoot } from "react-dom/client";
import { ArrowLeft, Mail, Send } from "lucide-react";
import { useActionLock } from "../../shared/controls.jsx";
import { SessionGate } from "../../shared/SessionGate.jsx";
import { api, tokenKey } from "./api.js";
import { Button, Field, CabinetToast } from "../../shared/account/components.jsx";
import Cabinet from "./CabinetApp.jsx";
import CookieNotice from "../../shared/CookieNotice.jsx";
import authPreview from "../../static/assets/cabinet-mobile.webp";
import "../../shared/controls.css";
import "../../shared/brand.css";
import "../../shared/account/account.css";
import "./auth.css";

if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/cabinet/sw.js", { scope: "/cabinet/" }).catch(() => {});
  });
}

function CabinetAuth(){
  const [mode,setMode]=useState("login");
  const [channel,setChannel]=useState("email");
  const [identity,setIdentity]=useState("");
  const [code,setCode]=useState("");
  const [sent,setSent]=useState(false);
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  const [registerEmail,setRegisterEmail]=useState("");
  const [registerCode,setRegisterCode]=useState("");
  const [registerStep,setRegisterStep]=useState("email");
  const [offerAccepted,setOfferAccepted]=useState(false);
  const [termsAccepted,setTermsAccepted]=useState(false);
  const [privacyAccepted,setPrivacyAccepted]=useState(false);
  const [registerBusy,setRegisterBusy]=useState(false);
  const authLock=useActionLock();
  const allAccepted=offerAccepted&&termsAccepted&&privacyAccepted;
  const send=()=>authLock(async()=>{setBusy(true);setError("");try{await api(channel==="email"?"/api/auth/send-email-code":"/api/auth/send-telegram-code",{method:"POST",body:JSON.stringify(channel==="email"?{email:identity}:{tg_id:Number(identity)})});setSent(true)}catch(e){setError(e.message)}finally{setBusy(false)}});
  const verify=()=>authLock(async()=>{setBusy(true);setError("");try{const data=await api("/api/auth/verify-code",{method:"POST",body:JSON.stringify(channel==="email"?{channel,email:identity,code}:{channel,tg_id:Number(identity),code})});localStorage.setItem(tokenKey,data.access_token);location.href="/cabinet/"}catch(e){setError(e.message)}finally{setBusy(false)}});
  const startRegistration=()=>authLock(async()=>{setRegisterBusy(true);setError("");try{await api("/api/auth/register",{method:"POST",body:JSON.stringify({email:registerEmail,offer_accepted:offerAccepted,terms_accepted:termsAccepted,privacy_accepted:privacyAccepted})});setRegisterStep("code")}catch(e){setError(e.message)}finally{setRegisterBusy(false)}});
  const completeRegistration=()=>authLock(async()=>{setRegisterBusy(true);setError("");try{const data=await api("/api/auth/register/verify",{method:"POST",body:JSON.stringify({email:registerEmail,code:registerCode})});localStorage.setItem(tokenKey,data.access_token);location.href="/cabinet/"}catch(e){setError(e.message)}finally{setRegisterBusy(false)}});
  const changeMode=next=>{setMode(next);setError("")};
  return <main className="auth-page" onKeyDown={event=>{
    if(event.key!=="Enter"||event.target.tagName!=="INPUT"||event.target.type==="checkbox"||busy||registerBusy)return;
    event.preventDefault();
    if(mode==="login") { if(sent){if(code.length===6)verify();}else if(channel==="email"?/^\S+@\S+\.\S+$/.test(identity.trim()):/^\d+$/.test(identity.trim()))send(); }
    else if(registerStep==="email"){if(allAccepted&&/^\S+@\S+\.\S+$/.test(registerEmail.trim()))startRegistration();}
    else if(registerCode.length===6)completeRegistration();
  }}>{error&&<CabinetToast message={error} kind="error" onClose={()=>setError("")}/>}
    <header className="auth-site-header">
      <a className="brand" href="https://lunet.pro/"><img src="/miniapp/assets/lunet-logo.png" alt="" width="34" height="34"/><b>Lunet<span>VPS</span></b></a>
      <nav className="auth-site-nav" aria-label="Сайт Lunet"><a href="https://lunet.pro/#about">О сервисе</a><a href="https://lunet.pro/#how">Инструкции</a><a href="https://lunet.pro/#plans">Тарифы</a><a href="https://t.me/LunetVPNSupport" target="_blank" rel="noopener noreferrer">Поддержка</a></nav>
    </header>
    <section className="auth-panel">
      <div className="auth-main">
        <nav className="auth-topline" aria-label="Навигация"><a href="https://lunet.pro/"><ArrowLeft size={15}/><span>Главная</span></a><a className="auth-desktop-support" href="https://t.me/LunetVpnSupport" target="_blank" rel="noopener noreferrer">Поддержка</a></nav>
        <div className="auth-form">
          <h1 aria-label={mode==="login"?"Вход в кабинет":"Создать аккаунт"}>{mode==="login"?"Вход":"Регистрация"}</h1>
          <p className="auth-description">{mode==="login"?(sent?"Введи код из сообщения, чтобы войти в аккаунт.":channel==="email"?"Войди в аккаунт и продолжай пользоваться Lunet. Мы отправим код на твою почту.":"Введи Telegram ID. Код придёт в бот Lunet."):registerStep==="email"?"Создай аккаунт Lunet — всё для подключения в одном месте.":"Подтверди почту, чтобы завершить регистрацию."}</p>
          {mode==="login"?<>
            {sent?<><div className="registration-email"><Mail size={18}/><div><span>Код отправлен {channel==="email"?"на почту":"в Telegram"}</span><b>{identity}</b></div></div><Field label="Код подтверждения" className="auth-code-input" inputMode="numeric" autoComplete="one-time-code" value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,"").slice(0,6))} maxLength={6} placeholder="000000" autoFocus/><Button onClick={verify} disabled={code.length!==6||busy} loading={busy}>Войти в аккаунт</Button><button className="auth-text-link" type="button" disabled={busy} onClick={()=>setSent(false)}>Изменить {channel==="email"?"почту":"Telegram ID"}</button></>:<><Field label={channel==="email"?"Почта":"Telegram ID"} type={channel==="email"?"email":"text"} inputMode={channel==="email"?"email":"numeric"} autoComplete={channel==="email"?"email":"off"} value={identity} onChange={e=>setIdentity(e.target.value)} placeholder={channel==="email"?"Ваш Email":"Ваш Telegram ID"}/><Button onClick={send} disabled={busy||(channel==="email"?!/^\S+@\S+\.\S+$/.test(identity.trim()):!/^\d+$/.test(identity.trim()))} loading={busy}>Получить код</Button><p className="auth-code-note">Вход по одноразовому коду</p></>}
            <div className="auth-divider"><span>или</span></div>
            <Button className="auth-telegram-button" disabled={busy} onClick={()=>{setChannel(channel==="email"?"telegram":"email");setIdentity("");setCode("");setSent(false);setError("");}}>{channel==="email"?<Send size={20}/>:<Mail size={20}/>} {channel==="email"?"Войти через Telegram":"Войти через почту"}</Button>
            <button type="button" className="auth-text-link" aria-label="Регистрация" disabled={busy} onClick={()=>changeMode("register")}>Нет аккаунта? Зарегистрироваться</button>
          </>:<>
            {registerStep==="email"?<><Field label="Почта" type="email" value={registerEmail} onChange={e=>setRegisterEmail(e.target.value)} placeholder="Ваш Email" autoComplete="email"/>
              <div className="legal-consents">
                <label className="legal-consent"><input type="checkbox" checked={offerAccepted} onChange={e=>setOfferAccepted(e.target.checked)}/><span>Я принимаю <a href="/terms/offer/" target="_blank" rel="noreferrer">оферту</a></span></label>
                <label className="legal-consent"><input type="checkbox" checked={termsAccepted} onChange={e=>setTermsAccepted(e.target.checked)}/><span>Я принимаю <a href="/terms/" target="_blank" rel="noreferrer">пользовательское соглашение</a></span></label>
                <label className="legal-consent"><input type="checkbox" checked={privacyAccepted} onChange={e=>setPrivacyAccepted(e.target.checked)}/><span>Я принимаю <a href="/terms/privacy/" target="_blank" rel="noreferrer">политику конфиденциальности</a></span></label>
              </div>
              <Button loading={registerBusy} disabled={!/^\S+@\S+\.\S+$/.test(registerEmail.trim())||!allAccepted} onClick={startRegistration}>Получить код</Button>
            </>:<><div className="registration-email"><Mail size={18}/><div><span>Код отправлен на почту</span><b>{registerEmail}</b></div></div><Field label="Код подтверждения" className="auth-code-input" inputMode="numeric" value={registerCode} onChange={e=>setRegisterCode(e.target.value.replace(/\D/g,"").slice(0,6))} maxLength={6} placeholder="000000" autoComplete="one-time-code"/><Button loading={registerBusy} disabled={registerCode.length!==6} onClick={completeRegistration}>Создать аккаунт</Button><button className="auth-text-link" type="button" disabled={registerBusy} onClick={()=>setRegisterStep("email")}>Изменить почту</button></>}
            <button className="auth-text-link" type="button" aria-label="Вход" disabled={registerBusy} onClick={()=>changeMode("login")}>Есть аккаунт? Войти</button>
          </>}
        </div>
      </div>
      <aside className="auth-showcase" aria-label="Личный кабинет Lunet"><a className="brand" href="https://lunet.pro/"><img src="/miniapp/assets/lunet-logo.png" alt="" width="42" height="42"/><b>Lunet VPS</b></a><p>Твой интернет.<br/>Твои правила.</p><div className="auth-phone" aria-hidden="true"><div className="auth-phone-camera"/><img src={authPreview} alt="" width="390" height="844"/></div><span className="auth-preview-note">Интерфейс кабинета · демо-данные</span></aside>
    </section>
    <CookieNotice/>
  </main>;
}
function CabinetNotFound(){return <NotFound description="Проверьте адрес или вернитесь в личный кабинет." href="/cabinet/" action="Вернуться в кабинет"/>}
const checkCabinetSession = () => api("/api/auth/me", { method:"GET" });
function App(){const pathname=location.pathname.replace(/\/$/,"")||"/";return <>{pathname==="/cabinet/login"?<CabinetAuth/>:pathname==="/cabinet"?<SessionGate check={checkCabinetSession}><Cabinet/></SessionGate>:<CabinetNotFound/>}</>}
createRoot(document.getElementById("root")).render(<App/>);
