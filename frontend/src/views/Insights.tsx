import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, errorText } from "../lib/api";
import { FORM_LABEL, FORMS, type Learner, type LectureFull, type LossMap, type Profile } from "../lib/types";
import { LossMapCard } from "./LossMap";
import { TallyCard } from "./Tally";
import { readLocalSetting, writeLocalSetting } from "../lib/storage";

/** Insights shell: the learner's own review preferences (Tally) plus the
 *  anonymized, aggregate lecture overview (LossMap). No per-learner traces
 *  on the LossMap card, ever. Route params (Agent A's shell) and query
 *  params both work, so /tally/:learnerId and /lossmap/:lectureId can be
 *  re-homed here without losing the deep link. */
export default function Insights({ learnerId: learnerProp, lectureId: lectureProp }: { learnerId?: string; lectureId?: string } = {}) {
  const params = useParams<{ learnerId?: string; lectureId?: string }>();
  const [search] = useSearchParams();
  const pinnedLearner = learnerProp ?? params.learnerId ?? search.get("learner") ?? "";
  const pinnedLecture = lectureProp ?? params.lectureId ?? search.get("lecture") ?? "";

  const [learners, setLearners] = useState<Learner[]>([]);
  const [selectedLearner, setSelectedLearner] = useState(() => pinnedLearner || readLocalSetting("learner") || "");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [tallyErr, setTallyErr] = useState<string | null>(null);
  const [confirmReset, setConfirmReset] = useState(false);

  const [lectures, setLectures] = useState<LectureFull[]>([]);
  const [selectedLecture, setSelectedLecture] = useState(pinnedLecture);
  const [lm, setLm] = useState<LossMap | null>(null);
  const [lecture, setLecture] = useState<LectureFull | null>(null);
  const [lmErr, setLmErr] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    api.learners()
      .then(({ learners: list }) => {
        setLearners(list);
        setSelectedLearner((current) => {
          const preferred = pinnedLearner || current;
          return list.some((l) => l.id === preferred) ? preferred : list[0]?.id ?? "";
        });
      })
      .catch((e) => setLoadError(String(e)));
  }, [pinnedLearner]);

  useEffect(() => {
    api.lectures()
      .then(({ lectures: list }) => {
        setLectures(list);
        setSelectedLecture((current) => {
          const preferred = pinnedLecture || current;
          return list.some((l) => l.id === preferred) ? preferred : list[0]?.id ?? "";
        });
      })
      .catch((e) => setLoadError(String(e)));
  }, [pinnedLecture]);

  const learnerId = pinnedLearner || selectedLearner;
  useEffect(() => {
    setProfile(null);
    setTallyErr(null);
    setConfirmReset(false);
    if (!learnerId) return;
    let alive = true;
    api.profile(learnerId)
      .then((p) => { if (alive) setProfile(p); })
      .catch((e) => { if (alive) setTallyErr(String(e)); });
    return () => { alive = false; };
  }, [learnerId]);

  const resetPreferences = () => {
    api.resetProfile(learnerId).then(() => {
      setConfirmReset(false);
      return api.profile(learnerId).then(setProfile);
    }).catch((e) => setTallyErr(errorText(e)));
  };

  const lectureId = pinnedLecture || selectedLecture;
  useEffect(() => {
    setLm(null);
    setLecture(null);
    setLmErr(null);
    if (!lectureId) return;
    let alive = true;
    Promise.all([api.lossmap(lectureId), api.lecture(lectureId)])
      .then(([m, l]) => { if (alive) { setLm(m); setLecture(l); } })
      .catch((e) => { if (alive) setLmErr(String(e)); });
    return () => { alive = false; };
  }, [lectureId, refresh]);

  const pickLearner = (id: string) => {
    setSelectedLearner(id);
    if (!pinnedLearner) {
      writeLocalSetting("learner", id);
    }
  };

  return (
    <div className="dashboard">
      <div className="dashboard-toolbar">
        <div>

          <h1>What lands for you.</h1>
          <p className="muted">Your review preferences are learner-scoped. Lecture overviews pool the room and stay anonymous.</p>
        </div>
      </div>
      {loadError ? <div className="panel error" role="alert">{loadError}</div> : null}
      <div className="home">
        <section className="col" aria-labelledby="review-preferences-heading">
          <div className="dashboard-section-heading">
            <h2 id="review-preferences-heading">My review preferences</h2>
            {!pinnedLearner && learners.length ? (
              <label className="row" style={{ gap: ".5rem" }}>
                <span className="small muted">profile</span>
                <select value={selectedLearner} onChange={(e) => pickLearner(e.target.value)}>
                  {learners.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
                </select>
              </label>
            ) : null}
          </div>
          <p className="muted small" style={{ margin: 0 }}>
            We don't believe in learning styles. We test it on you, and show you the data.
          </p>
          {tallyErr ? <div className="panel error" role="alert">{tallyErr}</div> : null}
          {!learnerId ? (
            <div className="panel muted">Create a profile on the <Link to="/">dashboard</Link> to start your tally.</div>
          ) : !profile ? (
            <div className="panel muted">loading…</div>
          ) : (
            <>
              <div className="stats">
                <div className="stat orange">
                  <div className="v">{profile.stats.streak_days}</div>
                  <div className="k">day streak</div>
                </div>
                <div className="stat">
                  <div className="v">{profile.stats.lectures}</div>
                  <div className="k">lectures</div>
                </div>
                <div className="stat green">
                  <div className="v">{profile.stats.moments_restudied}</div>
                  <div className="k">moments landed</div>
                </div>
              </div>
              <TallyCard tally={profile.tally} />
              <div className="panel" aria-label="How much each explanation held your attention">
                <h2 style={{ marginTop: 0 }}>Held your attention</h2>
                <p className="small muted" style={{ marginTop: 0 }}>Measured with the headset while you read a re-teach card. A drift switches the explanation on the spot.</p>
                {FORMS.map((f) => {
                  const meanFocus = profile.tally.forms[f].focus?.mean_focus;
                  const focusPct = meanFocus != null ? Math.round(meanFocus * 100) : null;
                  return (
                    <div className="rescue-row" key={f}>
                      <div className="rescue-head"><span>{FORM_LABEL[f]}</span></div>
                      <div className="rescue-track" role="img" aria-label={`${FORM_LABEL[f]}: ${focusPct ?? "no"} percent attention held`}>
                        <div className="rescue-fill" style={{ width: `${focusPct ?? 0}%` }} />
                      </div>
                      <span className="small muted">{focusPct != null ? `${focusPct}%` : "no headset data yet"}</span>
                    </div>
                  );
                })}
              </div>
              <div className="row between" style={{ alignItems: "center" }}>
                <span className="small muted">{profile.calibrated ? "Focus calibration saved from your last lecture." : "Focus calibration is learned during your next lecture."}</span>
                {!confirmReset ? (
                  <button className="linklike" onClick={() => setConfirmReset(true)}>Reset preferences</button>
                ) : (
                  <span className="row" style={{ gap: ".5rem", alignItems: "center" }}>
                    <span className="small muted">Reset this learner's preferences and calibration. Lectures stay.</span>
                    <button className="btn btn-sm btn-danger" onClick={resetPreferences}>Start fresh</button>
                    <button className="btn btn-sm btn-plain" onClick={() => setConfirmReset(false)}>Keep</button>
                  </span>
                )}
              </div>
            </>
          )}
        </section>
        <section className="col" aria-labelledby="lecture-overview-heading">
          <div className="dashboard-section-heading">
            <h2 id="lecture-overview-heading">Lecture overview</h2>
            <div className="row" style={{ gap: ".5rem" }}>
              {!pinnedLecture && lectures.length ? (
                <label className="row" style={{ gap: ".5rem" }}>
                  <span className="small muted">lecture</span>
                  <select value={selectedLecture} onChange={(e) => setSelectedLecture(e.target.value)}>
                    {lectures.map((l) => <option key={l.id} value={l.id}>{l.title}</option>)}
                  </select>
                </label>
              ) : null}
              {lectureId ? (
                <button className="ghost" onClick={() => setRefresh((r) => r + 1)}>refresh</button>
              ) : null}
            </div>
          </div>
          {lmErr ? <div className="panel error" role="alert">{lmErr}</div> : null}
          {!lectureId ? (
            <div className="panel muted">No lecture selected yet.</div>
          ) : !lm || !lecture ? (
            <div className="panel muted">loading…</div>
          ) : (
            <LossMapCard lm={lm} lecture={lecture} />
          )}
        </section>
      </div>
    </div>
  );
}
