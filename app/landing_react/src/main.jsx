import React, { useState } from "react";
import { ArrowRight, Check, ChevronDown, Globe2, Menu, MessageCircle, ShieldCheck, Sparkles, X, Zap } from "lucide-react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const botUrl = "https://t.me/LunetVpnBot";
const supportUrl = "https://t.me/LunetVPNSupport";
const locations = ["Россия", "Италия", "Швейцария", "Финляндия", "Германия", "Турция", "Япония"];
const steps = [["01", "Выберите способ подключения", "Откройте Telegram-бота или личный кабинет и выберите подходящий тариф."], ["02", "Получите доступ", "После оплаты ссылка на подключение появится сразу — без сложной ручной настройки."], ["03", "Пользуйтесь свободно", "Управляйте подпиской, устройствами и трафиком в одном удобном кабинете."]];

function Button({ href, children, secondary = false }) { return <a className={`button ${secondary ? "button-secondary" : ""}`} href={href}>{children}<ArrowRight size={16} /></a>; }
function App() {
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);
  return <div className="landing-shell">
    <header className="navbar">
      <a className="brand" href="#top"><img src="/miniapp/assets/lunet-logo.png" alt="Lunet" /><span><b>Lunet</b><small>Личный кабинет</small></span></a>
      <nav className="nav-links"><a href="#locations">Локации</a><a href="#how">Как это работает</a><a href="#faq">Вопросы</a></nav>
      <div className="nav-actions"><a className="support-link" href={supportUrl} target="_blank" rel="noreferrer">Поддержка</a><Button href={botUrl}>Подключиться</Button></div>
      <button className="menu-button" onClick={() => setOpen(!open)} aria-label={open ? "Закрыть меню" : "Открыть меню"}>{open ? <X size={20} /> : <Menu size={20} />}</button>
    </header>
    {open && <><button className="menu-backdrop" onClick={close} aria-label="Закрыть меню" /><div className="mobile-menu"><a href="#locations" onClick={close}>Локации</a><a href="#how" onClick={close}>Как это работает</a><a href="#faq" onClick={close}>Вопросы</a><a href={supportUrl} target="_blank" rel="noreferrer">Поддержка</a><Button href={botUrl}>Подключиться</Button></div></>}

    <main id="top">
      <section className="hero">
        <div className="hero-copy"><div className="eyebrow"><Sparkles size={14} /> LUNET VPN</div><h1>Стабильный доступ к интернету без лишних настроек</h1><p>Подключайтесь к нужному региону за пару минут. Управляйте тарифом, устройствами и трафиком в одном месте.</p><div className="hero-actions"><Button href={botUrl}>Начать подключение</Button><Button href="#how" secondary>Узнать больше</Button></div><div className="trust-row"><span><Check size={15} /> Быстрый старт</span><span><Check size={15} /> 7+ локаций</span><span><Check size={15} /> Поддержка в Telegram</span></div></div>
        <div className="hero-card"><div className="hero-card-head"><span className="status-dot" /> Сервис работает стабильно</div><div className="hero-orb"><ShieldCheck size={42} /></div><div className="hero-card-title">Ваш доступ под контролем</div><p>Все настройки подписки — в личном кабинете.</p><div className="mini-metrics"><div><b>7+</b><span>локаций</span></div><div><b>24/7</b><span>поддержка</span></div><div><b>1 клик</b><span>до старта</span></div></div></div>
      </section>
      <section className="feature-strip"><div><Globe2 size={20}/><span><b>Локации по всему миру</b><small>Выбирайте подходящий регион</small></span></div><div><Zap size={20}/><span><b>Быстрое подключение</b><small>Без сложных инструкций</small></span></div><div><ShieldCheck size={20}/><span><b>Понятное управление</b><small>Тариф и устройства в кабинете</small></span></div></section>
      <section className="section" id="locations"><div className="section-heading"><div><div className="eyebrow">ГЕОГРАФИЯ</div><h2>Выберите удобную локацию</h2></div><p>Подключайтесь к серверам в нужном регионе и меняйте направление в любое время.</p></div><div className="location-grid">{locations.map((name, i) => <div className="location-card" key={name}><span className="location-number">0{i + 1}</span><Globe2 size={19}/><b>{name}</b><small>Доступно для подключения</small></div>)}</div></section>
      <section className="section how-section" id="how"><div className="section-heading"><div><div className="eyebrow">ПРОСТОЙ СТАРТ</div><h2>Подключение в три шага</h2></div><p>Ничего лишнего: выберите тариф, оплатите и откройте готовую ссылку.</p></div><div className="steps">{steps.map(([number, title, text]) => <article className="step-card" key={number}><span>{number}</span><h3>{title}</h3><p>{text}</p></article>)}</div></section>
      <section className="cta" id="faq"><div><div className="eyebrow">ГОТОВЫ НАЧАТЬ?</div><h2>Подключите Lunet сегодня</h2><p>Откройте Telegram-бота или задайте вопрос поддержке — мы поможем разобраться.</p></div><div className="cta-actions"><Button href={botUrl}>Открыть бота</Button><a className="text-button" href={supportUrl} target="_blank" rel="noreferrer"><MessageCircle size={17}/> Написать в поддержку</a></div></section>
    </main>
    <footer><div className="footer-brand"><img src="/miniapp/assets/lunet-logo.png" alt="Lunet"/><b>Lunet</b><small>Стабильный доступ каждый день</small></div><div className="footer-links"><a href="/terms/">Документы</a><a href={supportUrl} target="_blank" rel="noreferrer">Поддержка</a><span>© Lunet 2026</span></div></footer>
  </div>;
}
createRoot(document.getElementById("root")).render(<App />);
