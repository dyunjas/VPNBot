import React, { useState } from "react";
import { Gift, LoaderCircle } from "lucide-react";

function Spinner() { return <LoaderCircle className="button-spinner" size={16} role="status" aria-label="Loading" />; }

const T = {
  payments: "\u041f\u043b\u0430\u0442\u0435\u0436\u0438",
  description: "\u041f\u043e\u043f\u043e\u043b\u043d\u044f\u0439\u0442\u0435 \u0431\u0430\u043b\u0430\u043d\u0441 \u0438 \u043e\u043f\u043b\u0430\u0447\u0438\u0432\u0430\u0439\u0442\u0435 \u043f\u043e\u0434\u043f\u0438\u0441\u043a\u0443.",
  topup: "\u041f\u043e\u043f\u043e\u043b\u043d\u0438\u0442\u044c \u0431\u0430\u043b\u0430\u043d\u0441",
  choose: "\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0441\u0443\u043c\u043c\u0443 \u0438 \u0441\u043f\u043e\u0441\u043e\u0431 \u043e\u043f\u043b\u0430\u0442\u044b.",
  amount: "\u0421\u0443\u043c\u043c\u0430, \u20bd",
  method: "\u0421\u043f\u043e\u0441\u043e\u0431 \u043e\u043f\u043b\u0430\u0442\u044b",
  pay: "\u041f\u0435\u0440\u0435\u0439\u0442\u0438 \u043a \u043e\u043f\u043b\u0430\u0442\u0435",
  promo: "\u0410\u043a\u0442\u0438\u0432\u0430\u0446\u0438\u044f \u043f\u0440\u043e\u043c\u043e\u043a\u043e\u0434\u0430",
  promoText: "\u0412\u0432\u0435\u0434\u0438\u0442\u0435 \u043a\u043e\u0434, \u0447\u0442\u043e\u0431\u044b \u043f\u043e\u043b\u0443\u0447\u0438\u0442\u044c \u0431\u043e\u043d\u0443\u0441 \u043d\u0430 \u0431\u0430\u043b\u0430\u043d\u0441.",
  promoPlaceholder: "\u0412\u0432\u0435\u0434\u0438\u0442\u0435 \u043f\u0440\u043e\u043c\u043e\u043a\u043e\u0434",
  apply: "\u0410\u043a\u0442\u0438\u0432\u0438\u0440\u043e\u0432\u0430\u0442\u044c",
  gift: "\u041f\u043e\u0434\u0430\u0440\u0438\u0442\u044c \u043f\u043e\u0434\u043f\u0438\u0441\u043a\u0443",
  giftText: "\u0423\u043a\u0430\u0436\u0438\u0442\u0435 username \u0438\u043b\u0438 Telegram ID \u043f\u043e\u043b\u0443\u0447\u0430\u0442\u0435\u043b\u044f.",
  giftHint: "\u0412\u044b\u0431\u043e\u0440 \u0442\u0430\u0440\u0438\u0444\u0430 \u0434\u043e\u0441\u0442\u0443\u043f\u0435\u043d \u0432 \u0440\u0430\u0437\u0434\u0435\u043b\u0435 \u00ab\u0422\u0430\u0440\u0438\u0444\u044b\u00bb.",
  giftButton: "\u041f\u043e\u0434\u0430\u0440\u0438\u0442\u044c",
  created: "\u0421\u0447\u0451\u0442 \u0441\u043e\u0437\u0434\u0430\u043d",
  activated: "\u041f\u0440\u043e\u043c\u043e\u043a\u043e\u0434 \u0430\u043a\u0442\u0438\u0432\u0438\u0440\u043e\u0432\u0430\u043d",
};

const initData = () => window.Telegram?.WebApp?.initData || new URLSearchParams(location.search).get("initData") || "";
async function request(path, body) {
  const response = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ initData: initData(), ...body }) });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw Error(data.detail || data.error || `Error ${response.status}`);
  return data;
}

export function Billing({ plans = [], onMessage }) {
  const [amount, setAmount] = useState(500), [promo, setPromo] = useState(""), [method, setMethod] = useState("platega-card"), [recipient, setRecipient] = useState(""), [giftPlan, setGiftPlan] = useState(""), [busy, setBusy] = useState("");
  const methods = [["platega-card", "\u041a\u0430\u0440\u0442\u0430", "Platega", "platega", "card", "pay-mir.png"], ["platega-sbp", "\u0421\u0411\u041f #2", "Platega", "platega", "sbp", "pay-sbp.png"], ["pally", "\u0421\u0411\u041f #1", "Pally", "pally", undefined, "pay-sbp.png"], ["crypto", "\u041a\u0440\u0438\u043f\u0442\u043e\u0432\u0430\u043b\u044e\u0442\u0430", "CryptoBot", "crypto", undefined, "pay-usdt.png"]];
  const selected = methods.find((item) => item[0] === method) || methods[0];
  const run = async (action, message, key) => { setBusy(key); try { await action(); onMessage?.(message); } catch (error) { onMessage?.(error.message); } finally { setBusy(false); } };
  return <div className="view-stack">
    <div><p className="eyebrow">{T.payments}</p><h1 className="page-heading">{T.payments}</h1><p className="page-description">{T.description}</p></div>
    <section className="card card-pad billing-card"><h2>{T.topup}</h2><p className="card-subtitle">{T.choose}</p><label className="field"><span>{T.amount}</span><input type="number" min="1" value={amount} onChange={(event) => setAmount(event.target.value)} /></label><div className="field"><span>{T.method}</span><div className="payment-options">{methods.map((item) => <button type="button" key={item[0]} className={selected[0] === item[0] ? "payment-option active" : "payment-option"} onClick={() => setMethod(item[0])}><span className="payment-mark"><img src={`/miniapp/assets/${item[5]}`} alt="" /></span><span><b>{item[1]}</b><small>{item[2]}</small></span><span className="radio-dot" /></button>)}</div></div><button className="button button-primary full-width" disabled={busy === "topup" || Number(amount) <= 0} onClick={() => run(async () => { const data = await request("/api/balance/topup", { amount: Number(amount), method: selected[3], platega_type: selected[4] }); if (data.payment_url) location.href = data.payment_url; }, T.created, "topup")}>{busy === "topup" && <Spinner />}{T.pay}</button></section>
    <section className="card card-pad billing-card"><h2>{T.promo}</h2><p className="card-subtitle">{T.promoText}</p><div className="promo-input-row"><input className="promo-input" placeholder={T.promoPlaceholder} value={promo} onChange={(event) => setPromo(event.target.value)} /><button className="button button-secondary" disabled={busy === "promo" || !promo.trim()} onClick={() => run(async () => { await request("/api/promocode/apply", { code: promo }); setPromo(""); }, T.activated, "promo")}>{busy === "promo" && <Spinner />}{T.apply}</button></div></section>
    <section className="card card-pad billing-card"><h2>{T.gift}</h2><p className="card-subtitle">{T.giftText}</p><div className="gift-form"><input placeholder="@username \u0438\u043b\u0438 Telegram ID" value={recipient} onChange={(event) => setRecipient(event.target.value)} /><select value={giftPlan} onChange={(event) => setGiftPlan(event.target.value)}><option value="">\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0442\u0430\u0440\u0438\u0444</option>{plans.map((plan) => <option value={plan.id} key={plan.id}>{plan.name} \u2014 {plan.price} \u20bd</option>)}</select><button className="button button-primary full-width" disabled={busy === "gift" || !recipient.trim() || !giftPlan} onClick={() => run(async () => { await request("/api/subscription/gift", { recipient, plan_id: Number(giftPlan) }); setRecipient(""); setGiftPlan(""); }, "\u041f\u043e\u0434\u0430\u0440\u043e\u043a \u043e\u0442\u043f\u0440\u0430\u0432\u043b\u0435\u043d", "gift")}>{busy === "gift" && <Spinner />}{T.giftButton}</button></div></section>
  </div>;
}
