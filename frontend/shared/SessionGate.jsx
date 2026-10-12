import { useEffect, useState } from "react";
import { LunetLoader } from "./controls.jsx";

// Protected components are mounted only after the server confirms the session.
export function SessionGate({ check, children }) {
  const [state, setState] = useState({ pending: true });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let current = true;
    setState({ pending: true });
    Promise.resolve().then(check).then(session => {
      if (current) setState({ session });
    }).catch(error => {
      // API clients redirect expired sessions; keep the shell hidden meanwhile.
      if (current && error.status !== 401) setState({ error: true });
    });
    return () => { current = false; };
  }, [check, attempt]);
  if (state.session) return typeof children === "function" ? children(state.session) : children;
  return <main className="session-check-page" aria-busy={state.pending || undefined}>
    {state.error ? <div className="session-check-error" role="alert"><p>Не удалось проверить сессию. Проверьте подключение и попробуйте снова.</p><button type="button" onClick={() => setAttempt(value => value + 1)}>Повторить</button></div> : <LunetLoader size={24} label="Проверка сессии"/>}
  </main>;
}
