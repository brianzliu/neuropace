import { useEffect, useRef, useState } from "react";
import type { SessionPublic } from "../lib/types";

export function sessionTitle(session: SessionPublic, titles: Record<string, string>) {
  if (session.lecture_id && titles[session.lecture_id]) return titles[session.lecture_id];
  if (session.mode === "office_hours") return "Office Hours";
  return session.mode === "recorded" ? "Recorded lecture" : "Live session";
}

export function sessionMeta(session: SessionPublic) {
  return new Date(session.started_at * 1000).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

interface SessionSwitcherProps {
  sessions: SessionPublic[];
  titles: Record<string, string>;
  currentId: string;
  currentTitle: string;
  onSelect: (id: string) => void;
}

/**
 * Themed dropdown for the Library header: same surface, border, type, and shadow
 * as the rest of the design system. A native <select> popup cannot be styled, so
 * this builds a listbox on <details> (keyboard toggle for free) with outside-click,
 * Escape, and arrow-key handling.
 */
export default function SessionSwitcher({ sessions, titles, currentId, currentTitle, onSelect }: SessionSwitcherProps) {
  const root = useRef<HTMLDetailsElement>(null);
  const [open, setOpen] = useState(false);
  const current = sessions.find((s) => s.id === currentId);

  const close = () => {
    root.current?.removeAttribute("open");
    setOpen(false);
  };

  useEffect(() => {
    if (!open) return;
    const onOutside = (e: MouseEvent) => {
      if (root.current && !root.current.contains(e.target as Node)) close();
    };
    document.addEventListener("mousedown", onOutside);
    return () => document.removeEventListener("mousedown", onOutside);
  }, [open]);

  const choose = (id: string) => {
    close();
    if (id !== currentId) onSelect(id);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLDetailsElement>) => {
    if (e.key === "Escape") {
      e.preventDefault();
      close();
      root.current?.querySelector<HTMLElement>("summary")?.focus();
      return;
    }
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    const options = Array.from(root.current?.querySelectorAll<HTMLButtonElement>(".switcher-option") ?? []);
    if (!options.length) return;
    e.preventDefault();
    const at = options.indexOf(document.activeElement as HTMLButtonElement);
    const next = e.key === "ArrowDown" ? Math.min(at + 1, options.length - 1) : Math.max(at - 1, 0);
    options[next === -1 ? 0 : next]?.focus();
  };

  return (
    <details
      className="session-switcher"
      ref={root}
      onToggle={(e) => setOpen(e.currentTarget.open)}
      onKeyDown={onKeyDown}
    >
      <summary aria-haspopup="listbox">
        <span className="switcher-text">
          <b>{current ? sessionTitle(current, titles) : currentTitle}</b>
          {current ? <small>{sessionMeta(current)}</small> : null}
        </span>
        <span className="switcher-caret" aria-hidden="true">⌄</span>
      </summary>
      <div className="switcher-menu" role="listbox" aria-label="Choose a session">
        {sessions.map((s) => {
          const selected = s.id === currentId;
          return (
            <button
              key={s.id}
              type="button"
              role="option"
              aria-selected={selected}
              className={"switcher-option" + (selected ? " is-current" : "")}
              onClick={() => choose(s.id)}
            >
              <span className="switcher-check" aria-hidden="true">{selected ? "✓" : ""}</span>
              <span className="switcher-option-text">
                <b>{sessionTitle(s, titles)}</b>
                <small>{sessionMeta(s)}</small>
              </span>
            </button>
          );
        })}
      </div>
    </details>
  );
}
