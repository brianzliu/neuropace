import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import type { Learner, LectureFull, LossMap, TallySummary } from "../lib/types";
import { LossMapCard } from "./LossMap";
import { TallyCard } from "./Tally";

const LS_KEY = "reflow.learner";

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
  const [selectedLearner, setSelectedLearner] = useState(() => pinnedLearner || localStorage.getItem(LS_KEY) || "");
  const [tally, setTally] = useState<TallySummary | null>(null);
  const [tallyErr, setTallyErr] = useState<string | null>(null);

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
    setTally(null);
    setTallyErr(null);
    if (!learnerId) return;
    let alive = true;
    api.tally(learnerId)
      .then((t) => { if (alive) setTally(t); })
      .catch((e) => { if (alive) setTallyErr(String(e)); });
    return () => { alive = false; };
  }, [learnerId]);

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

  const learner = learners.find((l) => l.id === learnerId) ?? null;
  const pickLearner = (id: string) => {
    setSelectedLearner(id);
    if (!pinnedLearner) {
      try { localStorage.setItem(LS_KEY, id); } catch { /* Selection still works without storage. */ }
    }
  };

  return (
    <div className="dashboard">
      <div className="dashboard-toolbar">
        <div>
          <span className="workspace-label"><span aria-hidden="true">✳</span> Insights</span>
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
            {learner ? ` · ${learner.name}` : ""}
          </p>
          {tallyErr ? <div className="panel error" role="alert">{tallyErr}</div> : null}
          {!learnerId ? (
            <div className="panel muted">Create a profile on the <Link to="/">dashboard</Link> to start your tally.</div>
          ) : !tally ? (
            <div className="panel muted">loading…</div>
          ) : (
            <TallyCard tally={tally} />
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
          <p className="muted small" style={{ margin: 0 }}>Aggregate and anonymous. It grades the lecture, never a student.</p>
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
