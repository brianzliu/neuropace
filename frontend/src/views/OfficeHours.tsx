import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, errorText } from "../lib/api";
import type { OHSnapshot } from "../lib/types";
import Board from "../components/Board";
import OfficeHoursChat from "../components/OfficeHoursChat";
import OHScrubber from "../components/OHScrubber";

/** Office Hours (docs/PRODUCT.md §5a): an open conversation about a lecture. The agent replies and draws on a
 * shared board; the scrubber replays any earlier point read-only; clicking a board element asks the agent to
 * say more about it. */
export default function OfficeHours() {
  const { sessionId = "" } = useParams();
  const navigate = useNavigate();
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
    void load();
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
        <div>
          <div className="eyebrow">Office Hours</div>
          <h1 className="t-title1">Ask about the lecture</h1>
        </div>
        <div className="row">
          <button type="button" className="btn btn-sm" onClick={() => setVoiceOn((v) => !v)}>
            {voiceOn ? "Voice on" : "Voice off"}
          </button>
          <button type="button" className="btn btn-sm" onClick={() => navigate(-1)}>
            Done
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
