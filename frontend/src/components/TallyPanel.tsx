import { FORM_LABEL, FORMS, type TallySummary } from "../lib/types";
import { pct } from "../lib/format";
import { Badge } from "./Badges";
import { Group, Row } from "./Inspector";

export default function TallyPanel({ tally, compact }: { tally: TallySummary; compact?: boolean }) {
  const note = !tally.enough_data
    ? `Not enough data yet: ${tally.total_attempts} of ${tally.needed_attempts} scored cards.`
    : `Best form so far: ${FORM_LABEL[tally.rank[0]]}.`;
  return (
    <Group
      title="Your tally"
      note={
        <>
          {note}
          {!compact ? " A rescue is a form shown right before a correct answer. Scored by quiz answers only; the headset never updates this. New learners start from the average across learners." : ""}
        </>
      }
    >
      {FORMS.map((f) => {
        const st = tally.forms[f];
        return (
          <Row key={f} label={<span className="row">{FORM_LABEL[f]}{tally.pick === f ? <Badge tone="accent">pick</Badge> : null}</span>}>
            <span className="progress" style={{ width: 90 }} title={`posterior mean ${st.posterior_mean}`}>
              <i style={{ width: `${Math.round(st.posterior_mean * 100)}%` }} />
            </span>
            <span className="mono">
              {st.rescues}/{st.attempts}{st.rate !== null ? ` · ${pct(st.rate)}` : ""}
            </span>
          </Row>
        );
      })}
    </Group>
  );
}
