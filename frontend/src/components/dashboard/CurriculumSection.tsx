import { useState } from "react";
import { backendFetch } from "../../lib/backend";
import type { Curriculum } from "../../lib/dashboardTypes";

interface CurriculumSectionProps {
  curriculum: Curriculum | undefined;
  learnerId: string;
  onSave: (curriculum: Curriculum) => Promise<void>;
}

/**
 * Dashboard compartment 3: curriculum progress + syllabus editor.
 * Checkboxes are self-reported coverage only — review results are tracked
 * separately and the LLM never writes completion. Parse errors surface via
 * role="status". Server caps (2 MB / 30 pages / 30k chars / 100 topics) stay
 * enforced backend-side; this form just previews before saving.
 */
export default function CurriculumSection({ curriculum, learnerId, onSave }: CurriculumSectionProps) {
  const topics = curriculum?.topics ?? [];
  const completed = topics.filter((t) => t.completed).length;
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
          : "Topics extracted. Check and edit them before saving.",
      );
    } catch (e) {
      setSyllabusMessage(String(e));
    } finally {
      setBusy(false);
    }
  };

  const toggleTopic = async (index: number) => {
    if (!curriculum || busy) return;
    setBusy(true);
    try {
      await onSave({
        ...curriculum,
        topics: topics.map((t, i) => (i === index ? { ...t, completed: !t.completed } : t)),
      });
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
            Check off topics you’ve covered. This tracks your own progress, not tested mastery. Up
            to 100 topics.
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
          <div className="curriculum-progress">
            <progress value={completed} max={topics.length} />
            <span>
              {completed} of {topics.length} covered
            </span>
          </div>
          <p className="coverage-note"><span>Your own checkmarks</span><span>Review results tracked separately</span></p>
          <div className="topic-list">
            {topics.map((topic, index) => (
              <label key={index}>
                <input
                  type="checkbox"
                  checked={topic.completed}
                  disabled={busy}
                  onChange={() => void toggleTopic(index)}
                />
                <span>{topic.title}</span>
              </label>
            ))}
          </div>
        </>
      ) : (
        <p className="muted">
          Add your syllabus topics to see the course at a glance and track what you’ve covered.
        </p>
      )}
    </section>
  );
}
