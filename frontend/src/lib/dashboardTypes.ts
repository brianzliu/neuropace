import type { SessionRow } from "./types";
export interface Concept { id: string; session_id: string; lecture: string; title: string; description: string; status: string; t_start: number; reason: string; source: string }
export interface Dashboard {
  sessions: (SessionRow & { title: string })[];
  concepts: Concept[];
  closed: number;
  summary: string;
  organization_source: string;
}
