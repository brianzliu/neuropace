import { FORM_LABEL, FORMS, type Form, type RecapMsg } from "../lib/types";
import { mmss } from "../lib/format";
import { SourceBadge } from "./Badges";

export default function RecapPanel({ recap, bestForm }: { recap: RecapMsg | null; bestForm: Form }) {
  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">Rolling recap</span>
        <span className="row">
          {recap ? (
            <span className="mono t-footnote label-2">
              {mmss(recap.t_from)} to {mmss(recap.t_to)}
            </span>
          ) : null}
          {recap ? <SourceBadge source={recap.source} /> : null}
        </span>
      </div>
      {!recap ? <div className="t-footnote label-2">Written every 20 s from the last 30 s of transcript, in all four forms.</div> : null}
      {recap
        ? FORMS.map((f) => (
            <div key={f} className={"recap-row" + (f === bestForm ? " best" : "")}>
              <div className="name">{FORM_LABEL[f]}{f === bestForm ? " · best" : ""}</div>
              <div className="text">{recap.forms[f]}</div>
            </div>
          ))
        : null}
    </div>
  );
}
