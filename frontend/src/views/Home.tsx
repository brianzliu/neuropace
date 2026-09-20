import { useCallback, useEffect, useState } from "react";
import { api, errorText } from "../lib/api";
import type { Dashboard } from "../lib/dashboardTypes";
import type { Profile } from "../lib/types";
import NewSessionButton from "../components/dashboard/NewSessionButton";
import ReviewQueue from "../components/dashboard/ReviewQueue";
import SessionsSidebar from "../components/dashboard/SessionsSidebar";
import { TallyCard } from "./Tally";
import { readLocalSetting, writeLocalSetting } from "../lib/storage";

/** The one learner page: moments worth another look, the lectures they came from, and which
 * explanation form has been landing. Preserve an existing profile; new devices use the default learner. */
export default function Home() {
  const [learnerId, setLearnerId] = useState(() => readLocalSetting("learner") ?? "");
  const [data, setData] = useState<Dashboard | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    api.learners().then(async ({ learners }) => {
      const saved = readLocalSetting("learner");
      const learner = learners.find(item => item.id === saved) ?? await api.learner("me");
      if (active) setLearnerId(learner.id);
    }).catch(e => { if (active) setError(errorText(e)); });
    return () => { active = false; };
  }, []);

  const load = useCallback(async () => {
    if (!learnerId) return;
    try {
      const [fresh, prof] = await Promise.all([api.dashboard(learnerId), api.profile(learnerId)]);
      setData(fresh);
      setProfile(prof);
      setError("");
    } catch (e) { setError(errorText(e)); }
  }, [learnerId]);

  useEffect(() => {
    setData(null); setProfile(null);
    if (!learnerId) return;
    writeLocalSetting("learner", learnerId);
    void load();
    const refresh = () => { if (document.visibilityState === "visible") void load(); };
    window.addEventListener("focus", refresh);
    return () => window.removeEventListener("focus", refresh);
  }, [learnerId, load]);

  const resetPatterns = async () => {
    try {
      await api.resetProfile(learnerId);
      await load();
    } catch (e) { setError(errorText(e)); }
  };

  // Office Hours and review-only sessions aren't lectures: they never transition to "ended" the way a
  // recorded/live capture does and would sit here as a phantom "running" row forever.
  const sessions = data?.sessions.filter(s => s.mode !== "review" && s.mode !== "office_hours");

  return <div className="dashboard">
    <div className="dashboard-toolbar">
      <div className="dashboard-actions">
        <NewSessionButton />
      </div>
    </div>
    {error && <div className="panel error" role="alert">{error}</div>}
    <div className="dashboard-grid">
      <div className="dashboard-main">
        <ReviewQueue concepts={data?.concepts} closed={data?.closed ?? 0} />
        {profile ? (
          <section className="insights tally-section" aria-label="What helps you understand">
            <TallyCard tally={profile.tally} onReset={() => void resetPatterns()} />
          </section>
        ) : null}
      </div>
      <SessionsSidebar sessions={sessions} />
    </div>
  </div>;
}
