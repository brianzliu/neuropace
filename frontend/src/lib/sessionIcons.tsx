import type { ReactNode } from "react";

/** Stroke-consistent fallback icons (24-grid, round caps, 2px stroke) shown until (or unless) the
 *  matching generated art in /public loads — shared by the session action row and the section tabs
 *  so a lecture's Notes/Review/Quiz/Replay/Explanations icon is drawn identically everywhere. */
export function ActionIcon({ children }: { children: ReactNode }) {
  return (
    <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      {children}
    </svg>
  );
}

export interface SessionIcon {
  name: string;
  tone: string;
  /** Generated art in /public; omitted means the stroke SVG below is the real icon, not a fallback. */
  img?: string;
  paths: ReactNode;
}

export type SessionIconKind = "notes" | "review" | "quiz" | "replay" | "artifacts";

export const SESSION_ICONS: Record<SessionIconKind, SessionIcon> = {
  notes: {
    name: "Notes", tone: "tone-notes", img: "/icon-notes.png",
    paths: (<><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /></>),
  },
  review: {
    name: "Review", tone: "tone-review", img: "/icon-review.png",
    paths: (<><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" /><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" /></>),
  },
  quiz: {
    name: "Quiz", tone: "tone-quiz", img: "/icon-quiz.png",
    paths: (<><rect x="8" y="2" width="8" height="4" rx="1" /><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" /><path d="m9 14 2 2 4-4" /></>),
  },
  replay: {
    name: "Replay", tone: "tone-replay", img: "/icon-replay.png",
    paths: (<><polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" /></>),
  },
  artifacts: {
    name: "Explanations", tone: "tone-artifacts",
    paths: (<><path d="M9 18h6" /><path d="M10 22h4" /><path d="M12 2a6 6 0 0 0-4 10.5c.6.55 1 1.36 1 2.24V16h6v-1.26c0-.88.4-1.69 1-2.24A6 6 0 0 0 12 2z" /></>),
  },
};

/** The icon+generated-art pair used everywhere a tab/action needs an icon, not just text. */
export function SessionIconArt({ kind }: { kind: SessionIconKind }) {
  const icon = SESSION_ICONS[kind];
  return (
    <span className={"action-art" + (icon.img ? "" : " no-art")} aria-hidden="true">
      <ActionIcon>{icon.paths}</ActionIcon>
      {icon.img ? (
        <img
          src={icon.img}
          alt=""
          onError={(e) => {
            e.currentTarget.remove();
            e.currentTarget.parentElement?.classList.add("no-art");
          }}
        />
      ) : null}
    </span>
  );
}
