import type { SessionRow } from "./types";
export interface Curriculum { title: string; topics: { title: string; completed: boolean }[] }
export interface Concept { id: string; session_id: string; lecture: string; title: string; description: string; status: string; t_start: number; reason: string; source: string }
export type UnderstandingStage = "advanced" | "intermediate" | "beginner" | "review" | "no_evidence";
export interface UnderstandingTopic {
  topic: string;
  stage: UnderstandingStage;
  reason: string;
  gap_ids: string[];
  evidence: { resolved: number; open: number; exhausted: number; total: number };
}
/** Coaching estimate from saved moments + review outcomes; never a grade or completion record. */
export interface Understanding {
  source: string;
  topics: UnderstandingTopic[];
  quizzes: { lecture: string; before: { correct: number; total: number }; after: { correct: number; total: number } }[];
}
export interface Dashboard {
  sessions: (SessionRow & { title: string })[];
  concepts: Concept[];
  closed: number;
  summary: string;
  organization_source: string;
  understanding?: Understanding;
  curriculum: Curriculum;
}
