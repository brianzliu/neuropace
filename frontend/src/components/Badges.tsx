import type { ReactNode } from "react";

export type Tone = "neutral" | "accent" | "success" | "warning" | "danger" | "purple";

export function Badge({ tone = "neutral", children, title }: { tone?: Tone; children: ReactNode; title?: string }) {
  return (
    <span className={"badge" + (tone !== "neutral" ? " " + tone : "")} title={title}>
      {children}
    </span>
  );
}

export function SourceBadge({ source }: { source: string | null | undefined }) {
  if (!source) return null;
  if (source === "offline") return <Badge tone="warning">offline</Badge>;
  if (source === "cache") return <Badge>cached</Badge>;
  if (source === "transcript") return <Badge>verbatim transcript</Badge>;
  if (source === "failed") return <Badge tone="danger">failed</Badge>;
  return <Badge tone="accent">llm</Badge>;
}

export function StatusDot({ state }: { state: "ok" | "warn" | "bad" | "off" | "accent" }) {
  return <span className={"dot " + (state === "off" ? "" : state)} />;
}
