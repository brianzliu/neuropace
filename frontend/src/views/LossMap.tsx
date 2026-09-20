import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../lib/api";
import type { LectureFull, LossMap } from "../lib/types";
import { mmss, range } from "../lib/format";

function difficultyLabel(percent: number) {
  if (percent >= 67) return "high difficulty";
  if (percent >= 34) return "medium difficulty";
  return "low difficulty";
}

/** An anonymous aggregate view of where learners needed more help in a lecture. */
export function LossMapCard({ lm, lecture }: { lm: LossMap; lecture: LectureFull }) {
  const bins = lm.bins ?? [];
  const maxLoss = Math.max(0.5, ...bins.map(bin => bin.loss ?? 0));
  const minLoss = Math.min(0, ...bins.map(bin => bin.loss ?? 0));
  const span = maxLoss - minLoss || 1;
  const peak = lm.peak;
  const maxScore = Math.max(0, ...(lm.segments ?? []).map(segment => segment.score ?? 0)) || 1;

  if (!lm.ready) {
    return (
      <div className="panel waiting-card">
        <h2>More sessions needed</h2>
        <p className="muted small">This chart appears after the lecture has been recorded twice.</p>
      </div>
    );
  }

  return (
    <>
      <section className="panel difficulty-card" aria-labelledby="difficulty-chart-title">
        <div className="loss-head">
          <h2 id="difficulty-chart-title">Difficulty across the lecture</h2>
          {peak ? <span className="peak-time">Hardest stretch: {range(peak.t_start, peak.t_end)}</span> : null}
        </div>
        <div className="difficulty-chart">
          <div className="difficulty-scale" aria-hidden="true"><span>More difficult</span><span>Easier</span></div>
          <div className="lossbars">
            {bins.map(bin => {
              const inPeak = !!peak && bin.t >= peak.t_start && bin.t < peak.t_end;
              const height = bin.loss === null ? 0 : ((bin.loss - minLoss) / span) * 100;
              const percent = Math.max(2, Math.round(height));
              return (
                <div
                  key={bin.t}
                  className={`bar${inPeak ? " peak" : ""}${bin.loss === null ? " empty" : ""}`}
                  style={{ height: `${percent}%` }}
                  data-tip={`${mmss(bin.t)}: ${bin.loss === null ? "no signal" : difficultyLabel(percent)}`}
                  aria-label={`${mmss(bin.t)}, ${bin.loss === null ? "no signal" : difficultyLabel(percent)}`}
                />
              );
            })}
          </div>
        </div>
        <div className="row small muted chart-times"><span>{mmss(0)}</span><span>{mmss(lecture.duration ?? 0)}</span></div>
      </section>
      {(lm.segments?.length ?? 0) > 0 ? (
        <section className="panel">
          <h2 className="section-list-title">Lecture sections</h2>
          <ol className="seglist">
            {(lm.segments ?? [])
              .slice()
              .sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99))
              .map(segment => {
                const percent = Math.round(((segment.score ?? 0) / maxScore) * 100);
                return (
                  <li key={segment.id} className={segment.rank === 1 ? "top" : ""}>
                    <div className="seg-body">
                      <span className="seg-title">{segment.title}</span>
                      <span className="seg-meta">{range(segment.t_start, segment.t_end)}</span>
                    </div>
                    <span className="seg-score" role="img" aria-label={`${difficultyLabel(percent)} compared with other sections`}>
                      <i style={{ width: `${percent}%` }} />
                    </span>
                  </li>
                );
              })}
          </ol>
        </section>
      ) : null}
    </>
  );
}

export default function LossMapView() {
  const { lectureId = "" } = useParams();
  const [lossMap, setLossMap] = useState<LossMap | null>(null);
  const [lecture, setLecture] = useState<LectureFull | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([api.lossmap(lectureId), api.lecture(lectureId)])
      .then(([nextMap, nextLecture]) => {
        if (active) {
          setLossMap(nextMap);
          setLecture(nextLecture);
        }
      })
      .catch(cause => { if (active) setError(String(cause)); });
    return () => { active = false; };
  }, [lectureId]);

  if (error) return <div className="panel error">{error}</div>;
  if (!lossMap || !lecture) return <div className="panel muted">Loading lecture patterns…</div>;
  return (
    <div className="col insights">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h1 style={{ margin: 0 }}>{lecture.title}</h1>
        <Link to="/insights">All insights</Link>
      </div>
      <LossMapCard lm={lossMap} lecture={lecture} />
    </div>
  );
}
