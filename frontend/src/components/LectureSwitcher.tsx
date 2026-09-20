import { useEffect, useRef, useState } from "react";
import type { LectureFull } from "../lib/types";

export default function LectureSwitcher({ lectures, currentId, onSelect }: {
  lectures: LectureFull[];
  currentId: string;
  onSelect: (id: string) => void;
}) {
  const root = useRef<HTMLDetailsElement>(null);
  const [open, setOpen] = useState(false);
  const current = lectures.find(lecture => lecture.id === currentId);

  const close = () => {
    root.current?.removeAttribute("open");
    setOpen(false);
  };

  useEffect(() => {
    if (!open) return;
    const onOutside = (event: MouseEvent) => {
      if (root.current && !root.current.contains(event.target as Node)) close();
    };
    document.addEventListener("mousedown", onOutside);
    return () => document.removeEventListener("mousedown", onOutside);
  }, [open]);

  return (
    <details
      className="session-switcher lecture-switcher"
      ref={root}
      onToggle={event => setOpen(event.currentTarget.open)}
      onKeyDown={event => {
        if (event.key !== "Escape") return;
        event.preventDefault();
        close();
        root.current?.querySelector<HTMLElement>("summary")?.focus();
      }}
    >
      <summary aria-haspopup="listbox">
        <span className="switcher-text"><b>{current?.title ?? "Choose a lecture"}</b></span>
        <span className="switcher-caret" aria-hidden="true">⌄</span>
      </summary>
      <div className="switcher-menu" role="listbox" aria-label="Choose a lecture">
        {lectures.map(lecture => {
          const selected = lecture.id === currentId;
          return (
            <button
              key={lecture.id}
              type="button"
              role="option"
              aria-selected={selected}
              className={`switcher-option${selected ? " is-current" : ""}`}
              onClick={() => {
                close();
                if (!selected) onSelect(lecture.id);
              }}
            >
              <span className="switcher-check" aria-hidden="true">{selected ? "✓" : ""}</span>
              <span className="switcher-option-text"><b>{lecture.title}</b></span>
            </button>
          );
        })}
      </div>
    </details>
  );
}
