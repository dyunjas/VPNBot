import { useLayoutEffect, useRef, useState } from "react";

const storageKey = "lunet_cookie_notice_v1";

export default function CookieNotice() {
  const [visible, setVisible] = useState(() => {
    try { return localStorage.getItem(storageKey) !== "accepted"; }
    catch { return true; }
  });
  const notice = useRef(null);

  useLayoutEffect(() => {
    if (!visible) return;
    const measure = () => {
      const bottom = parseFloat(getComputedStyle(notice.current).bottom) || 0;
      document.documentElement.style.setProperty("--cookie-notice-space", `${notice.current.offsetHeight + bottom + 16}px`);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(notice.current);
    return () => {
      observer.disconnect();
      document.documentElement.style.removeProperty("--cookie-notice-space");
    };
  }, [visible]);

  const accept = () => {
    // Acknowledges this notice; does not enable optional tracking or accept agreements.
    try { localStorage.setItem(storageKey, "accepted"); } catch {}
    setVisible(false);
  };

  if (!visible) return null;
  return <aside className="cookie-notice" ref={notice} aria-label="Уведомление о cookie">
    <p>Мы используем необходимые cookie для работы личного кабинета и сохранения входа. Подробнее — в <a href="/terms/privacy/" target="_blank" rel="noopener noreferrer">Политике конфиденциальности</a> и <a href="/terms/" target="_blank" rel="noopener noreferrer">Пользовательском соглашении</a>.</p>
    <button type="button" className="button" onClick={accept}>Принять</button>
  </aside>;
}
