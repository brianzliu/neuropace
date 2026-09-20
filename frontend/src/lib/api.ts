import { backendFetch } from "./backend";
import type {
  Profile,
  Devices,
  GapArtifacts,
  Doctor, EventsResponse, LectureFull, Learner, LossMap, ManimContent, NotesResponse, OHMessage, OHSnapshot, QuizGet, QuizResult, RegenerateResponse, ReviewAnswer,
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

/** Fetch timeout so a dead connection surfaces as an error instead of
 *  hanging every section on "Loading…" forever. Callers may pass their
 *  own signal to override, or a longer budget for model-backed calls. */
const FETCH_TIMEOUT_MS = 15000;
/** Budget for the background LLM organize pass, which can take 30s+. */
const ORGANIZE_TIMEOUT_MS = 90000;

async function request<T>(path: string, init?: RequestInit, timeoutMs = FETCH_TIMEOUT_MS): Promise<T> {
  const res = await backendFetch(path, { headers: { "Content-Type": "application/json" }, signal: AbortSignal.timeout(timeoutMs), ...init });
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
const getSlow = <T,>(path: string, ms: number) => request<T>(path, undefined, ms);
const post = <T,>(path: string, body?: unknown) => request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export interface SessionCreate {
  learner_id?: string | null; // omitted: this device's single learner
  learner_name?: string | null; // study participant, optional
  lecture_id?: string | null;
  mode: "live" | "recorded" | "review" | "office_hours";
  catchup_policy?: "always" | "randomized";
  baseline_seconds?: number;
  use_stored_baseline?: boolean;
  auto_pause?: boolean;
  headset?: string; // auto | sim | fake | replay:<dir> | serial:<port> | a device path
  totem?: string; // auto | keyboard | a device path
  transcript?: "auto" | "scripted" | "deepgram" | "recorded";
  seed?: number;
}

export const api = {
  demoMode: () => get<{ enabled: boolean; synthetic: true }>("/api/settings/demo"),
  setDemoMode: (enabled: boolean) => request<{ enabled: boolean; synthetic: true }>("/api/settings/demo", { method: "PUT", body: JSON.stringify({ enabled }) }),
  dashboard: (id: string, organize = false, classId?: string) => {
    const path = `/api/learners/${id}/dashboard?organize=${organize}${classId ? `&class_id=${classId}` : ""}`;
    return organize ? getSlow<import("./dashboardTypes").Dashboard>(path, ORGANIZE_TIMEOUT_MS) : get<import("./dashboardTypes").Dashboard>(path);
  },
  saveCurriculum: (id: string, body: import("./dashboardTypes").Curriculum) => request<import("./dashboardTypes").Curriculum>(`/api/learners/${id}/curriculum`, { method: "PUT", body: JSON.stringify(body) }),
  classes: (id: string) => get<{ classes: import("./dashboardTypes").ClassSummary[] }>(`/api/learners/${id}/classes`),
  createClass: (id: string, title: string) => post<import("./dashboardTypes").ClassDetail>(`/api/learners/${id}/classes`, { title }),
  activateClass: (id: string, classId: string) => post<import("./dashboardTypes").ClassDetail>(`/api/learners/${id}/classes/${classId}/activate`),
  deleteClass: (id: string, classId: string) => request<{ classes: import("./dashboardTypes").ClassSummary[] }>(`/api/learners/${id}/classes/${classId}`, { method: "DELETE" }),
  deepgramKeyStatus: () => get<{ configured: boolean }>("/api/settings/deepgram"),
  setDeepgramKey: (api_key: string) => request<{ configured: boolean }>("/api/settings/deepgram", { method: "PUT", body: JSON.stringify({ api_key }) }),
  modelSettings: () => get<{ provider: "openai" | "openrouter" | "gemini"; model: string; models: Record<"openai" | "openrouter" | "gemini", string>; configured: Record<"openai" | "openrouter" | "gemini", boolean> }>("/api/settings/model"),
  setModelSettings: (body: { provider: "openai" | "openrouter" | "gemini"; api_key?: string; model: string }) =>
    request<{ provider: "openai" | "openrouter" | "gemini"; model: string; models: Record<"openai" | "openrouter" | "gemini", string>; configured: Record<"openai" | "openrouter" | "gemini", boolean> }>("/api/settings/model", { method: "PUT", body: JSON.stringify(body) }),
  health: () => get<{ ok: boolean; version: string; voice?: boolean }>("/api/health"),  doctor: () => get<Doctor>("/api/doctor"),
  devices: () => get<Devices>("/api/devices"),
  artifacts: (id: string) => get<{ gaps: GapArtifacts[] }>(`/api/sessions/${id}/artifacts`),
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
  beginCalibration: (id: string) => post<unknown>(`/api/sessions/${id}/personal-calibration/start`),
  continueCalibration: (id: string) => post<unknown>(`/api/sessions/${id}/personal-calibration/continue`),
  tap: (id: string) => post<unknown>(`/api/sessions/${id}/tap`),
  simHeadset: (id: string, state: string) => post<unknown>(`/api/sessions/${id}/sim/headset`, { state }),
  events: (id: string) => get<EventsResponse>(`/api/sessions/${id}/events`),
  notes: (id: string) => get<NotesResponse>(`/api/sessions/${id}/notes`),
  regenerate: (id: string) => post<RegenerateResponse>(`/api/sessions/${id}/regenerate`),
  reviewStart: (id: string, mode: "tutor" | "manual" = "tutor") => post<ReviewStart>(`/api/sessions/${id}/review/start`, { mode }),
  reviewState: (id: string) => get<ReviewStart>(`/api/sessions/${id}/review`),
  reviewAnswer: (id: string, card_id: string, choice: number, focus_ratio?: number | null) =>
    post<ReviewAnswer>(`/api/sessions/${id}/review/answer`, { card_id, choice, focus_ratio: focus_ratio ?? null }),
  reviewDrop: (id: string, card_id: string, focus_ratio?: number | null) => post<ReviewNext>(`/api/sessions/${id}/review/drop`, { card_id, focus_ratio: focus_ratio ?? null }),
  profile: (learnerId?: string) => get<Profile>(`/api/me/profile${learnerId ? `?learner_id=${encodeURIComponent(learnerId)}` : ""}`),
  resetProfile: (learnerId?: string) => post<{ ok: boolean }>(`/api/me/reset${learnerId ? `?learner_id=${encodeURIComponent(learnerId)}` : ""}`),
  reviewAdvance: (id: string, card_id: string, focus_ratio?: number | null) =>
    post<ReviewNext>(`/api/sessions/${id}/review/advance`, { card_id, focus_ratio: focus_ratio ?? null }),
  quiz: (id: string) => get<QuizGet>(`/api/sessions/${id}/quiz`),
  submitQuiz: (id: string, phase: "before" | "after", answers: Record<string, number>) => post<QuizResult>(`/api/sessions/${id}/quiz`, { phase, answers }),
  officeHoursSnapshot: (id: string, uptoOrd?: number) =>
    get<OHSnapshot>(`/api/sessions/${id}/office_hours${uptoOrd != null ? `?upto_ord=${uptoOrd}` : ""}`),
  officeHoursSend: (id: string, text: string) => post<OHMessage>(`/api/sessions/${id}/office_hours/message`, { text }),
  officeHoursExpand: (id: string, elementId: string) =>
    post<OHMessage>(`/api/sessions/${id}/office_hours/expand`, { element_id: elementId }),
  officeHoursVoice: async (id: string, blob: Blob): Promise<{ text: string; reply: OHMessage }> => {
    const body = new FormData();
    body.append("file", blob, "clip.webm");
    const res = await backendFetch(`/api/sessions/${id}/office_hours/voice`, { method: "POST", body });
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
    return (await res.json()) as { text: string; reply: OHMessage };
  },
  renderManim: async (content: ManimContent): Promise<Blob> => {
    const res = await backendFetch("/api/manim/render", { headers: { "Content-Type": "application/json" }, method: "POST", body: JSON.stringify(content) });
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
    return res.blob();
  },
};
