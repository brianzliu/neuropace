import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { Learner } from "../lib/types";
import type { Curriculum, Dashboard } from "../lib/dashboardTypes";
import NewSessionButton from "../components/dashboard/NewSessionButton";
import ReviewQueue from "../components/dashboard/ReviewQueue";
import SessionsSidebar from "../components/dashboard/SessionsSidebar";
import CurriculumSection from "../components/dashboard/CurriculumSection";

/** Dashboard home: profile-scoped composition + data fetching only.
 *  Sections live in components/dashboard/*. One launcher (NewSessionButton);
 *  no other start-language buttons on this page. Learner switching reloads;
 *  no cross-learner pooling here (aggregation lives in Insights). */
export default function Home() {
  const [learners, setLearners] = useState<Learner[]>([]);
  const [learnerId, setLearnerId] = useState(() => localStorage.getItem("reflow.learner") ?? "");
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [organizing, setOrganizing] = useState(false);
  const generation = useRef(0);

  useEffect(() => { api.learners().then(({learners: list}) => {
    setLearners(list);
    setLearnerId(current => list.some(l => l.id === current) ? current : list[0]?.id ?? "");
  }).catch(e => setError(String(e))); }, []);

  useEffect(() => {
    const version = ++generation.current;
    setData(null); setError("");
    if (!learnerId) return;
    localStorage.setItem("reflow.learner", learnerId);
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

  const createProfile = async () => {
    if (!name.trim()) return;
    setBusy(true); setError("");
    try { const learner = await api.createLearner(name.trim()); setLearners(ls => [...ls, learner]); setLearnerId(learner.id); setName(""); }
    catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  };
  const saveCurriculum = async (curriculum: Curriculum) => {
    const owner = learnerId;
    const version = generation.current;
    setError("");
    try {
      const saved = await api.saveCurriculum(owner, curriculum);
      if (version === generation.current) setData(d => d ? {...d, curriculum: saved} : d);
    } catch (e) { setError(String(e)); throw e; }
  };
  const learner = learners.find(l => l.id === learnerId);

  return <div className="dashboard">
    <div className="dashboard-toolbar">
      <div><span className="workspace-label">Your learning space</span><h1>Let’s connect the dots.</h1><p className="muted">A second look can make all the difference.</p></div>
      <NewSessionButton />
    </div>
    <div className="profile-toolbar">
      {learners.length > 0 && <label>Your profile<select value={learnerId} onChange={e => setLearnerId(e.target.value)}>{learners.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}</select></label>}
      <details><summary>{learners.length ? "Add a profile" : "Create your profile to get started"}</summary><div className="row"><input aria-label="Profile name" placeholder="Your name" value={name} onChange={e => setName(e.target.value)} onKeyDown={e => { if (e.key === "Enter") void createProfile(); }} /><button disabled={busy || !name.trim()} onClick={() => void createProfile()}>Create profile</button></div></details>
      <span className="small muted">{learner ? `${learner.name}’s notes and review` : "Your saved moments will live here."}</span>
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
          hasLearner={Boolean(learnerId)}
        />
        <CurriculumSection
          curriculum={data?.curriculum}
          learnerId={learnerId}
          onSave={saveCurriculum}
        />
      </div>
      <SessionsSidebar sessions={data?.sessions} />
    </div>
  </div>;
}
