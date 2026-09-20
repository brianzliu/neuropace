import { useState } from "react";
import { backendFetch } from "../../lib/backend";
import type { Curriculum, Understanding, UnderstandingStage } from "../../lib/dashboardTypes";

interface CurriculumSectionProps {
  curriculum: Curriculum | undefined;
  understanding: Understanding | undefined;
  organizing: boolean;
  learnerId: string;
  onSave: (curriculum: Curriculum) => Promise<void>;
}

const STAGE_ORDER: UnderstandingStage[] = ["review", "beginner", "intermediate", "advanced", "no_evidence"];
const STAGE_LABEL: Record<UnderstandingStage, string> = {
  review: "To review",
  beginner: "Beginner",
  intermediate: "Intermediate",
  advanced: "Advanced",
  no_evidence: "No evidence yet",
};

/**
 * Dashboard compartment 3: curriculum stages estimated from the learner's own
 * saved moments and review outcomes, plus the syllabus editor. Stages are
 * coaching estimates labelled with their source ("Model reading" vs "Rules
 * estimate"); they never set completion, review outcomes, or grades. The
 * stored checkbox field is legacy only and is no longer shown or toggled.
 */
export default function CurriculumSection({ curriculum, understanding, organizing, learnerId, onSave }: CurriculumSectionProps) {
  const topics = curriculum?.topics ?? [];
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [syllabus, setSyllabus] = useState("");
  const [syllabusMessage, setSyllabusMessage] = useState("");
  const [course, setCourse] = useState("");

  const startEditing = () => {
    setCourse(curriculum?.title ?? "My curriculum");
    setSyllabus(curriculum?.topics.map((t) => t.title).join("\n") ?? "");
    setSyllabusMessage("");
    setEditing(true);
  };

  const parseSyllabus = async (file?: File) => {
    setBusy(true);
    setSyllabusMessage("");
    try {
      if (file && file.size > 2_000_000) throw new Error("Choose a file smaller than 2 MB.");
      const body = new FormData();
      if (file) body.append("file", file);
      else body.append("text", syllabus);
      const response = await backendFetch(`/api/learners/${learnerId}/syllabus/parse`, {
        method: "POST",
        body,
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Could not read syllabus");
      setCourse(result.curriculum.title);
      setSyllabus(result.curriculum.topics.map((t: { title: string }) => t.title).join("\n"));
      setSyllabusMessage(
        result.source === "lines"
          ? "Imported as text lines. Edit these into topics before saving."
          : "Topics extracted. Review and edit them before saving.",
      );
    } catch (e) {
      setSyllabusMessage(String(e));
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    const old = new Map(topics.map((t) => [t.title, t.completed]));
    setBusy(true);
    try {
      await onSave({
        title: course.trim() || "My curriculum",
        topics: [...new Set(syllabus.split("\n").map((s) => s.trim()).filter(Boolean))].map(
          (title) => ({ title, completed: old.get(title) ?? false }),
        ),
      });
      setEditing(false);
    } finally {
      setBusy(false);
    }
  };

  const rows = topics.map(
    (topic) =>
      understanding?.topics.find((row) => row.topic === topic.title) ?? {
        topic: topic.title,
        stage: "no_evidence" as UnderstandingStage,
        reason: "No saved moments mention this topic yet.",
        gap_ids: [],
        evidence: { resolved: 0, open: 0, exhausted: 0, total: 0 },
      },
  );
  const counts = Object.fromEntries(
    STAGE_ORDER.map((stage) => [stage, rows.filter((row) => row.stage === stage).length]),
  ) as Record<UnderstandingStage, number>;
  const organized = understanding?.source === "llm" || understanding?.source === "cache";
  const sourceLabel = organizing ? "Organizing…" : organized ? "Model reading" : "Rules estimate";
  const barLabel = STAGE_ORDER.filter((stage) => counts[stage] > 0)
    .map((stage) => `${counts[stage]} ${STAGE_LABEL[stage].toLowerCase()}`)
    .join(", ");

  return (
    <section className="curriculum-section" aria-label="Curriculum">
      <div className="dashboard-section-heading">
        <div>
          <h2>{curriculum?.title ?? "Your curriculum"}</h2>
        </div>
        <button className="ghost" disabled={!curriculum} onClick={startEditing}>
          {topics.length ? "Edit syllabus" : "Add syllabus"}
        </button>
      </div>
      {editing ? (
        <form
          className="syllabus-form"
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
        >
          <label>
            Upload your syllabus
            <input
              type="file"
              accept=".pdf,.txt,.md"
              disabled={busy}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void parseSyllabus(file);
                e.target.value = "";
              }}
            />
          </label>
          <span className="small muted">
            PDF, text, or Markdown · up to 2 MB. Text extraction may use the configured model; you
            review the topics before saving.
          </span>
          <label>
            Course name
            <input value={course} maxLength={200} onChange={(e) => setCourse(e.target.value)} />
          </label>
          <label>
            Syllabus topics
            <textarea
              value={syllabus}
              onChange={(e) => setSyllabus(e.target.value)}
              placeholder="One topic per line. Paste the topic list from your syllabus."
              rows={7}
              required
            />
          </label>
          <button
            type="button"
            className="ghost"
            disabled={busy || !syllabus.trim()}
            onClick={() => void parseSyllabus()}
          >
            {busy ? "Working…" : "Extract topics from pasted syllabus"}
          </button>
          {syllabusMessage && (
            <p className="small muted" role="status">
              {syllabusMessage}
            </p>
          )}
          <p className="small muted">
            Topics are labels for grouping. Your stage is estimated from saved moments and review
            results — editing this list never sets it. Up to 100 topics.
          </p>
          <div className="row">
            <button className="primary" disabled={busy}>
              Save syllabus
            </button>
            <button type="button" onClick={() => setEditing(false)}>
              Cancel
            </button>
          </div>
        </form>
      ) : curriculum === undefined ? (
        <p className="muted" role="status">
          Loading your saved moments…
        </p>
      ) : topics.length ? (
        <>
          <div className="understanding-head">
            <p className="coverage-note">
              <span>Estimated from your saved moments and review results.</span>
              <span>Not a grade — your own review changes it.</span>
            </p>
            <span className={"organize-source" + (organized ? " is-suggested" : organizing ? " is-organizing" : "")}>
              {sourceLabel}
            </span>
          </div>
          <div className="stage-bar" role="img" aria-label={barLabel}>
            {STAGE_ORDER.filter((stage) => counts[stage] > 0).map((stage) => (
              <i key={stage} className={"stage-seg is-" + stage} style={{ flexGrow: counts[stage] }} />
            ))}
          </div>
          <ul className="stage-legend">
            {STAGE_ORDER.map((stage) => (
              <li key={stage} className={"is-" + stage}>
                <i aria-hidden="true" />
                {STAGE_LABEL[stage]} <b>{counts[stage]}</b>
              </li>
            ))}
          </ul>
          {STAGE_ORDER.map((stage) => {
            const group = rows.filter((row) => row.stage === stage);
            if (!group.length) return null;
            return (
              <section className={"stage-group is-" + stage} key={stage}>
                <h3 className={"stage-heading is-" + stage}>
                  {STAGE_LABEL[stage]}
                  <span>{group.length}</span>
                </h3>
                <ul className="stage-topics">
                  {group.map((row) => (
                    <li key={row.topic} className="stage-topic">
                      <b>{row.topic}</b>
                      <p>{row.reason}</p>
                    </li>
                  ))}
                </ul>
              </section>
            );
          })}
        </>
      ) : (
        <p className="muted">
          Add your syllabus topics to see how each one looks after review.
        </p>
      )}
    </section>
  );
}
