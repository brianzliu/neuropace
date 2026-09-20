import { useState } from "react";
import type { Dashboard } from "../../lib/dashboardTypes";
import { readLocalSetting, writeLocalSetting } from "../../lib/storage";

const dateKey = (date: Date) => `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
const GRID_WEEKS = 12;

type ActivityView = "bars" | "grid";

/** Counts recorded sessions per calendar day (viewer timezone), not time
 *  studied or inferred mastery. Review-mode and created sessions excluded. */
function countByDay(sessions: Dashboard["sessions"]): Map<string, number> {
  const now = new Date();
  const counts = new Map<string, number>();
  for (const session of sessions) {
    const date = new Date(session.started_at * 1000);
    if (session.mode === "review" || session.status === "created" || !Number.isFinite(date.getTime()) || date > now) continue;
    const key = dateKey(date);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return counts;
}

function currentStreak(counts: Map<string, number>, now: Date): number {
  let streak = 0;
  const cursor = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  if (!counts.has(dateKey(cursor))) cursor.setDate(cursor.getDate() - 1);
  while (counts.has(dateKey(cursor))) {
    streak += 1;
    cursor.setDate(cursor.getDate() - 1);
  }
  return streak;
}

const level = (count: number) => (count <= 0 ? 0 : count === 1 ? 1 : count === 2 ? 2 : 3);

const pluralSessions = (n: number) => `${n} session${n === 1 ? "" : "s"}`;

export default function SessionActivity({ sessions }: { sessions: Dashboard["sessions"] | undefined }) {
  const [view, setView] = useState<ActivityView>(() =>
    readLocalSetting("activity-view") === "grid" ? "grid" : "bars",
  );
  if (!sessions) return null;
  const now = new Date();
  const counts = countByDay(sessions);
  const days = Array.from({ length: 7 }, (_, i) => {
    const date = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 6 + i);
    return { date, count: counts.get(dateKey(date)) ?? 0 };
  });
  const total = days.reduce((sum, day) => sum + day.count, 0);
  if (!total) return null;
  const streak = currentStreak(counts, now);
  const maximum = Math.max(...days.map(day => day.count), 1);

  // GitHub-style grid: one column per week (Sunday-first), last 12 weeks.
  const gridEnd = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const gridStart = new Date(gridEnd);
  gridStart.setDate(gridStart.getDate() - (GRID_WEEKS * 7 - 1));
  const firstSunday = new Date(gridStart);
  firstSunday.setDate(firstSunday.getDate() - firstSunday.getDay());
  const weeks: Date[][] = [];
  for (let col = new Date(firstSunday); col <= gridEnd; col.setDate(col.getDate() + 7)) {
    weeks.push(Array.from({ length: 7 }, (_, i) => {
      const date = new Date(col);
      date.setDate(date.getDate() + i);
      return date;
    }));
  }
  let gridTotal = 0;
  const weekdayTotals = [0, 0, 0, 0, 0, 0, 0];
  for (const week of weeks) {
    for (const date of week) {
      if (date < gridStart || date > gridEnd) continue;
      const count = counts.get(dateKey(date)) ?? 0;
      gridTotal += count;
      weekdayTotals[date.getDay()] += count;
    }
  }
  const bestDay = weekdayTotals.indexOf(Math.max(...weekdayTotals));
  // Jan 4 2026 is a Sunday; offset by weekday index for a stable long name.
  const bestDayName = new Date(2026, 0, 4 + bestDay).toLocaleDateString(undefined, { weekday: "long" });

  const switchView = (next: ActivityView) => {
    writeLocalSetting("activity-view", next);
    setView(next);
  };

  return <section className="session-activity" aria-label="Recording activity">
    <div className="dashboard-section-heading activity-heading">
      <h2>{streak > 1 ? `You're on a ${streak}-day streak!` : `${pluralSessions(total)} this week`}</h2>
      <div className="activity-view-toggle" role="group" aria-label="Activity chart style">
        <button type="button" aria-pressed={view === "bars"} onClick={() => switchView("bars")}>Bars</button>
        <button type="button" aria-pressed={view === "grid"} onClick={() => switchView("grid")}>Grid</button>
      </div>
    </div>
    {view === "bars" ? (
      <div className="activity-chart" role="img" aria-label={`Sessions recorded over the last seven days, including practice. ${days.map(day => `${day.date.toLocaleDateString()}: ${day.count}`).join(". ")}`}>
        {days.map(day => <div className="activity-day" key={dateKey(day.date)} aria-hidden="true">
          <span className="activity-count">{day.count || ""}</span>
          <div className="activity-track"><div className="activity-bar" style={{height: `${day.count / maximum * 100}%`}} /></div>
          <span>{day.date.toLocaleDateString(undefined, { weekday: "short" })}</span>
        </div>)}
      </div>
    ) : (
      <>
        <div className="activity-grid" role="img" aria-label={`Sessions recorded per day over the last ${GRID_WEEKS} weeks, including practice. ${pluralSessions(gridTotal)} in total. Most active day: ${bestDayName}.`}>
          {weeks.map((week, wi) => {
            const first = week.find(date => date >= gridStart && date.getDay() === 0) ?? week[0];
            const prev = wi === 0 ? null : weeks[wi - 1][0];
            const showMonth = first.getMonth() !== (prev?.getMonth() ?? first.getMonth()) || wi === 0;
            return (
              <div className="activity-week" key={wi} aria-hidden="true">
                <span className="activity-month">{showMonth ? first.toLocaleDateString(undefined, { month: "short" }) : ""}</span>
                {week.map(date => {
                  const future = date > gridEnd;
                  const early = date < gridStart;
                  const count = !future && !early ? counts.get(dateKey(date)) ?? 0 : 0;
                  return (
                    <span
                      key={dateKey(date)}
                      className={`grid-cell l${level(count)}${future || early ? " is-outside" : ""}`}
                      title={future || early ? undefined : `${pluralSessions(count)} on ${date.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}`}
                    />
                  );
                })}
              </div>
            );
          })}
        </div>
        <div className="activity-legend" aria-hidden="true">
          <span>Less</span>
          {[0, 1, 2, 3].map(l => <span key={l} className={`grid-cell legend-swatch l${l}`} />)}
          <span>More</span>
        </div>
      </>
    )}
  </section>;
}
