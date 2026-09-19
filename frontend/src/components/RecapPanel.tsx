import { FORM_LABEL, FORMS, type Form, type RecapMsg } from "../lib/types";
import { mmss } from "../lib/format";
import { SourceBadge } from "./Badges";

export default function RecapPanel({ recap, bestForm }: { recap: RecapMsg | null; bestForm: Form }) {
  return (
    <div className="panel recap-panel">
      <h2>
        Rolling recap{" "}
        {recap ? (
          <span className="muted small mono">
            {mmss(recap.t_from)} to {mmss(recap.t_to)}
          </span>
        ) : null}{" "}
        {recap ? <SourceBadge source={recap.source} /> : null}
      </h2>
      {!recap ? <div className="dim small">Written every 20 s from the last 30 s of transcript, in all four forms.</div> : null}
      {recap
        ? FORMS.map((f) => (
            <div key={f} className={"form" + (f === bestForm ? " best" : "")}>
              <div className="name">{FORM_LABEL[f]}{f === bestForm ? " ★" : ""}</div>
              <div className="text">{recap.forms[f]}</div>
            </div>
          ))
        : null}
    </div>
  );
}
