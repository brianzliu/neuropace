import { useLibrary } from "./Library";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, errorText } from "../lib/api";
import { ARTIFACT_FAMILY, ARTIFACT_KINDS, ARTIFACT_LABEL, FORM_LABEL, type ArtifactKind, type GapArtifacts, type ReteachContent } from "../lib/types";
import ArtifactView, { stepsOf } from "../components/ArtifactView";
import { Badge, SourceBadge } from "../components/Badges";
import { range } from "../lib/format";

/** For the team (docs/PRODUCT.md §3): every explanation NeuroPace generated for every moment of a session, one template
 * at a time with its reveal steps, so each renderer can be checked on its own. `/team/artifacts/sample` renders
 * built-in sample data for all ten templates without a session or a model. */
export default function Artifacts() {
  const { sessionId = "sample" } = useParams();
  const [gaps, setGaps] = useState<GapArtifacts[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const sample = sessionId === "sample";
  const library = useLibrary();
  useEffect(() => {
    if (sample) {
      setGaps([SAMPLE]);
      return;
    }
    api
      .artifacts(sessionId)
      .then((r) => setGaps(r.gaps))
      .catch((e) => setErr(errorText(e)));
  }, [sessionId, sample]);
  if (err) return <div className="page narrow"><div className="callout danger">{err}</div></div>;
  if (!gaps) return <div className="page narrow"><div className="loading">Loading…</div></div>;
  return (
    <div className="page">
      <header className="hero">
        <div className="eyebrow">For the team</div>
        <h1 className="t-title1">{sample ? "Every template, sample data" : "Every explanation for this lecture"}</h1>
        <p className="sub">
          {sample
            ? "The ten renderings with built-in data: what each template looks like before a model fills it."
            : "What the model filled for each moment, template by template. The plan names which visual and which doing template the content called for; the other families always exist."}
        </p>
        <div className="row">
          {!sample && !library ? (
            <Link className="btn btn-sm" to={`/lecture/${sessionId}`}>
              The lecture
            </Link>
          ) : null}
          <Link className="btn btn-sm" to={sample ? "/team" : "/team/artifacts/sample"}>
            {sample ? "Team" : "Sample data"}
          </Link>
        </div>
      </header>
      {gaps.length === 0 ? <div className="empty-state">No moments in this session.</div> : null}
      <div className="stack-lg">
        {gaps.map((g) => (
          <GapCard key={g.id} g={g} />
        ))}
      </div>
    </div>
  );
}

function contentOf(g: GapArtifacts, kind: ArtifactKind): ReteachContent {
  const a = g.artifacts;
  if (kind === "words") return a.summary || a.key_idea ? { summary: a.summary ?? "", key_idea: a.key_idea ?? { term: "", definition: "", example: "" } } : null;
  const v = a[kind];
  if (!v) return null;
  if (typeof v === "object" && (v as { applicable?: boolean }).applicable === false) return null;
  return v as ReteachContent;
}

function GapCard({ g }: { g: GapArtifacts }) {
  const kinds = useMemo(() => ARTIFACT_KINDS.filter((k) => contentOf(g, k) !== null), [g]);
  const [kind, setKind] = useState<ArtifactKind>(kinds[0] ?? "words");
  const [step, setStep] = useState(0);
  const content = contentOf(g, kind);
  const n = stepsOf(kind, content);
  useEffect(() => setStep(0), [kind]);
  const plan = g.artifacts.plan;
  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">
          Moment {g.ord + 1} · {range(g.t_start, g.t_end)}
          {g.note?.key_term ? ` · ${g.note.key_term}` : ""}
        </span>
        <span className="row">
          {g.id === "sample" ? <Badge>sample data</Badge> : <SourceBadge source={g.package_source} />}
          {plan ? (
            <Badge tone="accent" title={plan.why}>
              plan: {ARTIFACT_LABEL[plan.visual]} · {ARTIFACT_LABEL[plan.doing]}
            </Badge>
          ) : null}
        </span>
      </div>
      {plan?.why ? <div className="t-footnote label-2">{plan.why}</div> : null}
      <div className="tabs">
        {kinds.map((k) => (
          <button key={k} className={"tab" + (k === kind ? " is-active" : "")} onClick={() => setKind(k)}>
            <span className="tab-fam">{FORM_LABEL[ARTIFACT_FAMILY[k]]}</span>
            {ARTIFACT_LABEL[k]}
            {g.sources?.[k] ? <span className={"tab-src " + g.sources[k]}>{g.sources[k]}</span> : null}
          </button>
        ))}
      </div>
      <div className="preview">
        <ArtifactView key={kind} kind={kind} content={content} step={step} />
      </div>
      {n > 1 ? (
        <div className="row">
          <button className="btn btn-sm" onClick={() => setStep((s) => Math.max(0, s - 1))} disabled={step === 0}>
            Back
          </button>
          <span className="t-footnote mono">
            {step + 1}/{n}
          </span>
          <button className="btn btn-sm btn-blue" onClick={() => setStep((s) => Math.min(n - 1, s + 1))} disabled={step >= n - 1}>
            Next
          </button>
        </div>
      ) : null}
    </div>
  );
}

const SAMPLE_ANIMATION = `<div><svg viewBox="0 0 600 260" width="100%">
<circle cx="80" cy="60" r="10" fill="#ff9600"/><text x="80" y="40" text-anchor="middle" font-size="13" fill="currentColor">sat A</text>
<circle cx="300" cy="40" r="10" fill="#ff9600"/><text x="300" y="20" text-anchor="middle" font-size="13" fill="currentColor">sat B</text>
<circle cx="520" cy="70" r="10" fill="#ff9600"/><text x="520" y="50" text-anchor="middle" font-size="13" fill="currentColor">sat C</text>
<circle id="you" cx="300" cy="220" r="9" fill="none" stroke="currentColor" stroke-width="2"/><text x="300" y="248" text-anchor="middle" font-size="13" fill="currentColor">you</text>
<circle id="a" cx="80" cy="60" r="6" fill="#1cb0f6"/><circle id="b" cx="300" cy="40" r="6" fill="#1cb0f6"/><circle id="c" cx="520" cy="70" r="6" fill="#1cb0f6"/>
<text id="msg" x="300" y="140" text-anchor="middle" font-size="14" fill="currentColor"></text>
</svg><script>(function(){var S=[[80,60,'a'],[300,40,'b'],[520,70,'c']],Y=[300,220],T=6000,msg=document.getElementById('msg');
function d(p){return Math.hypot(Y[0]-p[0],Y[1]-p[1]);}var m=Math.max.apply(null,S.map(d));
function f(t){var u=(t%T)/T*1.3;var done=0;S.forEach(function(p){var k=Math.min(1,u*m/d(p));var e=document.getElementById(p[2]);e.setAttribute('cx',p[0]+(Y[0]-p[0])*k);e.setAttribute('cy',p[1]+(Y[1]-p[1])*k);if(k>=1)done++;});
msg.textContent=done===0?'all three signals leave now':done<3?done+' arrived, '+(3-done)+' still travelling':'all three arrived: three distances';requestAnimationFrame(f);}requestAnimationFrame(f);})();</script></div>`;

/** Built-in data for every template: the renderers' own test page. */
const SAMPLE: GapArtifacts = {
  id: "sample",
  ord: 0,
  t_start: 0,
  t_end: 42,
  span_text: "",
  context_text: "",
  question: null,
  flag_ids: [],
  status: "open",
  note: { what_was_said: "", key_term: "trilateration", definition: "", connection: "" },
  package_source: "llm",
  artifacts: {
    summary: "Each satellite broadcasts the time. Your phone measures how late each signal arrives and turns the delay into a distance. Three distances pin you down; a fourth fixes your cheap clock.",
    key_idea: { term: "trilateration", definition: "finding a position from distances to known points", example: "three spheres meet at two points, one of them is in space" },
    plan: { visual: "animation", doing: "steps", why: "signals travelling from satellites are a mechanism in motion" },
    analogy: {
      story: "Three friends each shout your name from a known street corner. From how late each shout reaches you, you know how far each corner is, and only one spot on the map fits all three.",
      mapping: [
        { idea: "satellite", everyday: "a friend at a known corner" },
        { idea: "signal delay", everyday: "how late the shout arrives" },
        { idea: "fourth satellite", everyday: "a friend who also tells you the exact time" },
      ],
      caveat: "shouts bend around buildings; radio mostly does not, so multipath is smaller than the analogy suggests",
    },
    diagram: {
      title: "from delays to a position",
      nodes: [
        { id: "n1", label: "satellite time", shape: "pill", tone: "butter" },
        { id: "n2", label: "delay", shape: "card", tone: "peach" },
        { id: "n3", label: "distance", shape: "card", tone: "lilac" },
        { id: "n4", label: "position", shape: "ellipse", tone: "mint" },
      ],
      edges: [
        { from_id: "n1", to_id: "n2", label: "arrives late" },
        { from_id: "n2", to_id: "n3", label: "times c" },
        { from_id: "n3", to_id: "n4", label: "three of them" },
      ],
      steps: [
        { highlight: ["n1"], caption: "every satellite shouts the time" },
        { highlight: ["n1", "n2"], caption: "your phone hears it late" },
        { highlight: ["n2", "n3"], caption: "delay times the speed of light is a distance" },
        { highlight: ["n3", "n4"], caption: "three distances cross at your position" },
      ],
    },
    chart: {
      kind: "bar",
      title: "error budget the lecturer gave",
      unit: "meters",
      points: [
        { label: "receiver clock", value: 30 },
        { label: "ionosphere", value: 5 },
        { label: "multipath", value: 5 },
        { label: "satellite clock", value: 2 },
      ],
      takeaway: "the receiver clock dominates, which is why a fourth satellite matters",
    },
    plot: {
      title: "position error as satellites are added",
      x_label: "satellites in view",
      y_label: "error",
      series: [
        { name: "without clock fix", points: [{ x: 3, y: 30 }, { x: 4, y: 30 }, { x: 5, y: 28 }, { x: 6, y: 27 }, { x: 8, y: 26 }] },
        { name: "with clock fix", points: [{ x: 3, y: 30 }, { x: 4, y: 8 }, { x: 5, y: 6 }, { x: 6, y: 5 }, { x: 8, y: 4 }] },
      ],
      annotations: [{ x: 4, y: 8, text: "fourth satellite" }],
      illustrative: true,
      takeaway: "the fourth satellite is the big drop; the rest is polish",
    },
    timeline: {
      title: "one fix, in order",
      events: [
        { when: "t = 0", label: "satellite sends the time", detail: "the atomic clock stamps the message" },
        { when: "+67 ms", label: "phone hears it", detail: "about 20,000 km at the speed of light" },
        { when: "+67 ms", label: "delay becomes distance", detail: "multiply by c" },
        { when: "3 signals", label: "two candidate points", detail: "one is out in space and is dropped" },
        { when: "4 signals", label: "clock error solved", detail: "the fourth equation fixes the phone's cheap clock" },
      ],
      takeaway: "everything happens within a tenth of a second",
    },
    compare: {
      title: "satellite clock vs phone clock",
      left: "satellite",
      right: "phone",
      rows: [
        { aspect: "clock", left_value: "atomic, nanoseconds", right_value: "quartz, drifts by microseconds" },
        { aspect: "what it knows", left_value: "its own orbit and time", right_value: "nothing until signals arrive" },
        { aspect: "role", left_value: "shouts the time", right_value: "listens and solves" },
      ],
      verdict: "the phone's bad clock is the unknown the fourth satellite pays for",
    },
    animation: {
      title: "signals travelling from three satellites",
      caption: "three pulses leave at the same moment; the one from the farthest satellite arrives last",
      html: SAMPLE_ANIMATION,
    },
    steps: {
      title: "get a fix by hand",
      steps: ["read the send time in each message", "subtract it from the arrival time", "multiply each delay by the speed of light", "intersect the three spheres", "use the fourth to correct your clock"],
    },
    example: {
      title: "one satellite, one distance",
      lines: ["signal sent at 12:00:00.000", "heard at 12:00:00.067", "delay = 67 ms", "67 ms times 300,000 km/s"],
      result: "distance = 20,100 km",
    },
  },
  sources: {},
};
