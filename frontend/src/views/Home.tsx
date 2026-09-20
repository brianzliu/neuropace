import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { Dashboard } from "../lib/dashboardTypes";
import NewSessionButton from "../components/dashboard/NewSessionButton";
import DemoModeToggle from "../components/dashboard/DemoModeToggle";
import ReviewQueue from "../components/dashboard/ReviewQueue";
import SessionsSidebar from "../components/dashboard/SessionsSidebar";
import SessionActivity from "../components/dashboard/SessionActivity";
import { readLocalSetting, writeLocalSetting } from "../lib/storage";

/** Learner-owned dashboard. Preserve an existing profile; new devices use the default learner. */
export default function Home() {
  const [learnerId, setLearnerId] = useState(() => readLocalSetting("learner") ?? "");
  const [data, setData] = useState<Dashboard | null>(null);
  const [organizing, setOrganizing] = useState(false);
  const [error, setError] = useState("");
  const generation = useRef(0);

  useEffect(() => {
    let active = true;
    api.learners().then(async ({ learners }) => {
      const saved = readLocalSetting("learner");
      const learner = learners.find(item => item.id === saved) ?? await api.learner("me");
      if (active) setLearnerId(learner.id);
    }).catch(e => { if (active) setError(String(e)); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const version = ++generation.current;
    setData(null); setError("");
    setOrganizing(false);
    if (!learnerId) return;
    writeLocalSetting("learner", learnerId);
    let active = true;
    let loading = false;
    const load = async (organize = false, loud = true) => {
      if (loading) return;
      loading = true;
      try {
        const fresh = await api.dashboard(learnerId, organize);
        if (active && version === generation.current) setData(fresh);
      } catch (e) { if (active && loud) setError(String(e)); }
      finally { loading = false; }
    };
    void load().then(async () => {
      if (!active) return;
      setOrganizing(true);
      // Quiet: a slow/failed organize pass keeps the deterministic data
      // instead of painting the whole dashboard red.
      await load(true, false);
      if (active) setOrganizing(false);
    });
    const refresh = () => { if (document.visibilityState === "visible") void load(true); };
    window.addEventListener("focus", refresh);
    return () => { active = false; window.removeEventListener("focus", refresh); };
  }, [learnerId]);

  // Office Hours and Restudy-only sessions aren't lectures: they'd otherwise show up here as a
  // phantom "Live lecture" row stuck on "running" forever, since neither mode ever transitions a
  // session to "ended" the way a recorded/live capture does. Same filter Lectures.tsx/Library.tsx use.
  const sessions = data?.sessions.filter(s => s.mode !== "review" && s.mode !== "office_hours");

  return <div className="dashboard">
    <div className="dashboard-toolbar">
      <div className="dashboard-actions">
        <DemoModeToggle />
        <NewSessionButton />
      </div>
    </div>
    {error && <div className="panel error" role="alert">{error}</div>}
    <div className="dashboard-grid">
      <div className="dashboard-main">
        <ReviewQueue
          concepts={data?.concepts}
          closed={data?.closed ?? 0}
          summary={data?.summary}
          organizationSource={data?.organization_source}
          organizing={organizing}
        />
        <SessionActivity sessions={sessions} />
      </div>
      <SessionsSidebar sessions={sessions} concepts={data?.concepts} closed={data?.closed ?? 0} />
    </div>
  </div>;
}
