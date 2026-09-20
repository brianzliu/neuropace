import { useState } from "react";
import { backendFetch } from "../../lib/backend";
import type { ClassSummary, Curriculum, Understanding, UnderstandingStage, UnderstandingTopic } from "../../lib/dashboardTypes";

interface CurriculumSectionProps {
  curriculum: Curriculum | undefined;
  understanding: Understanding | undefined;
  organizing: boolean;
  learnerId: string;
  onSave: (curriculum: Curriculum) => Promise<void>;
  classes: ClassSummary[];
  activeClassId: string;
  onSelectClass: (id: string) => Promise<void>;
  onCreateClass: (title: string) => Promise<string>;
  onDeleteClass: (id: string) => Promise<void>;
}

const NO_EVIDENCE_REASON = "No saved moments mention this topic yet.";
const STAGE_ORDER: UnderstandingStage[] = ["review", "beginner", "intermediate", "advanced", "no_evidence"];

function EvidenceDots({ evidence }: { evidence: UnderstandingTopic["evidence"] }) {
  const dots: string[] = [
    ...Array(evidence.resolved).fill("resolved"),
    ...Array(evidence.open).fill("open"),
    ...Array(evidence.exhausted).fill("exhausted"),
  ];
  if (!dots.length) return null;
  return (
    <span
      className="evidence-dots"
      role="img"
      aria-label={`${evidence.resolved} resolved, ${evidence.open} open, ${evidence.exhausted} exhausted`}
    >
      {dots.map((kind, i) => (
        <i key={i} className={"is-" + kind} aria-hidden="true" />
      ))}
    </span>
  );
}
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
export default function CurriculumSection({ curriculum, understanding, learnerId, onSave, classes, activeClassId, onSelectClass, onCreateClass, onDeleteClass }: CurriculumSectionProps) {
  const topics = curriculum?.topics ?? [];
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [syllabus, setSyllabus] = useState("");
  const [syllabusMessage, setSyllabusMessage] = useState("");
  const [course, setCourse] = useState("");
  const [creating, setCreating] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [createBusy, setCreateBusy] = useState(false);
  const [createError, setCreateError] = useState("");

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

  const create = async () => {
    const title = newTitle.trim();
    if (!title || createBusy) return;
    setCreateBusy(true);
    setCreateError("");
    try {
      await onCreateClass(title);
      setCreating(false);
      setNewTitle("");
      setCourse(title);
      setSyllabus("");
      setSyllabusMessage("");
      setEditing(true);
    } catch (e) {
      setCreateError(String(e));
    } finally {
      setCreateBusy(false);
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
        reason: NO_EVIDENCE_REASON,
        gap_ids: [],
        evidence: { resolved: 0, open: 0, exhausted: 0, total: 0 },
      },
  );
  const counts = Object.fromEntries(
    STAGE_ORDER.map((stage) => [stage, rows.filter((row) => row.stage === stage).length]),
  ) as Record<UnderstandingStage, number>;
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
      {classes.length > 0 && (
        <div className="class-tabs" role="group" aria-label="Classes">
          {classes.map(c => (
            <button
              key={c.id}
              type="button"
              className="class-tab"
              aria-pressed={c.id === activeClassId}
              onClick={() => { if (c.id !== activeClassId) void onSelectClass(c.id); }}
            >
              {c.title}
              <span>{c.topic_count}</span>
            </button>
          ))}
          {creating ? (
            <span className="class-create">
              <input
                aria-label="New class name"
                placeholder="Class name"
                maxLength={200}
                value={newTitle}
                disabled={createBusy}
                onChange={e => setNewTitle(e.target.value)}
                onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); void create(); } }}
              />
              <button type="button" disabled={createBusy || !newTitle.trim()} onClick={() => void create()}>
                {createBusy ? "Adding…" : "Add"}
              </button>
              <button type="button" onClick={() => { setCreating(false); setNewTitle(""); setCreateError(""); }}>
                Cancel
              </button>
            </span>
          ) : (
            <button type="button" className="class-tab is-new" onClick={() => { setCreating(true); setNewTitle(""); setCreateError(""); }}>
              + New
            </button>
          )}
        </div>
      )}
      {createError && <p className="small muted" role="alert">{createError}</p>}
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
            <button
              type="button"
              className="ghost danger"
              disabled={busy}
              onClick={() => {
                if (window.confirm(`Delete "${curriculum?.title ?? "this class"}" and its topics? Your sessions stay.`))
                  void onDeleteClass(activeClassId).then(() => setEditing(false)).catch(() => {});
              }}
            >
              Delete class
            </button>
          </div>
        </form>
      ) : curriculum === undefined ? (
        <p className="muted" role="status">
          Loading your saved moments…
        </p>
      ) : topics.length ? (
        <>
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
                  <i aria-hidden="true" />
                  {STAGE_LABEL[stage]}
                  <span>{group.length}</span>
                </h3>
                <ul className="stage-topics">
                  {group.map((row) => (
                    <li key={row.topic} className="stage-topic">
                      <b>{row.topic}</b>
                      <EvidenceDots evidence={row.evidence} />
                      {row.reason !== NO_EVIDENCE_REASON && <p>{row.reason}</p>}
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
