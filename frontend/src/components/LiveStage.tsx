import type { ReactNode } from "react";
import type { SessionState } from "../lib/sessionState";
import SessionInspector from "./SessionInspector";
import FocusTrace from "./FocusTrace";
import TranscriptPane from "./TranscriptPane";
import RecapPanel from "./RecapPanel";
import CatchupOverlay from "./CatchupOverlay";
import Chip from "./Chip";
import FocusCard from "./FocusCard";
import BrainWaves from "./BrainWaves";

interface Props {
  state: SessionState;
  onCatchupExpire: () => void;
  onCatchupDismiss: () => void;
  onOpenChip: () => void;
  onIgnoreChip: () => void;
  cycleToken: number;
  freezeCatchup?: boolean;
  /** Bottom control bar (sticky). */
  controls?: ReactNode;
  /** Header row above the document. */
  head?: ReactNode;
  inspectorExtra?: ReactNode;
  /** Show the instrumentation (trace, signal groups, rolling recap). Off for students, on for demos. */
  details: boolean;
}

/** The stage shared by the live view and the replay view: transcript, focus card, optional details, control bar, HUD and chip. */
export default function LiveStage(props: Props) {
  const { state, onCatchupExpire, onCatchupDismiss, onOpenChip, onIgnoreChip, cycleToken, freezeCatchup, controls, head, inspectorExtra, details } = props;
  const flags = state.flagOrder.map((id) => state.flags[id]).filter(Boolean);
  const last = state.focus.length ? state.focus[state.focus.length - 1] : null;
  const cfg = state.hello?.config;
  const latestRecap = state.recaps.length ? state.recaps[state.recaps.length - 1] : null;
  const errors = state.notices.filter((n) => n.level === "error");
  return (
    <>
      <div className={"stage" + (details ? "" : " calm")}>
        <div className="stage-doc">
          {head}
          <TranscriptPane words={state.words} interim={state.interim} flags={flags} now={state.t} />
        </div>
        <div className="inspector">
          <BrainWaves samples={state.raw} bands={state.bands} connected={!!state.headset?.connected} />
          <FocusCard last={last} headset={state.headset} flags={flags.length} />
          {errors.length ? (
            <div className="callout danger" style={{ margin: 0 }}>
              {errors[errors.length - 1].text}
            </div>
          ) : null}
          {details ? (
            <>
              <FocusTrace focus={state.focus} flags={flags} now={state.t} enterZ={cfg?.drop_enter_z ?? -1.25} exitZ={cfg?.drop_exit_z ?? -0.6} />
              <SessionInspector
                headset={state.headset}
                last={last}
                totem={state.totem}
                transcriptKind={state.hello?.transcript_kind ?? null}
                bestForm={state.bestForm}
                policy={state.hello?.policy ?? null}
                withheld={state.withheld}
                extraRows={inspectorExtra}
              />
              <RecapPanel recap={latestRecap} bestForm={state.bestForm} />
              {state.notices.length ? (
                <div className="group">
                  {state.notices.map((n, i) => (
                    <div key={i} className={"notice " + n.level}>
                      {n.text}
                    </div>
                  ))}
                </div>
              ) : null}
            </>
          ) : null}
        </div>
      </div>
      {controls ? <div className="controlbar">{controls}</div> : null}
      <CatchupOverlay card={state.catchup} onExpire={onCatchupExpire} onDismiss={onCatchupDismiss} cycleToken={cycleToken} freeze={freezeCatchup} />
      <Chip count={state.chipIds.length} onOpen={onOpenChip} onIgnore={onIgnoreChip} />
    </>
  );
}
