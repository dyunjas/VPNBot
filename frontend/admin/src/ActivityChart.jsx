// Adapted from Amicro MonoRoundedBarChart (MIT), see ../public/AMICRO-LICENSE.txt.
// Real Lunet series replace demo data; users and currency use independent views.
import { useMemo, useState } from "react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip } from "recharts";
import { useReducedMotion } from "../../shared/controls.jsx";

function TooltipContent({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return <div className="chart-tooltip"><b>{label}</b>{payload.map(item => <span key={item.dataKey}>{item.name}: <strong>{Number(item.value).toLocaleString("ru-RU")}{item.dataKey === "payments" ? " ₽" : ""}</strong></span>)}</div>;
}

export function ActivityChart({ stats }) {
  const [metric, setMetric] = useState("users");
  const reduced = useReducedMotion();
  const data = useMemo(() => {
    const points = new Map();
    const add = (items, key) => items.forEach((item, index) => {
      const label = String(item.label || item.date || item.key || index + 1);
      const point = points.get(label) || { label, users: null, payments: null };
      const value = key === "users" ? item.count ?? item.value ?? item.users : item.amount ?? item.value;
      point[key] = value != null && Number.isFinite(Number(value)) ? Number(value) : null;
      points.set(label, point);
    });
    add(stats.users_chart || [], "users"); add(stats.payments_chart || [], "payments");
    const data = [...points.values()];
    return data.every(point => /^\d{4}-\d{2}-\d{2}/.test(point.label)) ? data.sort((a,b) => a.label.localeCompare(b.label)) : data;
  }, [stats.users_chart, stats.payments_chart]);
  if (!data.length) return <div className="empty-state">Нет данных за выбранный период</div>;
  const title = metric === "users" ? "Пользователи" : "Выручка, ₽";
  return <div className="lunet-chart">
    <div className="lunet-chart-tabs" aria-label="Показатель графика">{[["users", "Пользователи"], ["payments", "Выручка, ₽"]].map(([key, label]) => <button key={key} type="button" aria-pressed={metric === key} onClick={() => setMetric(key)}>{label}</button>)}</div>
    <div className="lunet-chart-stage" role="img" aria-label={`${title} за выбранный период. Точные значения доступны в таблице под графиком.`}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 10, right: 12, left: 0, bottom: 0 }} accessibilityLayer>
          <CartesianGrid strokeDasharray="2 2" vertical={false} stroke="var(--chart-grid)" />
          <XAxis dataKey="label" tickLine={false} axisLine={false} minTickGap={24} tick={{ fontSize: 11, fill: "var(--chart-muted)" }} />
          <YAxis width={48} tickLine={false} axisLine={false} allowDecimals={metric === "payments"} tick={{ fontSize: 11, fill: "var(--chart-muted)" }} tickFormatter={value => Intl.NumberFormat("ru-RU", { notation: "compact" }).format(value)} />
          <Tooltip cursor={{ fill: "var(--chart-grid)" }} content={<TooltipContent />} />
          <Bar dataKey={metric} name={title} fill="var(--chart-1)" radius={[6,6,6,6]} maxBarSize={18} isAnimationActive={!reduced} animationDuration={220} />
        </BarChart>
      </ResponsiveContainer>
    </div>
    <details className="lunet-chart-data"><summary>Точные значения</summary><div className="table-scroll"><table><caption className="lunet-sr-only">Статистика за выбранный период</caption><thead><tr><th>Дата</th><th>Пользователи</th><th>Выручка, ₽</th></tr></thead><tbody>{data.map(point => <tr key={point.label}><td>{point.label}</td><td>{point.users?.toLocaleString("ru-RU") ?? "—"}</td><td>{point.payments?.toLocaleString("ru-RU") ?? "—"}</td></tr>)}</tbody></table></div></details>
  </div>;
}
