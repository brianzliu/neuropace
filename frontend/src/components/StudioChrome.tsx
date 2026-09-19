import { Link } from "react-router-dom";

/** Honest connection states shared by Studio setup and live capture (agent C). */
export type ConnectionState = "connected" | "simulated" | "pending" | "off";

export interface ConnectionPill {
  key: string;
  label: string;
  state: ConnectionState;
  detail?: string;
}

const STATE_WORD: Record<ConnectionState, string> = {
  connected: "Connected",
  simulated: "Simulated",
  pending: "Pending",
  off: "Off",
};

const STATE_DOT: Record<ConnectionState, string> = {
  connected: "on",
  simulated: "",
  pending: "warn",
  off: "off",
};

/** EEG / button / transcription / board-camera pills. Green only for verified non-sim state. */
export function ConnectionPills({ pills }: { pills: ConnectionPill[] }) {
  return (
    <div className="strip" role="list" aria-label="Connection status">
      {pills.map((p) => (
        <span key={p.key} className="item" role="listitem" title={p.detail}>
          <span className={"dotled " + STATE_DOT[p.state]} aria-hidden="true" />
          {p.label} <b>{STATE_WORD[p.state]}</b>
        </span>
      ))}
    </div>
  );
}

/** `Setup → Live` stepper for the dedicated Studio window. Visual only; never re-enters setup mid-session. */
export function StudioSteps({ current }: { current: "setup" | "live" }) {
  return (
    <div className="row" style={{ gap: "0.6rem" }}>
      <span className={"badge" + (current === "setup" ? " accent" : "")} aria-current={current === "setup" ? "step" : undefined}>
        1 · Setup
      </span>
      <span className="muted" aria-hidden="true">→</span>
      <span className={"badge" + (current === "live" ? " accent" : "")} aria-current={current === "live" ? "step" : undefined}>
        2 · Live
      </span>
    </div>
  );
}

export function StudioBackLink({ leaveNote }: { leaveNote?: string }) {
  return (
    <Link className="small" to="/" title={leaveNote}>
      Back to dashboard
    </Link>
  );
}
