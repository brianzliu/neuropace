import type { Dashboard } from "../../lib/dashboardTypes";

const dateKey = (date: Date) => `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;

/** Counts saved sessions, not time studied or inferred mastery. Calendar days use the viewer's timezone. */
export default function SessionActivity({ sessions }: { sessions: Dashboard["sessions"] | undefined }) {
  if (!sessions) return null;
  const now = new Date();
  const counts = new Map<string, number>();
  for (const session of sessions) {
    const date = new Date(session.started_at * 1000);
    if (session.mode === "review" || session.status === "created" || !Number.isFinite(date.getTime()) || date > now) continue;
    const key = dateKey(date);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  const days = Array.from({ length: 7 }, (_, i) => {
    const date = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 6 + i);
    return { date, count: counts.get(dateKey(date)) ?? 0 };
  });
  const total = days.reduce((sum, day) => sum + day.count, 0);
  if (!total) return null;
  let streak = 0;
  const cursor = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  if (!counts.has(dateKey(cursor))) cursor.setDate(cursor.getDate() - 1);
  while (counts.has(dateKey(cursor))) {
    streak += 1;
    cursor.setDate(cursor.getDate() - 1);
  }
  const maximum = Math.max(...days.map(day => day.count), 1);
  return <section className="session-activity" aria-label="Recording activity">
    <div className="dashboard-section-heading">
      <h2>{total} session{total === 1 ? "" : "s"} this week</h2>
      {streak > 1 && <span>{streak}-day recording streak</span>}
    </div>
    <div className="activity-chart" role="img" aria-label={`Sessions recorded over the last seven days. ${days.map(day => `${day.date.toLocaleDateString()}: ${day.count}`).join(". ")}`}>
      {days.map(day => <div className="activity-day" key={dateKey(day.date)} aria-hidden="true">
        <span className="activity-count">{day.count || ""}</span>
        <div className="activity-track"><div className="activity-bar" style={{height: `${day.count / maximum * 100}%`}} /></div>
        <span>{day.date.toLocaleDateString(undefined, { weekday: "short" })}</span>
      </div>)}
    </div>
    <p className="small muted">Sessions recorded · last 7 days, including practice</p>
  </section>;
}
