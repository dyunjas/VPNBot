import { DocumentLinks } from "../../shared/DocumentLinks.jsx";
import { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { ArrowRight, Check, CreditCard, Menu, MessageCircle, Monitor, Plus, ShieldCheck, Smartphone, Wallet, X, Zap } from "lucide-react";
import { LunetLoader, useDialogFocus, useReducedMotion } from "../../shared/controls.jsx";
import "../../shared/controls.css";
import "../../shared/brand.css";
import "./landing.css";
import CookieNotice from "../../shared/CookieNotice.jsx";
import AccountLink, { useLandingAccount } from "./AccountLink.jsx";

const cabinetUrl = "/cabinet/";
const supportUrl = "https://t.me/LunetVPNSupport";
const botUrl = "https://t.me/LunetVpnBot";
const navigation = [["about", "О сервисе"], ["benefits", "Преимущества"], ["plans", "Тарифы"], ["how", "Как подключиться"], ["support", "Поддержка"]];
const money = value => new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 }).format(Number(value));
const benefits = [
  [Zap, "Простое подключение", "Ссылка подписки и понятные инструкции — в твоём кабинете."],
  [Smartphone, "Твои устройства", "Смотри подключённые устройства и управляй их доступом."],
  [CreditCard, "Гибкие тарифы", "Выбирай подходящий срок, лимит LTE-трафика и количество устройств."],
  [Wallet, "Всё в одном кабинете", "Баланс, подписка, платежи и остаток LTE-трафика всегда под рукой."],
  [MessageCircle, "Поддержка рядом", "Обратись в Telegram, если нужна помощь с подключением."],
];
const questions = [
  ["Как подключить Lunet?", "Зарегистрируйся в личном кабинете или открой Telegram-бота. Выбери тариф, пополни баланс и подключи подписку. Затем открой ссылку подключения и следуй инструкции для своего устройства."],
  ["Какие устройства поддерживаются?", "VPN можно настроить на телефоне или компьютере с совместимым VPN-клиентом. Инструкция и доступные приложения указаны на странице подключения. Количество устройств зависит от выбранного тарифа."],
  ["Как продлить подписку?", "Открой раздел «Подписка» в кабинете. Там доступны продление и управление автопродлением. Для оплаты нужен достаточный баланс."],
  ["Как управлять устройствами?", "В разделе «Устройства» отображаются подключённые устройства. Там можно удалить устройство; дополнительные места приобретаются в разделе подписки."],
  ["Где посмотреть остаток LTE-трафика?", "Лимит и использованный LTE-трафик отображаются в разделе «Подписка» кабинета и Telegram Mini App. Дополнительные гигабайты можно приобрести для действующей подписки."],
  ["Как связаться с поддержкой?", "Напиши команде Lunet в Telegram по ссылке ниже. Опиши вопрос и устройство, на котором нужна помощь."],
];

function Button({ href = cabinetUrl, children, secondary = false, className = "", ...props }) {
  return <a className={`button ${secondary ? "button-secondary" : ""} ${className}`} href={href} {...props}>{children}<ArrowRight size={17} aria-hidden="true" /></a>;
}
function Device({ laptop = false, light = false }) {
  return <div className={`device ${laptop ? "laptop" : "phone"} ${light ? "device-light" : ""}`}>
    <div className="device-screen"><img src={laptop ? "/miniapp/assets/cabinet-desktop.webp" : "/miniapp/assets/cabinet-mobile.webp"} alt={laptop ? "Десктопный кабинет Lunet: баланс, подписка и устройства" : "Мобильный кабинет Lunet: обзор подписки"} width={laptop ? 1280 : 390} height={laptop ? 820 : 844} loading={light ? "lazy" : "eager"} /></div>
    {laptop ? <div className="laptop-base" /> : <span className="phone-camera" aria-hidden="true" />}
  </div>;
}
function Infrastructure() {
  return <div className="infrastructure" role="img" aria-label="Иллюстрация: устройства подключены к инфраструктуре Lunet">
    <div className="infra-grid" aria-hidden="true" />
    <div className="infra-heading"><ShieldCheck size={19} /> LUNET NETWORK</div>
    <svg className="infra-lines" viewBox="0 0 500 400" aria-hidden="true"><path d="M100 120H250V290H400M400 120H250M100 290H250"/><circle cx="100" cy="120" r="6"/><circle cx="400" cy="120" r="6"/><circle cx="100" cy="290" r="6"/><circle cx="400" cy="290" r="6"/></svg>
    <div className="server-rack" aria-hidden="true">{[0,1,2,3].map(i=><div className="server-unit" key={i}><span/><span/><b>•••</b><i/></div>)}</div>
    <div className="infra-node node-phone"><Smartphone size={27}/></div><div className="infra-node node-desktop"><Monitor size={27}/></div>
    <div className="infra-caption"><span className="badge"><Check size={14}/> Удобное управление</span><strong>Одно подключение.<br/>Твои устройства.</strong></div>
  </div>;
}
function Faq({ question, answer, index }) {
  const [open, setOpen] = useState(false);
  return <article className={`faq-item ${open ? "is-open" : ""}`}><h3><button type="button" aria-expanded={open} aria-controls={`answer-${index}`} onClick={()=>setOpen(!open)}>{question}<Plus size={21} aria-hidden="true"/></button></h3><div id={`answer-${index}`} className="faq-answer" inert={!open ? true : undefined} aria-hidden={!open}><div><p>{answer}{index===5&&<> <a href={supportUrl} target="_blank" rel="noopener noreferrer">Открыть поддержку <ArrowRight size={14}/></a></>}</p></div></div></article>;
}
function useCatalog() {
  const [state, setState] = useState({ loading: true, plans: [], traffic: null, error: false });
  const [attempt, setAttempt] = useState(0);
  useEffect(()=>{
    const controller = new AbortController();
    const timeout = setTimeout(()=>controller.abort(), 12000);
    let disposed = false;
    setState(s=>({...s, loading:true, error:false}));
    (async()=>{
      let failure;
      for(const url of ["/api/public/catalog","/catalog.json"]){
        try{
          const response=await fetch(url,{signal:controller.signal,cache:"no-store",headers:{Accept:"application/json"}});
          if(!response.ok || !/application\/json/i.test(response.headers.get("content-type")||""))throw new Error("catalog");
          const data=await response.json();
          if(!Array.isArray(data.plans))throw new Error("catalog");
          const plans=data.plans.filter(p=>!p.is_hidden&&Number.isFinite(Number(p.price))&&Number(p.price)>=0);
          if(!disposed)setState({loading:false,plans,traffic:Number(data.traffic_price_per_gb)>0?Number(data.traffic_price_per_gb):null,trafficMinimum:Math.max(1,Number(data.min_traffic_purchase_gb)||1),error:false});
          return;
        }catch(error){failure=error;if(controller.signal.aborted)throw error}
      }
      throw failure;
    })().catch(()=>{if(!disposed)setState({loading:false,plans:[],traffic:null,error:true})}).finally(()=>clearTimeout(timeout));
    return ()=>{disposed=true;clearTimeout(timeout);controller.abort();};
  },[attempt]);
  return {...state, retry:()=>setAttempt(n=>n+1)};
}
function App() {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState("");
  const menu = useRef(null);
  const page = useRef(null);
  const close = ()=>setOpen(false);
  const reducedMotion = useReducedMotion();
  const catalog = useCatalog();
  const user = useLandingAccount();
  useDialogFocus(menu, open, close);
  useEffect(()=>{
    const observer=new IntersectionObserver(entries=>entries.forEach(entry=>{
      if(entry.isIntersecting){entry.target.classList.add("revealed");observer.unobserve(entry.target);}
    }),{threshold:0.08});
    page.current.querySelectorAll("[data-reveal]").forEach(el=>observer.observe(el));
    return ()=>observer.disconnect();
  },[catalog.loading,reducedMotion]);
  useEffect(()=>{
    const observer=new IntersectionObserver(entries=>entries.forEach(entry=>{if(entry.isIntersecting)setActive(entry.target.id==="top"?"":entry.target.id);}),{rootMargin:"-15% 0px -65% 0px",threshold:0});
    observer.observe(document.getElementById("top"));
    navigation.forEach(([id])=>{const el=document.getElementById(id);if(el)observer.observe(el);});
    return ()=>observer.disconnect();
  },[]);
  useEffect(()=>{const resize=()=>{if(innerWidth<=700||innerWidth>1000)setOpen(false);};window.addEventListener("resize",resize);return ()=>window.removeEventListener("resize",resize);},[]);
  const featured = catalog.plans.find(p=>Number(p.period_days)===90)?.id;
  return <div className="landing-shell" ref={page}>
    <a className="skip-link" href="#main">К содержимому</a>
    <header className="navbar container">
      <a className="brand" href="#top" aria-label="Lunet — на главную"><img src="/miniapp/assets/lunet-logo.png" alt="" width="34" height="34"/><b>Lunet<span>VPS</span></b></a>
      <nav className="nav-links" aria-label="Основная навигация">{navigation.map(([id,label])=><a key={id} href={`#${id}`} className={active===id?"active":""} aria-current={active===id?"location":undefined}>{label}</a>)}</nav>
      <AccountLink user={user} className="nav-cabinet"/>
      <button className="menu-button" type="button" onClick={()=>setOpen(!open)} aria-expanded={open} aria-controls="landing-mobile-menu" aria-label={open?"Закрыть меню":"Открыть меню"}>{open?<X size={22}/>:<Menu size={22}/>}</button>
    </header>
    {open&&<><button className="menu-backdrop" onClick={close} aria-label="Закрыть меню"/><div className="mobile-menu" id="landing-mobile-menu" ref={menu} role="dialog" aria-modal="true" aria-label="Навигация"><button className="menu-close" onClick={close} aria-label="Закрыть меню"><X size={20}/></button>{navigation.map(([id,label])=><a key={id} href={`#${id}`} onClick={close}>{label}</a>)}<AccountLink user={user} onClick={close}/></div></>}
    <main id="main">
      <section className="hero container" id="top">
        <span className="badge hero-badge"><span className="brand-dot"/> На связи с Lunet</span>
        <h1>Интернет без границ.<br/><em>Свобода с Lunet.</em></h1>
        <p className="hero-description">Lunet VPS — удобный способ оставаться на связи, пользоваться любимыми сервисами и управлять подключением с любого устройства.</p>
        <div className="hero-actions"><Button>Подключить VPN</Button><Button href="#plans" secondary>Посмотреть тарифы</Button></div>
        <div className="device-composition" aria-label="Интерфейс Lunet на телефоне и компьютере"><Device/><Device laptop/></div>
        <p className="demo-caption">Настоящий интерфейс Lunet · демонстрационные данные</p>
      </section>
      <section className="about section container" id="about" data-reveal>
        <div><span className="badge">Что такое Lunet?</span><h2>Твой интернет.<br/><em>Твои правила.</em></h2><p>Lunet — VPN-сервис с удобным управлением подпиской, поддержкой нескольких устройств и простым подключением.</p><div className="inline-actions"><Button>Подключиться</Button><Button href="#benefits" secondary>Узнать больше</Button></div></div>
        <Infrastructure/>
      </section>
      <section className="control-section container" data-reveal>
        <div className="control-copy"><span className="badge dark-badge"><ShieldCheck size={14}/> Всё под контролем</span><h2>Управляй своим VPN<br/><em>так, как удобно тебе.</em></h2><p>Настраивай подключение, следи за подпиской, управляй устройствами и получай доступ к нужной информации в личном кабинете Lunet.</p><ul className="control-features"><li><Check size={16}/> Подписка и баланс</li><li><Check size={16}/> LTE-трафик и устройства</li><li><Check size={16}/> Веб-кабинет и Telegram Mini App</li></ul><Button>Открыть кабинет</Button></div>
        <div className="control-device"><Device light/></div>
      </section>
      <section className="section container" id="benefits">
        <div className="section-heading" data-reveal><span className="eyebrow">ПРОСТО. ПОНЯТНО. LUNET.</span><h2>Меньше настроек.<br/><em>Больше возможностей.</em></h2></div>
        <div className="benefit-grid">{benefits.map(([Icon,title,text],i)=><article className="benefit-card" key={title} data-reveal style={{"--delay":`${i*45}ms`}}><span className="feature-icon"><Icon size={23}/></span><h3>{title}</h3><p>{text}</p></article>)}</div>
      </section>
      <section className="section container" id="plans">
        <div className="section-heading centered" data-reveal><span className="eyebrow">ТВОЙ ПЛАН НА СВОБОДУ</span><h2>Выбери свой тариф Lunet</h2><p>Подключай подходящий тариф и пользуйся возможностями Lunet.</p></div>
        <div aria-live="polite" aria-busy={catalog.loading}>
          {catalog.loading?<div className="plan-grid plan-loading" role="status" aria-label="Загрузка тарифов">{[0,1,2].map(i=><div className="plan-skeleton" key={i}><LunetLoader size={24}/><span>Загружаем тарифы</span></div>)}</div>:catalog.error?<div className="catalog-message"><h3>Не удалось загрузить тарифы</h3><p>Попробуй ещё раз или посмотри актуальные предложения в кабинете.</p><button className="button" onClick={catalog.retry}>Повторить</button><Button secondary>Открыть кабинет</Button></div>:catalog.plans.length?<div className="plan-grid">{catalog.plans.map((plan,i)=><article className={`plan-card ${plan.id===featured?"featured":""}`} key={plan.id} data-reveal style={{"--delay":`${i%3*65}ms`}}><span className="plan-badge">{plan.id===featured?"Выбор Lunet":"VPN-подписка"}</span><h3>{plan.name}</h3><p>Доступ к Lunet на {plan.period_days} дней.</p><ul><li><Check size={15}/><span>Срок: {plan.period_days} дней</span></li><li><Check size={15}/><span>{Number(plan.gb_limit)>0?`${money(plan.gb_limit)} ГБ LTE-трафика`:"LTE-трафик без ограничений"}</span></li><li><Check size={15}/><span>{Number(plan.device_limit)>0?`До ${plan.device_limit} устройств`:"Устройства без ограничений"}</span></li><li><Check size={15}/><span>Управление в личном кабинете</span></li></ul><div className="plan-bottom"><span className="price-label">Стоимость подписки</span><strong className="plan-price">{money(plan.price)} <span>₽</span></strong><Button>Подключиться</Button></div></article>)}</div>:<div className="catalog-message"><h3>Тарифы пока недоступны</h3><p>Обратись в поддержку, чтобы узнать о подключении.</p><Button href={supportUrl}>Написать в поддержку</Button></div>}
        </div>
        <div className="plans-followup"><Button>Все возможности в кабинете</Button><a href="/cabinet/login/">Уже зарегистрирован? Войти <ArrowRight size={14}/></a></div>
      </section>
      {catalog.traffic!==null&&<section className="traffic-section section container" data-reveal><div><span className="badge"><Plus size={14}/> Дополнение к подписке</span><h2>Нужно больше<br/><em>LTE-трафика?</em></h2><p>Пополняй доступный LTE-трафик, когда это необходимо. Выбери количество гигабайтов в разделе подписки.</p></div><article className="traffic-card"><span className="plan-badge">Дополнительные гигабайты</span><h3>Столько, сколько нужно</h3><p>Для действующей подписки Lunet.</p><div className="traffic-price"><strong>{money(catalog.traffic)} ₽</strong><span>за 1 ГБ</span></div><Button>Добавить LTE-трафик в кабинете</Button><small>{catalog.trafficMinimum>1&&<>Минимум {catalog.trafficMinimum} ГБ. </>}Дополнение к подписке, а не отдельная услуга.</small></article></section>}
      <section className="section container" id="how"><div className="section-heading centered" data-reveal><span className="eyebrow">НАЧНИ С ПРОСТОГО</span><h2>Три шага до подключения</h2><p>От регистрации до настройки — понятный путь.</p></div><div className="steps">{[["01","Зарегистрируйся","Создай аккаунт в веб-кабинете или начни через Telegram-бота."],["02","Выбери тариф","Выбери подходящую подписку и оплати её с баланса."],["03","Настрой VPN","Открой ссылку подписки и следуй инструкции для своего устройства."]].map(([number,title,text],i)=><article className="step-card" key={number} data-reveal style={{"--delay":`${i*65}ms`}}><span className="step-number">{number}</span><h3>{title}</h3><p>{text}</p></article>)}</div><div className="center-action"><Button>Начать подключение</Button><a className="text-link" href={botUrl} target="_blank" rel="noopener noreferrer">Или открыть Telegram-бота <ArrowRight size={15}/></a></div></section>
      <section className="section faq-section container" id="faq" data-reveal><div className="section-heading"><span className="eyebrow">ОТВЕТЫ РЯДОМ</span><h2>Есть вопросы?</h2><p>Всё, что нужно знать перед подключением.</p></div><div className="faq-list">{questions.map(([question,answer],index)=><Faq key={question} question={question} answer={answer} index={index}/>)}</div></section>
      <section className="cta container" id="support" data-reveal><span className="badge dark-badge">ТВОЙ СЛЕДУЮЩИЙ ШАГ</span><h2>Готов попробовать Lunet?</h2><p>Выбери подходящий тариф и настрой VPN за несколько простых шагов.</p><div className="hero-actions"><Button>Подключить Lunet</Button><a className="text-link" href={supportUrl} target="_blank" rel="noopener noreferrer"><MessageCircle size={18}/> Написать в поддержку</a></div></section>
    </main>
    <footer><div className="footer-main container"><div className="footer-brand"><a className="brand" href="#top"><img src="/miniapp/assets/lunet-logo.png" alt="" width="34" height="34"/><b>Lunet<span>VPS</span></b></a><p>Твой интернет. Твои правила.<br/>Подписка и устройства в одном кабинете.</p></div><nav className="footer-links" aria-label="Сервис"><a href={cabinetUrl}>Личный кабинет</a><a href="#plans">Тарифы</a><a href="#how">Как подключиться</a><a href={botUrl} target="_blank" rel="noopener noreferrer">Telegram-бот</a></nav><nav className="footer-links" aria-label="Помощь и документы"><a href={supportUrl} target="_blank" rel="noopener noreferrer">Поддержка</a><a href="#faq">Частые вопросы</a><DocumentLinks/></nav></div><div className="footer-bottom container"><span>© {new Date().getFullYear()} Lunet</span><span>На связи. С любого устройства.</span></div></footer>
    <CookieNotice/>
  </div>;
}
createRoot(document.getElementById("root")).render(<App/>);
