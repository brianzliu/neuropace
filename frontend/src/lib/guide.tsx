import { createContext, useContext } from "react";

export type GuideAction = "notes" | "replay" | "review" | "quiz" | "complete";
export type GuideGoal = "understand" | "practice" | "recall";
export interface GuideDecision {
  action: GuideAction;
  reason: string;
  source?: string;
  target_gap_id?: string | null;
  target_time?: number | null;
  done?: boolean;
}
export interface GuideRequest {
  learner_id: string;
  goal: GuideGoal;
  current_step: GuideAction | null;
  completed_steps: GuideAction[];
  elapsed_seconds: number;
  time_limit_seconds: number;
  last_outcome?: "hit" | "miss" | "drop" | "read" | "completed" | null;
}
export type ReviewMode = "practice" | "whiteboard";
export interface ReviewRecommendationRequest {
  learner_id: string;
  current_mode: ReviewMode;
  focus_session_id?: string | null;
  conversation_session_id?: string | null;
}
export interface ReviewRecommendation {
  mode: ReviewMode;
  reason: string;
  source: string;
  allowed_modes: ReviewMode[];
  eeg: { available: boolean; simulated: boolean | null; recent_drop: boolean };
  learner_response_count: number;
  advisory: true;
}
export interface GuideStepContext {
  decision: GuideDecision;
  reportOutcome: (outcome: "hit" | "miss" | "drop" | "read" | "completed") => void;
  paused: boolean;
}
export const GuideContext = createContext<GuideStepContext | null>(null);
export const useGuidedStep = () => useContext(GuideContext);
