import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { Curriculum, Dashboard } from "../lib/dashboardTypes";
import NewSessionButton from "../components/dashboard/NewSessionButton";
import DemoModeToggle from "../components/dashboard/DemoModeToggle";
import ReviewQueue from "../components/dashboard/ReviewQueue";
import SessionsSidebar from "../components/dashboard/SessionsSidebar";
import CurriculumSection from "../components/dashboard/CurriculumSection";
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
    const load = async (organize = false) => {
      if (loading) return;
      loading = true;
      try {
        const fresh = await api.dashboard(learnerId, organize);
        if (active && version === generation.current) setData(fresh);
      } catch (e) { if (active) setError(String(e)); }
      finally { loading = false; }
    };
    void load().then(async () => {
      if (!active) return;
      setOrganizing(true);
      await load(true);
      if (active) setOrganizing(false);
    });
    const refresh = () => { if (document.visibilityState === "visible") void load(true); };
    window.addEventListener("focus", refresh);
    return () => { active = false; window.removeEventListener("focus", refresh); };
  }, [learnerId]);

  const saveCurriculum = async (curriculum: Curriculum) => {
    const owner = learnerId;
    const version = generation.current;
    setError("");
    try {
      const saved = await api.saveCurriculum(owner, curriculum);
      if (version === generation.current) setData(d => d ? {...d, curriculum: saved} : d);
    } catch (e) { setError(String(e)); throw e; }
  };

  return <div className="dashboard">
    <div className="dashboard-toolbar">
      <div><h1>Ready for your next idea?</h1></div>
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
          hasLearner={Boolean(learnerId)}
          summary={data?.summary}
          organizationSource={data?.organization_source}
          organizing={organizing}
        />
        <SessionActivity sessions={data?.sessions} />
        <CurriculumSection
          curriculum={data?.curriculum}
          learnerId={learnerId}
          onSave={saveCurriculum}
        />
      </div>
      <SessionsSidebar sessions={data?.sessions} concepts={data?.concepts} closed={data?.closed ?? 0} />
    </div>
  </div>;
}
