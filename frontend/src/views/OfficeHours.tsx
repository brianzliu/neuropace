import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, errorText } from "../lib/api";
import type { OHSnapshot } from "../lib/types";
import Board from "../components/Board";
import OfficeHoursChat from "../components/OfficeHoursChat";
import OHScrubber from "../components/OHScrubber";
import SessionBack from "../components/BackLink";

/** Office Hours (docs/PRODUCT.md §5a): an open conversation about a lecture. The agent replies and draws on a
 * shared board; the scrubber replays any earlier point read-only; clicking a board element asks the agent to
 * say more about it. */
export default function OfficeHours() {
  const { sessionId = "" } = useParams();
  const [search] = useSearchParams();
  const original = search.get("original");
  const [snap, setSnap] = useState<OHSnapshot | null>(null);
  const [scrubOrd, setScrubOrd] = useState<number | null>(null); // null = live (now)
  const [voiceOn, setVoiceOn] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const load = async (uptoOrd?: number) => {
    try {
      const s = await api.officeHoursSnapshot(sessionId, uptoOrd);
      setSnap(s);
    } catch (e) {
      setErr(errorText(e));
    }
  };

  useEffect(() => {
    (async () => {
      try {
        const s = await api.officeHoursSnapshot(sessionId);
        // A fresh session opened from Review (original set): kick off the same job Private tutoring used
        // to do — walk through what was missed — instead of a blank board waiting on the student to type.
        if (s.messages.length === 0 && original) {
          await api.officeHoursSend(sessionId, "What did I miss in this lecture? Walk me through it.");
          setSnap(await api.officeHoursSnapshot(sessionId));
        } else {
          setSnap(s);
        }
      } catch (e) {
        setErr(errorText(e));
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  useEffect(() => {
    if (scrubOrd != null) void load(scrubOrd);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scrubOrd]);

  if (err) return <div className="page narrow"><div className="callout danger">{err}</div></div>;
  if (!snap) return <div className="page narrow"><div className="loading">Loading…</div></div>;

  const live = scrubOrd == null;

  const expand = async (elementId: string) => {
    try {
      await api.officeHoursExpand(sessionId, elementId);
      await load();
    } catch (e) {
      setErr(errorText(e));
    }
  };

  return (
    <div className="office-hours">
      <header className="oh-header row between">
        <SessionBack />
        <div className="row">
          {original ? (
            <Link className="btn btn-sm" to={`/restudy/${original}?mode=manual`} title="Switch to a quiz-first self-test, no agent conversation">
              Review on my own
            </Link>
          ) : null}
          <button type="button" className="btn btn-sm" onClick={() => setVoiceOn((v) => !v)}>
            {voiceOn ? "Voice on" : "Voice off"}
          </button>
        </div>
      </header>
      <OHScrubber maxOrd={snap.ord} ord={scrubOrd ?? snap.ord} live={live} onChange={setScrubOrd} />
      <div className="oh-layout">
        <Board elements={snap.board} onExpand={live ? expand : () => undefined} />
        <OfficeHoursChat
          sessionId={sessionId}
          messages={snap.messages}
          voiceOn={voiceOn}
          disabled={!live}
          onSent={() => void load()}
        />
      </div>
    </div>
  );
}
