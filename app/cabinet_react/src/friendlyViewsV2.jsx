import React, { useEffect, useState } from "react";
import { Apple, LoaderCircle, Monitor, Smartphone, ShieldCheck, TabletSmartphone, Trash2 } from "lucide-react";

const formatDate = (value) => value ? new Date(value).toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" }) : "Дата не указана";
const formatGb = (value) => `${(Number(value || 0) / 1024 ** 3).toFixed(1)} ГБ`;

export function FriendlyOverview({ user, status, onNavigate }) {
  const sub = status?.subscription || {};
  return <div className="stack friendly-overview">
    <section className="card balance-card"><div className="section-kicker">БАЛАНС</div><strong>{user.balance || 0} ₽</strong><button className="button balance-button" onClick={() => onNavigate("billing")}>Пополнить</button></section>
    <section className="card profile-summary"><div><span>Пользователь</span><b>{user.username ? `@${user.username}` : "Не указан"}</b></div><div><span>Почта</span><b>{user.email || "Не указана"}</b></div><div><span>Telegram ID</span><b>{user.tg_id || "—"}</b></div><div className="profile-support"><span>Поддержка</span><div className="support-links"><a href="https://t.me/LunetVpnSupport" target="_blank" rel="noreferrer">@LunetVpnSupport</a><a href="mailto:support@lunet.pro">support@lunet.pro</a></div></div></section>
    <section className="card subscription-preview"><div className="card-head"><div><h2>Подписка</h2><p className="muted">{status?.has_subscription ? `Действует до ${formatDate(sub.current_period_end)}` : "Активной подписки нет"}</p></div><span className={`badge ${status?.has_subscription ? "ok" : "muted-badge"}`}>{status?.has_subscription ? "Активна" : "Неактивна"}</span></div><button className="button button-primary" onClick={() => onNavigate(status?.has_subscription ? "subscription" : "plans")}>Подробнее</button></section>
  </div>;
}

export function FriendlySubscription({ status, onNavigate, onAutoRenewChange }) {
  const sub = status?.subscription || {};
  const remote = status?.remnawave || {};
  const active = Boolean(status?.has_subscription);
  const [autoRenew, setAutoRenew] = useState(Boolean(sub.auto_renew));
  const [autoRenewBusy, setAutoRenewBusy] = useState(false);
  useEffect(() => setAutoRenew(Boolean(sub.auto_renew)), [sub.auto_renew]);
  const toggleAutoRenew = async () => {
    if (!active || autoRenewBusy) return;
    const next = !autoRenew;
    setAutoRenewBusy(true);
    const changed = await onAutoRenewChange(next);
    if (changed) setAutoRenew(next);
    setAutoRenewBusy(false);
  };
  const limit = Number(remote.trafficLimitBytes || 0);
  const used = Number(remote.usedTrafficBytes || 0);
  const percent = limit ? Math.min(100, Math.round(used / limit * 100)) : 0;
  return <div className="subscription-layout"><section className="card subscription-main"><div className="subscription-page-title"><div className="section-kicker">ПОДПИСКА</div><h2>Моя подписка</h2><p className="muted">Понятная информация о вашем доступе.</p></div>{active ? <><div className="subscription-banner"><ShieldCheck size={22}/><b>Подписка активна</b></div><div className="friendly-details"><div><span>Срок действия</span><b>До {formatDate(sub.current_period_end)}</b></div><div><span>Устройства</span><b>{sub.devices_used || 0} / {sub.devices_limit || "без ограничений"}</b></div><div><span>Статус</span><b>Активна</b></div>{limit > 0 && <div><span>Трафик</span><b>{formatGb(used)} из {formatGb(limit)} ({percent}%)</b></div>}</div><div className="auto-renew-row"><div><b>Автоматическое продление</b><span>{autoRenew ? "Подписка продлится автоматически при достаточном балансе." : "Автоматическое продление выключено."}</span></div><button type="button" className={`auto-renew-switch${autoRenew ? " active" : ""}`} role="switch" aria-checked={autoRenew} aria-label="Автоматическое продление" disabled={autoRenewBusy} onClick={toggleAutoRenew}>{autoRenewBusy ? <LoaderCircle className="spin" size={16}/> : <span/>}</button></div></> : <div className="empty subscription-empty"><ShieldCheck size={25}/><b>Активной подписки пока нет</b><span>Выберите тариф, чтобы подключить VPN.</span></div>}<button className="button button-primary subscription-action" onClick={() => onNavigate("plans")}>{active ? "Продлить подписку" : "Выбрать тариф"}</button></section></div>;
}

const deviceIcon = (os = "") => /ios|mac/i.test(os) ? Apple : /windows|desktop|linux|mac/i.test(os) ? Monitor : /tablet/i.test(os) ? TabletSmartphone : Smartphone;
export function FriendlyDevices({ devices, remove }) { return <section className="card devices-card"><div className="card-head"><div><div className="section-kicker">УСТРОЙСТВА</div><h2>Мои устройства</h2><p className="muted">Управляйте устройствами, использующими подписку.</p></div></div>{devices.length ? <div className="friendly-device-list">{devices.map((device, index) => { const Icon = deviceIcon(device.device_os || device.user_agent); return <div className="friendly-device" key={device.id ?? index}><div className="device-icon"><Icon size={19}/></div><div className="device-info"><b>{device.device_model || "Мобильное устройство"}</b><span>{device.device_os || "Операционная система не определена"}</span></div><button className="device-remove" onClick={() => remove(device.id)}><Trash2 size={16}/><span>Удалить</span></button></div>; })}</div> : <div className="empty"><Smartphone size={24}/><span>Подключённых устройств пока нет</span></div>}</section>; }
