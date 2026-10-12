import { useEffect, useRef } from "react";

export function useTelegramViewport(view, onBack) {
  const latestBack = useRef(onBack);
  latestBack.current = onBack;
  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    const root = document.documentElement;
    const safe = () => {
      for (const [prefix, values] of [["safe-area", tg?.safeAreaInset], ["content-safe-area", tg?.contentSafeAreaInset]]) {
        for (const edge of ["top", "bottom", "left", "right"]) root.style.setProperty(`--tg-${prefix}-inset-${edge}`, `${Math.max(0, Number(values?.[edge] || 0))}px`);
      }
    };
    const keyboard = () => {
      const focused = /INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName || "");
      const height = window.visualViewport?.height || window.innerHeight;
      root.classList.toggle("lunet-keyboard-open", focused && window.innerHeight - height > 120);
    };
    tg?.ready?.(); tg?.expand?.();
    if(tg?.isVersionAtLeast?.("6.1")){tg.setHeaderColor?.("#ffffff");tg.setBackgroundColor?.("#ffffff");}
    safe(); keyboard();
    tg?.onEvent?.("safeAreaChanged", safe); tg?.onEvent?.("contentSafeAreaChanged", safe);
    tg?.onEvent?.("viewportChanged", keyboard);
    window.visualViewport?.addEventListener("resize", keyboard);
    document.addEventListener("focusin", keyboard); document.addEventListener("focusout", keyboard);
    return () => {
      tg?.offEvent?.("safeAreaChanged", safe); tg?.offEvent?.("contentSafeAreaChanged", safe); tg?.offEvent?.("viewportChanged", keyboard);
      window.visualViewport?.removeEventListener("resize", keyboard);
      document.removeEventListener("focusin", keyboard); document.removeEventListener("focusout", keyboard);
      root.classList.remove("lunet-keyboard-open");
    };
  }, []);
  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    if (!tg?.isVersionAtLeast?.("6.1")) return;
    const back = tg.BackButton;
    const handler = () => latestBack.current();
    if (view === "home" || view === "subscription") back?.hide?.(); else back?.show?.();
    back?.onClick?.(handler);
    return () => { back?.offClick?.(handler); back?.hide?.(); };
  }, [view]);
}

export function selectionHaptic() {
  const tg = window.Telegram?.WebApp;
  if (tg?.isVersionAtLeast?.("6.1")) tg.HapticFeedback?.selectionChanged?.();
}
