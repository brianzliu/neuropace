import { useCallback, useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { api, errorText } from "../lib/api";
import { FORMS, type LectureFull, type LossMap, type Profile } from "../lib/types";
import LectureSwitcher from "../components/LectureSwitcher";
import { LossMapCard } from "./LossMap";
import { EXPLANATION_LABEL, TallyCard } from "./Tally";
import { readLocalSetting } from "../lib/storage";

export default function Insights({ learnerId: learnerProp, lectureId: lectureProp }: { learnerId?: string; lectureId?: string } = {}) {
  const params = useParams<{ learnerId?: string; lectureId?: string }>();
  const [search] = useSearchParams();
  const pinnedLearner = learnerProp ?? params.learnerId ?? search.get("learner") ?? "";
  const pinnedLecture = lectureProp ?? params.lectureId ?? search.get("lecture") ?? "";
  const [learnerId, setLearnerId] = useState(pinnedLearner || readLocalSetting("learner") || "");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [confirmReset, setConfirmReset] = useState(false);
  const [lectures, setLectures] = useState<LectureFull[]>([]);
  const [selectedLecture, setSelectedLecture] = useState(pinnedLecture);
  const [lossMap, setLossMap] = useState<LossMap | null>(null);
  const [lecture, setLecture] = useState<LectureFull | null>(null);
  const [lectureError, setLectureError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const requested = pinnedLearner || readLocalSetting("learner") || "me";
    api.learner(requested)
      .catch(() => api.learner("me"))
      .then(learner => { if (active) setLearnerId(learner.id); })
      .catch(error => { if (active) setProfileError(errorText(error)); });
    return () => { active = false; };
  }, [pinnedLearner]);

  const loadProfile = useCallback(async () => {
    if (!learnerId) return;
    try {
      const next = await api.profile(learnerId);
      setProfile(next);
      setProfileError(null);
    } catch (error) {
      setProfileError(errorText(error));
    }
  }, [learnerId]);

  useEffect(() => { void loadProfile(); }, [loadProfile]);

  useEffect(() => {
    let active = true;
    api.lectures()
      .then(({ lectures: list }) => {
        if (!active) return;
        setLectures(list);
        setSelectedLecture(current => {
          const preferred = pinnedLecture || current;
          return list.some(item => item.id === preferred) ? preferred : list[0]?.id ?? "";
        });
      })
      .catch(error => { if (active) setLectureError(errorText(error)); });
    return () => { active = false; };
  }, [pinnedLecture]);

  const lectureId = pinnedLecture || selectedLecture;
  const loadLecture = useCallback(async () => {
    if (!lectureId) return;
    try {
      const [nextMap, nextLecture] = await Promise.all([api.lossmap(lectureId), api.lecture(lectureId)]);
      setLossMap(nextMap);
      setLecture(nextLecture);
      setLectureError(null);
    } catch (error) {
      setLectureError(errorText(error));
    }
  }, [lectureId]);

  useEffect(() => {
    setLossMap(null);
    setLecture(null);
    void loadLecture();
    const refresh = () => { if (document.visibilityState === "visible") void loadLecture(); };
    window.addEventListener("focus", refresh);
    const timer = window.setInterval(refresh, 30_000);
    return () => {
      window.removeEventListener("focus", refresh);
      window.clearInterval(timer);
    };
  }, [loadLecture]);

  const resetPreferences = async () => {
    try {
      await api.resetProfile(learnerId);
      setConfirmReset(false);
      await loadProfile();
    } catch (error) {
      setProfileError(errorText(error));
    }
  };

  return (
    <div className="dashboard insights-page">
      <div className="dashboard-toolbar"><h1>Your learning patterns</h1></div>
      <div className="home insights">
        <section className="col" aria-labelledby="learning-heading">
          <div className="dashboard-section-heading"><h2 id="learning-heading">Your progress</h2></div>
          {profileError ? <div className="panel error" role="alert">{profileError}</div> : null}
          {!profile ? <div className="panel muted">Loading your progress…</div> : (
            <>
              <div className="stats">
                <div className="stat orange"><div className="v">{profile.stats.streak_days}</div><div className="k">day streak</div></div>
                <div className="stat"><div className="v">{profile.stats.lectures}</div><div className="k">lectures recorded</div></div>
                <div className="stat green"><div className="v">{profile.stats.moments_restudied}</div><div className="k">concepts reviewed</div></div>
              </div>
              <TallyCard tally={profile.tally} />
              <section className="panel focus-results" aria-labelledby="focus-results-title">
                <h2 id="focus-results-title">What held your focus</h2>
                {FORMS.map(form => {
                  const mean = profile.tally.forms[form].focus?.mean_focus;
                  const percent = mean == null ? null : Math.round(mean * 100);
                  return (
                    <div className="rescue-row" key={form}>
                      <div className="rescue-head"><span>{EXPLANATION_LABEL[form]}</span><span className="result-value">{percent == null ? "No data" : `${percent}%`}</span></div>
                      <div className="rescue-track" role="img" aria-label={`${EXPLANATION_LABEL[form]} held focus ${percent == null ? "with no headset data" : `${percent} percent of the time`}`}>
                        <div className="rescue-fill focus-fill" style={{ width: `${percent ?? 0}%` }} />
                      </div>
                    </div>
                  );
                })}
              </section>
              <div className="preference-actions">
                {!confirmReset ? <button className="linklike" onClick={() => setConfirmReset(true)}>Reset learning patterns</button> : (
                  <div className="reset-confirmation">
                    <span>Clear your explanation and headset preferences?</span>
                    <button className="btn btn-sm btn-danger" onClick={() => void resetPreferences()}>Clear</button>
                    <button className="btn btn-sm btn-plain" onClick={() => setConfirmReset(false)}>Cancel</button>
                  </div>
                )}
              </div>
            </>
          )}
        </section>
        <section className="col" aria-labelledby="lecture-patterns-heading">
          <div className="dashboard-section-heading lecture-patterns-heading">
            <h2 id="lecture-patterns-heading">Where the lecture got difficult</h2>
            {!pinnedLecture && lectures.length ? <LectureSwitcher lectures={lectures} currentId={selectedLecture} onSelect={setSelectedLecture} /> : null}
          </div>
          {lectureError ? <div className="panel error" role="alert">{lectureError}</div> : null}
          {!lectureId ? <div className="panel muted">Record a lecture to see its difficult sections.</div>
            : !lossMap || !lecture ? <div className="panel muted">Loading lecture patterns…</div>
            : <LossMapCard lm={lossMap} lecture={lecture} />}
        </section>
      </div>
    </div>
  );
}
