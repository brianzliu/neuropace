import type {
  Doctor, EventsResponse, LectureFull, Learner, LossMap, NotesResponse, QuizGet, QuizResult, RegenerateResponse, ReviewAnswer,
  ReviewNext, ReviewStart, SessionPublic, TallySummary, GapPublic,
} from "./types";

/** An HTTP error with the backend's `detail` kept separately, so views can show it verbatim. */
export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(`${status}: ${detail}`);
    this.name = "ApiError";
  }
}

export function errorText(e: unknown): string {
  if (e instanceof ApiError) return e.detail;
  return e instanceof Error ? e.message : String(e);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...init });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j);
    } catch {
      // keep statusText
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

const get = <T,>(path: string) => request<T>(path);
const post = <T,>(path: string, body?: unknown) => request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export interface SessionCreate {
  learner_id: string;
  lecture_id?: string | null;
  mode: "live" | "recorded";
  catchup_policy: "always" | "randomized";
  baseline_seconds?: number;
  use_stored_baseline?: boolean;
  auto_pause?: boolean;
  headset?: string; // auto | sim | fake | replay:<dir> | serial:<port> | a device path
  totem?: string; // auto | keyboard | a device path
  transcript?: "auto" | "scripted" | "deepgram" | "recorded";
  seed?: number;
}

export const api = {
  health: () => get<{ ok: boolean; version: string }>("/api/health"),
  doctor: () => get<Doctor>("/api/doctor"),
  learners: () => get<{ learners: Learner[] }>("/api/learners"),
  createLearner: (name: string) => post<Learner>("/api/learners", { name }),
  learner: (id: string) => get<Learner>(`/api/learners/${id}`),
  tally: (learnerId: string) => get<TallySummary>(`/api/learners/${learnerId}/tally`),
  lectures: () => get<{ lectures: LectureFull[] }>("/api/lectures"),
  lecture: (id: string, full = false) => get<LectureFull>(`/api/lectures/${id}${full ? "?full=1" : ""}`),
  lossmap: (lectureId: string) => get<LossMap>(`/api/lectures/${lectureId}/lossmap`),
  sessions: (q?: { lecture_id?: string; learner_id?: string }) => {
    const p = new URLSearchParams();
    if (q?.lecture_id) p.set("lecture_id", q.lecture_id);
    if (q?.learner_id) p.set("learner_id", q.learner_id);
    const qs = p.toString();
    return get<{ sessions: SessionPublic[] }>(`/api/sessions${qs ? "?" + qs : ""}`);
  },
  createSession: (body: SessionCreate) => post<SessionPublic>("/api/sessions", body),
  session: (id: string) => get<SessionPublic>(`/api/sessions/${id}`),
  endSession: (id: string) => post<{ gaps: GapPublic[]; session: SessionPublic }>(`/api/sessions/${id}/end`),
  tap: (id: string) => post<unknown>(`/api/sessions/${id}/tap`),
  simHeadset: (id: string, state: string) => post<unknown>(`/api/sessions/${id}/sim/headset`, { state }),
  events: (id: string) => get<EventsResponse>(`/api/sessions/${id}/events`),
  notes: (id: string) => get<NotesResponse>(`/api/sessions/${id}/notes`),
  regenerate: (id: string) => post<RegenerateResponse>(`/api/sessions/${id}/regenerate`),
  reviewStart: (id: string) => post<ReviewStart>(`/api/sessions/${id}/review/start`),
  reviewState: (id: string) => get<ReviewStart>(`/api/sessions/${id}/review`),
  reviewAnswer: (id: string, card_id: string, choice: number) => post<ReviewAnswer>(`/api/sessions/${id}/review/answer`, { card_id, choice }),
  reviewDrop: (id: string, card_id: string) => post<ReviewNext>(`/api/sessions/${id}/review/drop`, { card_id }),
  reviewAdvance: (id: string, card_id: string) => post<ReviewNext>(`/api/sessions/${id}/review/advance`, { card_id }),
  quiz: (id: string) => get<QuizGet>(`/api/sessions/${id}/quiz`),
  submitQuiz: (id: string, phase: "before" | "after", answers: Record<string, number>) => post<QuizResult>(`/api/sessions/${id}/quiz`, { phase, answers }),
};
