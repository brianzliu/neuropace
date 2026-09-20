import { useEffect, useState } from "react";
import { api, errorText } from "../lib/api";
import type { JargonResponse, ScholarGap, ScholarResponse } from "../lib/types";
import { range } from "../lib/format";
import "./scholar.css";

/** Scholarly sources for a session's missed moments, fetched lazily from the scholar sidecar
 * (`/api/sessions/:id/scholar`). The notes page never waits on this: it renders first, and this fills in
 * (or says plainly that sources are unavailable) a moment later. Sources come from OpenAlex and are labelled
 * as such; nothing here is written by the tutor model. */
export function useScholar(sessionId: string, enabled = true) {
  const [data, setData] = useState<ScholarResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const load = (refresh = false) => {
    if (!sessionId) return;
    setLoading(true);
    setErr(null);
    api
      .scholar(sessionId, refresh)
      .then(setData)
      .catch((e) => setErr(errorText(e)))
      .finally(() => setLoading(false));
  };
  useEffect(() => {
    if (enabled) load();
  }, [sessionId, enabled]); // eslint-disable-line react-hooks/exhaustive-deps
  const byGap = new Map<string, ScholarGap>();
  for (const g of data?.gaps ?? []) byGap.set(g.gap_id, g);
  return { data, err, loading, byGap, reload: () => load(true) };
}

function fmtCites(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k`;
  return String(n);
}

/** The "Go deeper" strip under one moment. */
export function ScholarStrip({ gap, loading }: { gap: ScholarGap | undefined; loading: boolean }) {
  if (!gap && loading) {
    return (
      <div className="note-row scholar-row">
        <div className="k">Go deeper</div>
        <div className="label-3 t-caption">Looking up sources on OpenAlex…</div>
      </div>
    );
  }
  if (!gap) return null;
  if (gap.source === "disabled") return null;
  if (gap.source === "unavailable" || gap.source === "empty" || gap.items.length === 0) {
    return (
      <div className="note-row scholar-row">
        <div className="k">Go deeper</div>
        <div className="label-3 t-caption">
          {gap.source === "unavailable" ? "Sources unavailable right now (OpenAlex could not be reached)." : "No open-access sources matched this moment."}
        </div>
      </div>
    );
  }
  return (
    <div className="note-row scholar-row">
      <div className="k">Go deeper</div>
      <div>
        <ul className="scholar-list">
          {gap.items.map((r) => (
            <li key={r.id} className="scholar-item">
              <a href={r.url} target="_blank" rel="noreferrer noopener" className="scholar-title">
                {r.title}
              </a>
              <div className="scholar-meta label-3 t-caption">
                {r.authors.join(", ")}
                {r.more_authors ? ` +${r.more_authors}` : ""}
                {r.year ? ` · ${r.year}` : ""}
                {r.venue ? ` · ${r.venue}` : ""}
                {r.kind === "review" ? " · review" : ""}
                {` · ${fmtCites(r.cited_by)} citations`}
              </div>
              {r.why ? <div className="scholar-why label-2">{r.why}</div> : null}
            </li>
          ))}
        </ul>
        <div className="scholar-attrib label-3 t-caption">
          Sources via OpenAlex{gap.source === "cache" ? " (cached)" : ""} · searched “{gap.query}”
        </div>
      </div>
    </div>
  );
}

/** The lecture's field, as OpenAlex labels it: a one-line breadcrumb over the notes. */
export function ScholarTopicLine({ data }: { data: ScholarResponse | null }) {
  const t = data?.topics?.topics?.[0];
  if (!t) return null;
  const src = data?.topics.source;
  return (
    <div className="scholar-topic label-3 t-caption" title={src === "local" ? "Labelled offline from the bundled OpenAlex topic table" : "Labelled by OpenAlex"}>
      {t.path}
      {src === "local" ? " · offline label" : ""}
    </div>
  );
}

/** Where the lecture got dense, from the transcript alone: 20 s windows whose words are unusually
 * field-specific (scored against OpenAlex abstracts) compared with the rest of the same lecture. This is
 * content-based risk (PLAN Part III), shown beside the sensor-flagged moments, not merged with them. */
export function useJargon(sessionId: string, enabled = true) {
  const [data, setData] = useState<JargonResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (!enabled || !sessionId) return;
    api.jargon(sessionId).then(setData).catch((e) => setErr(errorText(e)));
  }, [sessionId, enabled]);
  return { data, err };
}

export function JargonSpans({ data }: { data: JargonResponse | null }) {
  if (!data || !data.table.available) return null;
  return (
    <section className="stack jargon-block">
      <div className="eyebrow">Where the lecture got dense</div>
      {data.spans.length === 0 ? (
        <div className="label-3 t-caption">No stretch stood out from the rest of this lecture.</div>
      ) : (
        <ul className="scholar-list">
          {data.spans.map((s) => (
            <li key={s.t_start} className="scholar-item">
              <div>
                <span className="scholar-title">{range(s.t_start, s.t_end)}</span>
                <span className="label-3 t-caption"> · {s.peak_z.toFixed(1)}σ above the lecture's own level</span>
              </div>
              <div className="jargon-terms">
                {s.terms.map((t) => (
                  <span key={t.term} className={"jargon-term" + (t.known ? "" : " unknown")} title={t.known ? `${t.field ?? ""} · specificity ${t.spec}` : "not in the table (rare or a name)"}>
                    {t.term}
                  </span>
                ))}
              </div>
            </li>
          ))}
        </ul>
      )}
      <div className="scholar-attrib label-3 t-caption">
        From the transcript alone, against OpenAlex abstracts{data.table.dev_sized ? " (small development table — expect misses)" : ""}.
      </div>
    </section>
  );
}
