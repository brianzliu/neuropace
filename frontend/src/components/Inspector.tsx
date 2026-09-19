import type { ReactNode } from "react";

/** Inset grouped list, the macOS settings idiom. */
export function Group({ title, children, note }: { title?: string; children: ReactNode; note?: ReactNode }) {
  return (
    <div className="section">
      {title ? <div className="group-header">{title}</div> : null}
      <div className="group">{children}</div>
      {note ? <div className="group-note">{note}</div> : null}
    </div>
  );
}

export function Row({ label, children, stacked, className }: { label: ReactNode; children?: ReactNode; stacked?: boolean; className?: string }) {
  return (
    <div className={"group-row" + (stacked ? " stacked" : "") + (className ? " " + className : "")}>
      <span className="lbl">{label}</span>
      {children !== undefined ? <span className="val">{children}</span> : null}
    </div>
  );
}
