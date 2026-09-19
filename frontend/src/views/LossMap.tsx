import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../lib/api";
import type { LectureFull, LossMap } from "../lib/types";
import { mmss, range } from "../lib/format";

export default function LossMapView() {
  const { lectureId = "" } = useParams();
  const [lm, setLm] = useState<LossMap | null>(null);
  const [lecture, setLecture] = useState<LectureFull | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [reveal, setReveal] = useState(false);
  const load = () =>
    Promise.all([api.lossmap(lectureId), api.lecture(lectureId)])
      .then(([m, l]) => {
        setLm(m);
        setLecture(l);
      })
      .catch((e) => setErr(String(e)));
  useEffect(() => {
    void load();
  }, [lectureId]); // eslint-disable-line react-hooks/exhaustive-deps
  if (err) return <div className="panel error">{err}</div>;
  if (!lm || !lecture) return <div className="panel muted">loading…</div>;
  const planted = new Set((lecture.segments ?? []).filter((s) => s.planted_bad).map((s) => s.id));
  const bins = lm.bins ?? [];
  const maxLoss = Math.max(0.5, ...bins.map((b) => b.loss ?? 0));
  const minLoss = Math.min(0, ...bins.map((b) => b.loss ?? 0));
  const span = maxLoss - minLoss || 1;
  const peak = lm.peak;
  return (
    <div className="col">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h1 style={{ margin: 0 }}>Lecture loss map: {lecture.title}</h1>
        <div className="row">
          <button className="ghost" onClick={() => void load()}>refresh</button>
          <Link to="/">home</Link>
        </div>
      </div>
      <div className="muted">Where the room was lost. Aggregate and anonymous: it grades the lecture, never a student. n = {lm.n} learner{lm.n === 1 ? "" : "s"}.</div>
      {!lm.ready ? (
        <div className="panel">needs 2 or more learners on this lecture ({lm.n} so far)</div>
      ) : (
        <>
          <div className="panel">
            <h2>
              Pooled loss per {lm.bin_seconds} s{peak ? <span className="muted"> · peak 40 s: <span className="mono" style={{ color: "var(--bad)" }}>{range(peak.t_start, peak.t_end)}</span></span> : null}
            </h2>
            <div className="lossbars">
              {bins.map((b) => {
                const inPeak = !!peak && b.t >= peak.t_start && b.t < peak.t_end;
                const h = b.loss === null ? 0 : ((b.loss - minLoss) / span) * 100;
                return <div key={b.t} className={"bar" + (inPeak ? " peak" : "") + (b.loss === null ? " empty" : "")} style={{ height: `${Math.max(2, h)}%` }} data-tip={`${mmss(b.t)}  loss ${b.loss ?? "n/a"}  n=${b.n}`} />;
              })}
            </div>
            <div className="row small muted" style={{ justifyContent: "space-between" }}>
              <span>{mmss(0)}</span>
              <span>{mmss(lecture.duration ?? 0)}</span>
            </div>
          </div>
          <div className="panel">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <h2 style={{ margin: 0 }}>Segments</h2>
              {planted.size ? (
                <button className="ghost" onClick={() => setReveal((r) => !r)}>
                  {reveal ? "hide planted segment" : "reveal planted segment"}
                </button>
              ) : null}
            </div>
            <table className="segtable">
              <thead>
                <tr>
                  <th>rank</th>
                  <th>segment</th>
                  <th>time</th>
                  <th>loss score</th>
                </tr>
              </thead>
              <tbody>
                {(lm.segments ?? [])
                  .slice()
                  .sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99))
                  .map((s) => (
                    <tr key={s.id} className={(reveal && planted.has(s.id) ? "planted" : "") + (s.rank === 1 ? " top" : "")}>
                      <td className="mono">{s.rank ?? "n/a"}</td>
                      <td>
                        {s.title}
                        {reveal && planted.has(s.id) ? <span className="badge bad" style={{ marginLeft: 8 }}>planted bad segment</span> : null}
                      </td>
                      <td className="mono">{range(s.t_start, s.t_end)}</td>
                      <td className="mono">{s.score ?? "n/a"}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
