import { useEffect, useRef, useState } from "react";
import { api, errorText } from "../lib/api";
import type { OHSnapshot } from "../lib/types";
import Board from "../components/Board";
import OfficeHoursChat from "../components/OfficeHoursChat";

/** Whiteboard (docs/PRODUCT.md §5a), Review's second mode: an open conversation about a lecture. The agent
 * replies and draws on a shared board; clicking a board element asks it to say more. sessionId is the
 * office_hours session, original the lecture session it is about. */
export default function OfficeHours({ sessionId, original }: { sessionId: string; original: string | null }) {
  const [snap, setSnap] = useState<OHSnapshot | null>(null);
  const [voiceOn, setVoiceOn] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [pendingUserText, setPendingUserText] = useState<string | null>(null);
  const [pendingReplyText, setPendingReplyText] = useState<string | null>(null);
  const kickedOff = useRef(false);

  const load = async () => {
    try {
      const s = await api.officeHoursSnapshot(sessionId);
      setSnap(s);
    } catch (e) {
      setErr(errorText(e));
    }
  };

  // Streams one turn: the board fills in element by element as the model draws it, and the reply
  // text (usually ready well before the board is) drives the transient bubble + voice playback.
  // Resolves with the reply text once it's known.
  const sendStream = async (text: string): Promise<string> => {
    setPendingUserText(text);
    setPendingReplyText(null);
    let replyText = "";
    try {
      await api.officeHoursSendStream(sessionId, text, (event) => {
        if (event.type === "reply") {
          replyText = event.text;
          setPendingReplyText(event.text);
        } else if (event.type === "board") {
          setSnap((s) => (s ? { ...s, board: event.board } : s));
        }
      });
    } finally {
      setPendingUserText(null);
      setPendingReplyText(null);
      await load();
    }
    return replyText;
  };

  useEffect(() => {
    (async () => {
      // Render the board+chat shell immediately with whatever's already there — never block on a
      // full-page "generating" interstitial, even for the very first turn.
      const s = await api.officeHoursSnapshot(sessionId).catch((e) => {
        setErr(errorText(e));
        return null;
      });
      if (s) setSnap(s);
      // A fresh session opened from Review (original set): kick off the same job Private tutoring used
      // to do — walk through what was missed — instead of a blank board waiting on the student to type.
      if (s && s.messages.length === 0 && original && !kickedOff.current) {
        kickedOff.current = true;
        try {
          await sendStream("What did I miss in this lecture? Walk me through it.");
        } catch (e) {
          setErr(errorText(e));
        }
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  if (err) return <div className="page narrow"><div className="callout danger">{err}</div></div>;
  if (!snap) return <div className="page narrow"><div className="loading">Loading…</div></div>;

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
      <div className="oh-toolbar row">
        <button
          type="button"
          className="btn btn-sm"
          onClick={() => setVoiceOn((v) => !v)}
          title="Whether the tutor's replies are read aloud"
        >
          {voiceOn ? "🔊 Read aloud: on" : "🔈 Read aloud: off"}
        </button>
      </div>
      <div className="oh-layout">
        <Board elements={snap.board} onExpand={expand} />
        <OfficeHoursChat
          sessionId={sessionId}
          messages={snap.messages}
          voiceOn={voiceOn}
          disabled={false}
          onSend={sendStream}
          onVoiceClipSent={() => void load()}
          pendingUserText={pendingUserText}
          pendingReplyText={pendingReplyText}
        />
      </div>
    </div>
  );
}
