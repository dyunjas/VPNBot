import { useEffect } from "react";
import { Check, Info, AlertCircle, X } from "lucide-react";
import { LunetLoader, ModalFrame } from "../controls.jsx";

export function Button({children,variant="primary",loading=false,className="",...props}) {
  return <button {...props} type={props.type||"button"} className={`button button-${variant} ${className}`} disabled={loading||props.disabled} aria-busy={loading||undefined}>{loading&&<LunetLoader/>}{children}</button>;
}
export function Card({children,className=""}) {return <section className={`card ${className}`}>{children}</section>;}
export function AccountIdentitySkeleton() {
  return <div className="account-identity account-identity-loading" role="status" aria-label="Загрузка профиля" aria-busy="true">
    <span className="lunet-sr-only">Загрузка профиля</span>
    <span className="account-avatar account-placeholder" aria-hidden="true"/>
    <div className="account-identity-placeholders" aria-hidden="true"><span className="account-name-placeholder account-placeholder"/><span className="account-balance-placeholder account-placeholder"/></div>
  </div>;
}
export function Field({label,...props}) {return <label className="field"><span>{label}</span><input {...props}/></label>;}
export function Empty({Icon,title,children,action}) {return <section className="empty-state">{Icon&&<span className="empty-icon"><Icon size={28}/></span>}<h2>{title}</h2><p>{children}</p>{action}</section>;}
export function Dialog({title,children,onClose,busy=false}) {return <ModalFrame onClose={onClose} busy={busy}><section className="modal" role="dialog" aria-modal="true"><header><h2>{title}</h2><button type="button" className="icon-button" data-dialog-close="true" disabled={busy} aria-label="Закрыть окно"><X size={19}/></button></header>{children}</section></ModalFrame>;}
export function CabinetToast({message,kind,onClose}) {
  useEffect(()=>{if(kind==="error")return;const timer=setTimeout(onClose,5000);return()=>clearTimeout(timer);},[message,kind,onClose]);
  return <Notice className="cabinet-toast" kind={kind} role={kind==="error"?"alert":"status"} onClose={onClose}>{message}</Notice>;
}
export function Notice({children,kind="info",className="",onClose,...props}) {
  const Icon=kind==="error"?AlertCircle:kind==="success"?Check:Info;
  return <div {...props} className={`cabinet-notice notice-${kind} ${className}`}><span className="notice-icon" aria-hidden="true"><Icon size={18}/></span><div className="notice-content">{children}</div>{onClose&&<button className="notice-close" type="button" aria-label="Закрыть уведомление" onClick={onClose}><X size={16}/></button>}</div>;
}
export const money = value => new Intl.NumberFormat("ru-RU",{maximumFractionDigits:2}).format(Number(value)||0);
export const date = value => value && Number.isFinite(new Date(value).getTime()) ? new Date(value).toLocaleDateString("ru-RU",{day:"numeric",month:"long",year:"numeric"}) : "Не указана";
export const gb = bytes => `${new Intl.NumberFormat("ru-RU",{maximumFractionDigits:1}).format(Number(bytes)/1024**3)} ГБ`;
