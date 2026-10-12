import { useEffect } from "react";
import "../static/assets/not-found.css";

export function NotFound({description,href="/",action="Вернуться на главную"}) {
  useEffect(() => {
    const previous = document.title;
    document.title = "Страница не найдена";
    return () => { document.title = previous; };
  }, []);
  return <main className="lunet-not-found"><a className="lunet-not-found-brand" href="https://lunet.pro/" aria-label="Lunet VPS — на главную"><img src="/miniapp/assets/lunet-logo.png" alt="" width="34" height="34"/><span>Lunet<small>VPS</small></span></a><section className="lunet-not-found-card"><span className="lunet-not-found-code">404</span><h1>Страница не найдена</h1><p>{description || "Проверьте адрес или вернитесь на главную страницу Lunet."}</p><nav className="lunet-not-found-actions" aria-label="Помощь и навигация"><a className="lunet-not-found-action" href={href}>{action}<span aria-hidden="true">→</span></a><a className="lunet-not-found-support" href="https://t.me/LunetVPNSupport" target="_blank" rel="noopener noreferrer">Поддержка</a></nav></section></main>;
}
