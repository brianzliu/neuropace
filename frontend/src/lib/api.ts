import { backendFetch } from "./backend";
import type {
  Profile,
  Devices,
  GapArtifacts,
  BoardElement, Doctor, EventsResponse, LectureFull, Learner, LossMap, ManimContent, NotesResponse, OHMessage, OHSnapshot, QuizGet, QuizResult, RegenerateResponse, ReviewAnswer,
  ReviewNext, ReviewStart, SessionPublic, TallySummary, GapPublic, ScholarResponse, JargonResponse,
} from "./types";

/** One increment of an Office Hours turn as it streams in — see office_hours_turn_stream (backend). */
export type OHStreamEvent =
  | { type: "reply"; text: string }
  | { type: "board"; board: BoardElement[] }
  | { type: "done"; message: OHMessage }
  | { type: "error"; detail: string };

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
/** Budget for Office Hours model turns, which legitimately take 15s+ (measured).
 *  The default 15s budget aborted these mid-generation. */
const MODEL_TIMEOUT_MS = 120000;

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
const postSlow = <T,>(path: string, body: unknown, ms: number) => request<T>(path, { method: "POST", body: JSON.stringify(body) }, ms);

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
  dashboard: (id: string, organize = false) => {
    const path = `/api/learners/${id}/dashboard?organize=${organize}`;
    return organize ? getSlow<import("./dashboardTypes").Dashboard>(path, ORGANIZE_TIMEOUT_MS) : get<import("./dashboardTypes").Dashboard>(path);
  },
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
  /** Scholarly sources for a session's gaps (scholar sidecar). First call fetches from OpenAlex and can take a few seconds. */
  /** Jargon-dense stretches of a session's transcript, scored against OpenAlex (scholar sidecar). */
  jargon: (id: string) => get<JargonResponse>(`/api/sessions/${id}/scholar/jargon`),
  scholar: (id: string, refresh = false) => getSlow<ScholarResponse>(`/api/sessions/${id}/scholar${refresh ? "?refresh=1" : ""}`, 45000),
  regenerate: (id: string) => post<RegenerateResponse>(`/api/sessions/${id}/regenerate`),
  reviewStart: (id: string) => post<ReviewStart>(`/api/sessions/${id}/review/start`, { mode: "tutor" }),
  reviewAsk: (id: string, card_id: string, text: string) => postSlow<{ reply: string; source: string }>(`/api/sessions/${id}/review/ask`, { card_id, text }, MODEL_TIMEOUT_MS),
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
  /** The lecture's one whiteboard conversation: found or created once, never one per click. */
  officeHoursOpen: (id: string) => post<SessionPublic>(`/api/sessions/${id}/office_hours/open`),
  officeHoursSnapshot: (id: string, uptoOrd?: number) =>
    get<OHSnapshot>(`/api/sessions/${id}/office_hours${uptoOrd != null ? `?upto_ord=${uptoOrd}` : ""}`),
  officeHoursSend: (id: string, text: string) => postSlow<OHMessage>(`/api/sessions/${id}/office_hours/message`, { text }, MODEL_TIMEOUT_MS),
  /** Same turn as officeHoursSend, but calls onEvent as the reply and each board element streams in,
   *  instead of waiting for the whole turn. Resolves once the server-sent stream ends. */
  officeHoursSendStream: async (id: string, text: string, onEvent: (e: OHStreamEvent) => void): Promise<void> => {
    const res = await backendFetch(`/api/sessions/${id}/office_hours/message/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
      signal: AbortSignal.timeout(MODEL_TIMEOUT_MS),
    });
    if (!res.ok || !res.body) {
      let detail = res.statusText;
      try {
        const j = await res.json();
        detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j);
      } catch {
        // keep statusText
      }
      throw new ApiError(res.status, detail);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const parts = buf.split("\n\n");
      buf = parts.pop() ?? "";
      for (const chunk of parts) {
        const line = chunk.trim();
        if (!line.startsWith("data:")) continue;
        const payload = line.slice(5).trim();
        if (!payload) continue;
        try {
          onEvent(JSON.parse(payload) as OHStreamEvent);
        } catch {
          // malformed chunk; skip it rather than aborting the whole stream
        }
      }
    }
  },
  officeHoursExpand: (id: string, elementId: string) =>
    postSlow<OHMessage>(`/api/sessions/${id}/office_hours/expand`, { element_id: elementId }, MODEL_TIMEOUT_MS),
  /** Hold-to-talk for a text box: the clip's words back, nothing else. */
  transcribe: async (blob: Blob): Promise<{ text: string }> => {
    const body = new FormData();
    body.append("file", blob, "clip.webm");
    const res = await backendFetch("/api/transcribe", { method: "POST", body });
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
    return (await res.json()) as { text: string };
  },
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
