import { useState } from "react";

/** A local tutorial, deliberately separate from real session/tap events. */
export default function DeskObject() {
  const [pressed, setPressed] = useState(false);
  return (
    <div className={"desk-object" + (pressed ? " is-pressed" : "")}>
      <div className="desk-scene">
        <div className="desk-ring" aria-hidden="true" />
        <div className="desk-note" aria-hidden="true"><span>One moment<br />at a time.</span><i /><i /><i /></div>
        <div className="desk-device">
          <div className="device-face">
            <span className="device-wordmark" aria-hidden="true">neurospace</span>
            <div className="device-leds" aria-hidden="true"><i /><i /><i /></div>
            <button className="physical-button" aria-pressed={pressed} aria-describedby="button-practice" onClick={() => setPressed(!pressed)}>
              <span className="button-symbol" aria-hidden="true">{pressed ? "✓" : "+"}</span>
              <span>{pressed ? "Try again" : "I’m stuck"}</span>
            </button>
            <span className="device-caption" aria-hidden="true">a place to pick up again</span>
          </div>
        </div>
        <span className="desk-pebble" aria-hidden="true" /><span className="desk-shadow" aria-hidden="true" />
      </div>
      <div className="practice-caption" id="button-practice" aria-live="polite">
        <b>{pressed ? "That’s the idea." : "Give the button a try."}</b>
        <span>{pressed ? "In a session, a press saves the moment and requests a catch-up." : "A small way to say “hold that thought”."}</span>
        <small>Interactive preview · no session data is recorded</small>
      </div>
    </div>
  );
}
