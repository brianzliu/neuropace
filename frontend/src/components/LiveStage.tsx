import type { ReactNode } from "react";
import type { SessionState } from "../lib/sessionState";
import { StatusStrip } from "./Badges";
import FocusTrace from "./FocusTrace";
import TranscriptPane from "./TranscriptPane";
import RecapPanel from "./RecapPanel";
import CatchupOverlay from "./CatchupOverlay";
import Chip from "./Chip";

interface Props {
  state: SessionState;
  onCatchupExpire: () => void;
  onCatchupDismiss: () => void;
  onOpenChip: () => void;
  cycleToken: number;
  freezeCatchup?: boolean;
  controls?: ReactNode;
  above?: ReactNode;
  stripExtra?: ReactNode;
}

/** The demo stage shared by the live view and the replay view. */
export default function LiveStage(props: Props) {
  const { state, onCatchupExpire, onCatchupDismiss, onOpenChip, cycleToken, freezeCatchup, controls, above, stripExtra } = props;
  const flags = state.flagOrder.map((id) => state.flags[id]).filter(Boolean);
  const last = state.focus.length ? state.focus[state.focus.length - 1] : null;
  const cfg = state.hello?.config;
  const latestRecap = state.recaps.length ? state.recaps[state.recaps.length - 1] : null;
  return (
    <div className="live">
      <div className="live-left">
        {above}
        <TranscriptPane words={state.words} interim={state.interim} flags={flags} now={state.t} />
        {controls}
      </div>
      <div className="live-right">
        <StatusStrip
          headset={state.headset}
          quality={last?.quality}
          totem={state.totem}
          transcriptKind={state.hello?.transcript_kind ?? null}
          bestForm={state.bestForm}
          policy={state.hello?.policy ?? null}
          extra={stripExtra}
        />
        <FocusTrace focus={state.focus} flags={flags} now={state.t} enterZ={cfg?.drop_enter_z ?? -1} exitZ={cfg?.drop_exit_z ?? -0.5} />
        <RecapPanel recap={latestRecap} bestForm={state.bestForm} />
        {state.withheld > 0 ? <div className="withheld">withheld (study): {state.withheld}</div> : null}
        {state.notices.length ? (
          <div className="panel notices">
            {state.notices.map((n, i) => (
              <div key={i} className={n.level}>
                {n.text}
              </div>
            ))}
          </div>
        ) : null}
      </div>
      <CatchupOverlay card={state.catchup} onExpire={onCatchupExpire} onDismiss={onCatchupDismiss} cycleToken={cycleToken} freeze={freezeCatchup} />
      <Chip count={state.chipIds.length} onOpen={onOpenChip} />
    </div>
  );
}
