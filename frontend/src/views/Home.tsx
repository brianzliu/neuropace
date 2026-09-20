import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { ClassSummary, Curriculum, Dashboard } from "../lib/dashboardTypes";
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
  const [classes, setClasses] = useState<ClassSummary[]>([]);
  const [classId, setClassId] = useState("");
  const [organizing, setOrganizing] = useState(false);
  const [error, setError] = useState("");
  const generation = useRef(0);
  const learnerRef = useRef("");

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
    if (learnerRef.current !== learnerId) {
      learnerRef.current = learnerId;
      setClassId("");
      return;
    }
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
        const fresh = await api.dashboard(learnerId, organize, classId || undefined);
        if (active && version === generation.current) setData(fresh);
      } catch (e) { if (active) setError(String(e)); }
      finally { loading = false; }
    };
    api.classes(learnerId).then(({ classes: list }) => {
      if (active && version === generation.current) setClasses(list);
    }).catch(e => { if (active) setError(String(e)); });
    void load().then(async () => {
      if (!active) return;
      setOrganizing(true);
      await load(true);
      if (active) setOrganizing(false);
    });
    const refresh = () => { if (document.visibilityState === "visible") void load(true); };
    window.addEventListener("focus", refresh);
    return () => { active = false; window.removeEventListener("focus", refresh); };
  }, [learnerId, classId]);

  const saveCurriculum = async (curriculum: Curriculum) => {
    const owner = learnerId;
    const version = generation.current;
    setError("");
    try {
      const saved = await api.saveCurriculum(owner, curriculum);
      if (version === generation.current) {
        setData(d => d ? {...d, curriculum: saved} : d);
        api.classes(owner).then(({ classes: list }) => {
          if (version === generation.current) setClasses(list);
        }).catch(() => {});
      }
    } catch (e) { setError(String(e)); throw e; }
  };
  const refreshClasses = async () => {
    try {
      const { classes: list } = await api.classes(learnerId);
      setClasses(list);
      return list;
    } catch (e) { setError(String(e)); return []; }
  };
  const selectClass = async (id: string) => {
    setError("");
    try {
      await api.activateClass(learnerId, id);
      setClassId(id);
      void refreshClasses();
    } catch (e) { setError(String(e)); }
  };
  const createClass = async (title: string) => {
    setError("");
    const created = await api.createClass(learnerId, title);
    await api.activateClass(learnerId, created.id);
    setClassId(created.id);
    void refreshClasses();
    return created.id;
  };
  const deleteClass = async (id: string) => {
    setError("");
    try {
      const { classes: list } = await api.deleteClass(learnerId, id);
      setClasses(list);
      setClassId("");
    } catch (e) { setError(String(e)); throw e; }
  };
  const activeClassId = classId || data?.active_class?.id || classes.find(c => c.is_active)?.id || "";

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
          sessions={data?.sessions}
        />
        <SessionActivity sessions={data?.sessions} />
        <CurriculumSection
          curriculum={data?.curriculum}
          understanding={data?.understanding}
          organizing={organizing}
          learnerId={learnerId}
          onSave={saveCurriculum}
          classes={classes}
          activeClassId={activeClassId}
          onSelectClass={selectClass}
          onCreateClass={createClass}
          onDeleteClass={deleteClass}
        />
      </div>
      <SessionsSidebar sessions={data?.sessions} concepts={data?.concepts} closed={data?.closed ?? 0} />
    </div>
  </div>;
}
