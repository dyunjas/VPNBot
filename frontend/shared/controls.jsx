import { useEffect, useId, useRef, useState } from "react";

// Amicro AppleRadialSpinner: same eight bars, geometry and staggered fade.
// See AMICRO-NOTICE.md. CSS is scoped and uses the surrounding Lunet color.
export function LunetLoader({ size = 16, label = "Загрузка", className = "" }) {
  return <span className={`lunet-loader ${className}`} style={{ width: size, height: size, "--lunet-loader-size": `${size}px` }} role="status" aria-label={label}>
    <span className="lunet-loader-stage" aria-hidden="true">{Array.from({ length: 8 }, (_, i) =>
      <span className="lunet-loader-bar" key={i} style={{ transform: `translateX(-50%) rotate(${i * 45}deg)`, animationDelay: `${i * .1 - .8}s` }} />
    )}</span>
  </span>;
}

// Amicro SkeletonLoader opacity sequence, adapted to real content-sized cards.
export function LunetSkeleton({ label = "Загрузка данных…", rows = 3, variant = "list" }) {
  return <div className={`lunet-skeleton lunet-skeleton-${variant}`} role="status" aria-label={label}>
    <span className="lunet-sr-only">{label}</span>
    {Array.from({ length: rows }, (_, i) => <div className="lunet-skeleton-card" aria-hidden="true" key={i}>
      <span className="lunet-skeleton-circle" />
      <div><span className="lunet-skeleton-line" /><span className="lunet-skeleton-line" /><span className="lunet-skeleton-line" /></div>
    </div>)}
  </div>;
}

export function useReducedMotion() {
  const [reduced, setReduced] = useState(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const change = () => setReduced(media.matches);
    media.addEventListener("change", change);
    return () => media.removeEventListener("change", change);
  }, []);
  return reduced;
}

// A synchronous lock also covers two clicks before React commits disabled state.
export function useActionLock() {
  const locked = useRef(false);
  return async (action) => {
    if (locked.current) return;
    locked.current = true;
    try { return await action(); } finally { locked.current = false; }
  };
}

export function useDialogFocus(ref, open, onClose, busy = false) {
  const latest = useRef({ onClose, busy });
  latest.current = { onClose, busy };
  useEffect(() => {
    if (!open || !ref.current) return;
    const panel = ref.current;
    const previous = document.activeElement;
    const scroll = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusables = () => [...panel.querySelectorAll('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]')].filter(el => el.getClientRects().length);
    panel.tabIndex = -1;
    (focusables()[0] || panel).focus();
    const key = (e) => {
      const topDialog = [...document.querySelectorAll(".dialog-backdrop")].at(-1);
      if (topDialog && topDialog !== panel) return;
      if (e.key === "Escape") { e.preventDefault(); if (!latest.current.busy) latest.current.onClose(); }
      if (e.key === "Tab") {
        const list = focusables(), first = list[0], last = list.at(-1);
        if (!first) { e.preventDefault(); panel.focus(); }
        else if (e.shiftKey && (document.activeElement === first || !panel.contains(document.activeElement))) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && (document.activeElement === last || !panel.contains(document.activeElement))) { e.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener("keydown", key);
    return () => { document.body.style.overflow = scroll; document.removeEventListener("keydown", key); if (previous?.isConnected) previous.focus(); };
  }, [open, ref]);
}

export function ModalFrame({ children, onClose, busy = false }) {
  const ref = useRef(null);
  const titleId = useId();
  const [closing, setClosing] = useState(false);
  const timer = useRef(null);
  const reduced = useReducedMotion();
  const close = () => {
    if (busy || closing) return;
    if (reduced) { onClose(); return; }
    setClosing(true); timer.current = setTimeout(onClose, 140);
  };
  useEffect(() => () => clearTimeout(timer.current), []);
  useDialogFocus(ref, true, close, busy);
  useEffect(() => {
    const dialog = ref.current?.querySelector('[role="dialog"]');
    const title = dialog?.querySelector("h2");
    if (title && !dialog.hasAttribute("aria-labelledby")) { title.id = titleId; dialog.setAttribute("aria-labelledby", titleId); }
  }, [titleId]);
  return <div className={`dialog-backdrop${closing ? " lunet-dialog-closing" : ""}`} ref={ref} aria-busy={busy || undefined} onMouseDown={e => { if (e.target === e.currentTarget) close(); }} onClickCapture={e => {
    if (e.target.closest("button")?.getAttribute("data-dialog-close") === "true") { e.preventDefault(); e.stopPropagation(); close(); }
  }}>{children}</div>;
}

export function CopyValue({ value, label = "Копировать" }) {
  const [result, setResult] = useState("");
  const timer = useRef(null);
  useEffect(() => () => clearTimeout(timer.current), []);
  const copy = async () => {
    try { await navigator.clipboard.writeText(String(value)); setResult("Скопировано"); }
    catch { setResult("Не удалось скопировать"); }
    clearTimeout(timer.current); timer.current = setTimeout(() => setResult(""), 2500);
  };
  return <span className="lunet-copy"><span>{value || "—"}</span>{value && <button type="button" className="lunet-copy-button" onClick={copy} aria-label={`${label}: ${value}`}>Копировать</button>}<span className="lunet-sr-only" role="status">{result}</span>{result && <small>{result}</small>}</span>;
}

export function SubscriptionNotice({ end }) {
  const remaining = end ? Math.ceil((new Date(end).getTime() - Date.now()) / 86400000) : NaN;
  if (!Number.isFinite(remaining) || remaining > 3) return null;
  return <p className="lunet-expiry" role="status">{remaining <= 0 ? "Срок подписки истёк. Проверьте статус и продлите доступ." : `Подписка заканчивается через ${remaining} дн. Продлите доступ заранее.`}</p>;
}
