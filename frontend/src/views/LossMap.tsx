import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../lib/api";
import type { LectureFull, LossMap } from "../lib/types";
import { mmss, range } from "../lib/format";
import { Badge } from "../components/Badges";

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
  if (err) return <div className="page narrow"><div className="card error-text">{err}</div></div>;
  if (!lm || !lecture) return <div className="page narrow"><div className="loading">Loading…</div></div>;
  const planted = new Set((lecture.segments ?? []).filter((s) => s.planted_bad).map((s) => s.id));
  const bins = lm.bins ?? [];
  const maxLoss = Math.max(0.5, ...bins.map((b) => b.loss ?? 0));
  const minLoss = Math.min(0, ...bins.map((b) => b.loss ?? 0));
  const span = maxLoss - minLoss || 1;
  const peak = lm.peak;
  return (
    <div className="page narrow">
      <div className="page-head">
        <div>
          <h1 className="t-title1">Lecture loss map</h1>
          <div className="sub">
            {lecture.title}. Where the room was lost, pooled and anonymous: it grades the lecture, never a student.
          </div>
        </div>
        <span className="row">
          <Badge tone="accent">{lm.n} learner{lm.n === 1 ? "" : "s"}</Badge>
          <button className="btn btn-sm" onClick={() => void load()}>
            Refresh
          </button>
        </span>
      </div>
      <div className="stack-lg">
        {!lm.ready ? (
          <div className="empty-state">Needs 2 or more learners on this lecture ({lm.n} so far).</div>
        ) : (
          <>
            <div className="card">
              <div className="card-header">
                <span className="card-title">Pooled loss per {lm.bin_seconds} s</span>
                {peak ? (
                  <span className="t-footnote label-2">
                    peak 40 s <span className="mono warning-text">{range(peak.t_start, peak.t_end)}</span>
                  </span>
                ) : null}
              </div>
              <div className="lossbars">
                {bins.map((b) => {
                  const inPeak = !!peak && b.t >= peak.t_start && b.t < peak.t_end;
                  const h = b.loss === null ? 0 : ((b.loss - minLoss) / span) * 100;
                  return <div key={b.t} className={"bar" + (inPeak ? " peak" : "") + (b.loss === null ? " empty" : "")} style={{ height: `${Math.max(2, h)}%` }} data-tip={`${mmss(b.t)}  loss ${b.loss ?? "n/a"}  n=${b.n}`} />;
                })}
              </div>
              <div className="axis">
                <span>{mmss(0)}</span>
                <span>{mmss(lecture.duration ?? 0)}</span>
              </div>
            </div>
            <div className="card" style={{ padding: 0 }}>
              <div className="card-header" style={{ padding: "12px 12px 0" }}>
                <span className="card-title">Segments</span>
                {planted.size ? (
                  <button className="btn btn-sm" onClick={() => setReveal((r) => !r)}>
                    {reveal ? "Hide planted segment" : "Reveal planted segment"}
                  </button>
                ) : null}
              </div>
              <table className="table" style={{ marginTop: 8 }}>
                <thead>
                  <tr>
                    <th>rank</th>
                    <th>segment</th>
                    <th>time</th>
                    <th className="num">loss score</th>
                  </tr>
                </thead>
                <tbody>
                  {(lm.segments ?? [])
                    .slice()
                    .sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99))
                    .map((s) => (
                      <tr key={s.id} className={reveal && planted.has(s.id) ? "highlight" : ""}>
                        <td>{s.rank ? <Badge tone={s.rank === 1 ? "danger" : "neutral"}>{s.rank}</Badge> : <span className="label-3">n/a</span>}</td>
                        <td>
                          {s.title}
                          {reveal && planted.has(s.id) ? <span style={{ marginLeft: 8 }}><Badge tone="danger">planted bad segment</Badge></span> : null}
                        </td>
                        <td className="mono label-2">{range(s.t_start, s.t_end)}</td>
                        <td className="num mono">{s.score ?? "n/a"}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
