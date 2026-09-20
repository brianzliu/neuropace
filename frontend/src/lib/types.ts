// Shapes mirrored from the backend (neuropace/core/session.py, review.py, tally.py, lossmap.py, api/routes.py).

/** The four explanation families the preference model learns over (docs/PRODUCT.md §4). */
export type Form = "words" | "analogy" | "visual" | "doing";
export const FORMS: Form[] = ["words", "analogy", "visual", "doing"];
export const FORM_LABEL: Record<Form, string> = {
  words: "in words",
  analogy: "by comparison",
  visual: "as a picture",
  doing: "by doing",
};
export const FORM_ICON: Record<Form, string> = { words: "Aa", analogy: "≈", visual: "◔", doing: "⇢" };

/** One generated way of presenting a moment (docs/PRODUCT.md §4). */
export type ArtifactKind = "words" | "analogy" | "diagram" | "chart" | "plot" | "timeline" | "compare" | "animation" | "steps" | "example";
export const ARTIFACT_KINDS: ArtifactKind[] = ["words", "analogy", "diagram", "chart", "plot", "timeline", "compare", "animation", "steps", "example"];
export const ARTIFACT_LABEL: Record<ArtifactKind, string> = {
  words: "in words",
  analogy: "a comparison",
  diagram: "a picture",
  chart: "the numbers",
  plot: "a curve",
  timeline: "in order",
  compare: "side by side",
  animation: "in motion",
  steps: "step by step",
  example: "a worked example",
};
export const ARTIFACT_FAMILY: Record<ArtifactKind, Form> = {
  words: "words",
  analogy: "analogy",
  diagram: "visual",
  chart: "visual",
  plot: "visual",
  timeline: "visual",
  compare: "visual",
  animation: "visual",
  steps: "doing",
  example: "doing",
};

export interface Word {
  w: string;
  start: number;
  end: number;
}

export interface FocusMsg {
  type: "focus";
  t: number;
  e: number | null;
  x: number | null;
  z: number | null;
  w15: number | null;
  quality: "good" | "bad";
  state: "baseline" | "ok" | "drop" | "bad" | "nosignal";
  baseline_ready: boolean;
  baseline_progress: number;
  artifact: boolean;
  blink: boolean;
  mw?: MindwaveFrameExtras;
  bands?: { theta: number; alpha: number; beta: number } | null;
  paused: boolean;
  poor_signal: number;
  attention: number | null;
  sim?: boolean;
  blinks_total?: number;
}

export type FlagSource = "tap" | "key" | "eeg" | "forced" | "sim_tap";
export const isTapSource = (s: string) => s === "tap" || s === "key" || s === "sim_tap";

export interface Flag {
  id: string;
  source: FlagSource;
  t_trigger: number;
  t_start: number;
  t_end: number | null;
  catchup_shown: boolean | null;
  catchup_form: Form | null;
  opened: boolean;
  linked_eeg?: string | null;
  simulated?: boolean;
}

export interface CatchupMsg {
  type: "catchup";
  t: number;
  flag_id: string;
  since?: number; // lecture time where the missed span starts (the EEG drop when a tap is linked)
  span_seconds?: number;
  linked_eeg?: string | null;
  form: Form;
  line: string;
  now_text: string;
  forms: Record<Form, string>;
  source: "llm" | "cache" | "offline" | "transcript";
  recap_window: [number, number];
  ttl_s: number;
  auto_show: boolean;
  reason: "tap" | "eeg" | "video_pause";
}

export interface RecapMsg {
  t_from: number;
  t_to: number;
  forms: Record<Form, string>;
  source: "llm" | "cache" | "offline" | "transcript";
  best_form?: Form;
}

export type TotemKind = "real" | "keyboard";

export interface TotemStatus {
  connected: boolean;
  kind: TotemKind | string;
  port: string | null;
  dots: number;
  fit: number;
  pulse?: boolean;
  hint?: string | null;
}

export type HeadsetKind = "real" | "simulated" | "fake" | "replay" | "virtual";

/** Status of the team's mindwave pipeline (three-anchor calibration), present for real, fake and replay headsets. */
export interface MindwaveStatus {
  calibrated?: boolean | null;
  cal_phase?: string | null;
  calibration_weak?: boolean | null;
  alpha_closed_open_ratio?: number | null;
  messages?: string[] | null;
  quality?: number | null;
  error?: string | null;
  session_dir?: string | null;
  frames?: number;
}

/** Is the brain-wave stream actually arriving (a chunk in the last 2 s)? */
export interface StreamHealth {
  live: boolean;
  age_s: number | null;
  chunks: number;
}

export interface HeadsetStatus {
  connected: boolean;
  kind: HeadsetKind;
  /** true for every kind but "real": the waves on screen are not from a headset on this student's head */
  simulated?: boolean;
  port: string | null;
  state: string | null;
  stream?: StreamHealth;
  mw?: MindwaveStatus;
}

/** GET /api/devices: what a session would get right now (headset and pad), no network calls. */
export interface Devices {
  headset: { port: string | null; kind: "real" | "simulated" | string; setting: string | null; bridge?: string | null };
  totem: { port: string | null; kind: "real" | "keyboard" | string; setting: string | null };
  checked_at: number;
}

/** Per-frame extras from the mindwave pipeline, on focus samples when the bridge is the front end. */
export interface MindwaveFrameExtras {
  effort?: number | null;
  engagement?: number | null;
  alpha_ratio?: number | null;
  blink_rate?: number | null;
  z_effort_ema?: number | null;
  z_engagement_ema?: number | null;
  artifact_coverage?: number | null;
  calibrated?: boolean | null;
  cal_phase?: string | null;
  attention?: number | null;
}

export interface Notice {
  level: "info" | "warn" | "error";
  text: string;
}

export interface SessionConfig {
  baseline_seconds: number;
  lead_in_seconds: number;
  recap_period_seconds: number;
  recap_window_seconds: number;
  catchup_ttl_seconds: number;
  drop_enter_z: number;
  drop_exit_z: number;
  window_seconds: number;
  review_stop_streak: number;
  tally_enough_attempts: number;
  forms: Form[];
}

export interface Segment {
  id: string;
  title: string;
  t_start: number;
  t_end: number;
  planted_bad?: boolean;
}

export interface LectureLite {
  id: string;
  title: string;
  kind: "scripted" | "media";
  duration: number | null;
  segments: Segment[];
  keyterms: string[];
  has_media: boolean;
  quiz_count: number;
}

export interface Learner {
  id: string;
  name: string;
  created_at: number;
  baseline_mu: number | null;
  baseline_sigma: number | null;
  baseline_at: number | null;
}

export interface SessionRow {
  id: string;
  learner_id: string;
  lecture_id: string | null;
  mode: "live" | "recorded" | "review" | "office_hours";
  catchup_policy: "always" | "randomized";
  headset_kind: string | null;
  totem_kind: string | null;
  transcript_kind: "scripted" | "deepgram" | "recorded" | "none" | null;
  best_form: Form | null;
  status: "running" | "ended" | "reviewed" | "ending" | "created";
  started_at: number;
  ended_at: number | null;
  baseline: { mu: number | null; sigma: number | null; stored: boolean; ready?: boolean } | null;
  seed: number | null;
  auto_pause: boolean;
  /** Dashboard one-liner (LLM prose or a rules count fallback). Absent on older payloads. */
  summary?: string;
  summary_source?: string;
}

export interface SessionPublic extends SessionRow {
  running: boolean;
  flags: Flag[];
  gaps: number;
  words: number;
  catchups_shown: number;
  headset?: HeadsetStatus;
  totem?: TotemStatus;
}

export interface StartupCalibration {
  status: "waiting" | "collecting" | "failed" | "saved" | "complete";
  clean: boolean;
  remaining_seconds: number;
  error?: string;
}

export interface HelloMsg {
  startup_calibration?: StartupCalibration | null;
  type: "hello";
  session: SessionRow;
  learner: Learner;
  lecture: LectureLite | null;
  config: SessionConfig;
  best_form: Form;
  mode: "live" | "recorded" | "review";
  policy: "always" | "randomized";
  auto_pause: boolean;
  transcript_kind: "scripted" | "deepgram" | "recorded" | "none";
  words: Word[];
  flags: Flag[];
  recaps: RecapMsg[];
  focus: FocusMsg[];
  headset: HeadsetStatus;
  totem: TotemStatus;
  notices: Notice[];
  sim: { headset: boolean; totem: boolean; transcript: boolean };
}

/** A 64 Hz chunk of the brain-wave trace in microvolts (8 values, 8 times a second). */
export interface RawMsg {
  type: "raw";
  t: number;
  fs: number;
  uv: number[];
}

export interface SessionEndedMsg {
  type: "session_ended";
  gaps: number;
  flags: number;
  blinks: number;
}

export interface BoardExplanation { type: "board_explanation"; status: "pending" | "ready"; flag_id: string; text: string; source: "pending" | "llm" | "offline"; frames: {id: string; t: number}[]; t?: number }

export type ServerMsg =
  | ({ type: "startup_calibration" } & StartupCalibration)
  | BoardExplanation
  | HelloMsg
  | ({ type: "words"; words: Word[]; final: boolean; t: number })
  | FocusMsg
  | RawMsg
  | ({ type: "flag_open"; flag: Flag; t: number })
  | ({ type: "flag_close"; flag: Flag; t: number })
  | CatchupMsg
  | ({ type: "catchup_withheld"; flag_id: string; reason: string; t: number })
  | ({ type: "catchup_opened"; flag_id: string; t: number })
  | ({ type: "catchup_dismissed"; flag_id: string; t: number })
  | ({ type: "chip"; flag_id: string; t: number })
  | ({ type: "recap"; t: number } & RecapMsg)
  | ({ type: "totem"; t: number } & TotemStatus)
  | ({ type: "headset"; t: number } & HeadsetStatus)
  | ({ type: "pause_request"; flag_id: string; t: number })
  | SessionEndedMsg
  | ({ type: "notice"; t: number } & Notice)
  | ({ type: "error"; text: string; status?: string })
  | ({ type: "pong"; t: number });

// ---- REST shapes ----
export interface GapNote {
  what_was_said: string;
  key_term: string;
  definition: string;
  connection: string;
}

export type PackageSource = "llm" | "cache" | "offline" | "failed" | "transcript";

export interface GapPublic {
  id: string;
  ord: number;
  t_start: number;
  t_end: number;
  span_text: string;
  context_text: string;
  flag_ids: string[];
  status: "open" | "closed" | "exhausted";
  note: GapNote | null;
  question: { question: string; options: string[] } | null;
  package_source: PackageSource | null;
  error?: string | null;
  summary?: string | null;
  artifacts_available?: string[];
  forms_available?: Form[];
  plan?: Plan | null;
  kinds?: Record<Form, ArtifactKind> | null;
}

export interface RegenerateResponse {
  gaps: GapPublic[];
  failed: number;
}

export interface NotesResponse {
  session: SessionPublic;
  gaps: GapPublic[];
  words: Word[];
}

export interface SceneNode {
  id: string;
  label: string;
  shape?: "card" | "pill" | "ellipse" | "diamond";
  tone?: "butter" | "peach" | "mint" | "lilac";
}
export interface SceneEdge {
  from_id: string;
  to_id: string;
  label: string;
}
export interface SceneStep {
  highlight: string[];
  caption: string;
}
export interface SceneGraph {
  title: string;
  nodes: SceneNode[];
  edges: SceneEdge[];
  steps: SceneStep[];
}

export interface KeyIdea {
  term: string;
  definition: string;
  example: string;
}
export interface WordsContent {
  summary: string;
  key_idea: KeyIdea;
}
export interface ChartContent {
  applicable?: boolean; // packages from before the plan
  kind: "bar" | "line";
  title: string;
  unit: string;
  points: { label: string; value: number }[];
  takeaway: string;
}
export interface StepsContent {
  applicable?: boolean; // packages from before the plan
  title: string;
  steps: string[];
}
export interface ExampleContent {
  title: string;
  lines: string[];
  result: string;
}
/** By comparison: the story, the explicit mapping, and where it breaks. Older packages carry a plain string. */
export interface AnalogyContent {
  story: string;
  mapping: { idea: string; everyday: string }[];
  caveat: string;
}
export interface PlotContent {
  title: string;
  x_label: string;
  y_label: string;
  series: { name: string; points: { x: number; y: number }[] }[];
  annotations: { x: number; y: number; text: string }[];
  illustrative: boolean;
  takeaway: string;
}
export interface TimelineContent {
  title: string;
  events: { when: string; label: string; detail: string }[];
  takeaway: string;
}
export interface CompareContent {
  title: string;
  left: string;
  right: string;
  rows: { aspect: string; left_value: string; right_value: string }[];
  verdict: string;
}
/** A self-contained web animation (inline svg or canvas plus one script), rendered in a sandboxed iframe. */
export interface AnimationContent {
  title: string;
  caption: string;
  html: string;
}
export interface Plan {
  visual: ArtifactKind;
  doing: ArtifactKind;
  why: string;
}
export type ReteachContent =
  | WordsContent
  | string
  | AnalogyContent
  | SceneGraph
  | ChartContent
  | PlotContent
  | TimelineContent
  | CompareContent
  | AnimationContent
  | StepsContent
  | ExampleContent
  | null;

// ---------------------------------------------------------------- office hours (docs/PRODUCT.md §5a)
/** The board's three small annotation primitives, plus "manim" (optional, math content only), alongside
 * the ten content families above. */
export type BoardElementKind = ArtifactKind | "shape" | "arrow" | "label" | "manim";
export interface ShapeContent { shape: "rect" | "ellipse"; label: string }
export interface ArrowContent { from_id: string; to_id: string; label: string }
export interface LabelContent { text: string }
/** A Manim Community script (server-rendered, optional, docs/PRODUCT.md §5a): fetched lazily by ManimView,
 * 503s gracefully to just the caption when the server has no manim install. */
export interface ManimContent { title: string; caption: string; scene_name: string; script: string }

/** Position/size on the shared board (bounded canvas, roughly 4000x3000). */
export interface BoardEnvelope { x: number; y: number; w: number; h: number; z: number }

export interface BoardElement {
  id: string;
  kind: BoardElementKind;
  envelope: BoardEnvelope;
  content: ReteachContent | ShapeContent | ArrowContent | LabelContent | ManimContent;
}

export interface OHMessage {
  id: string;
  session_id: string;
  ord: number;
  role: "user" | "agent";
  text: string;
  related_element_ids: string[] | null;
  source: "llm" | "cache" | "offline" | "failed" | null;
  created_at: number;
}

export interface OHSnapshot {
  messages: OHMessage[];
  board: BoardElement[];
  ord: number;
}

/** GET /api/sessions/{id}/artifacts: every artifact of every moment, for the team's preview. */
export interface GapArtifacts extends GapPublic {
  artifacts: Record<string, unknown> & { summary?: string; key_idea?: KeyIdea; plan?: Plan };
  sources: Record<string, PackageSource>;
}

export interface Card {
  id: string;
  kind: "question" | "reteach";
  gap_id: string;
  gap_ord: number;
  form: Form | null;
  t_start: number;
  t_end: number;
  package_source: PackageSource | null;
  forms_used: Form[];
  question?: { question: string; options: string[] };
  reteach?: {
    form: Form;
    artifact: ArtifactKind;
    content: ReteachContent;
    key_term: string | null;
    /** how the missed span connects to what the student did hear (docs/PRODUCT.md §5 "where you were") */
    context: string;
    /** the lecturer's own words for the span */
    said: string;
    /** the tutor's reason for this family: preferred, untried, or exploring */
    why: string;
  };
}

export type ReviewMode = "tutor" | "manual";

export interface Progress {
  mode?: ReviewMode;
  gaps_total: number;
  gaps_closed: number;
  gaps_exhausted: number;
  streak: number;
  stop_streak: number;
  cards_answered: number;
  done: boolean;
}

export interface FormStat {
  form: Form;
  rescues: number;
  attempts: number;
  prior_a: number;
  prior_b: number;
  post_a: number;
  post_b: number;
  posterior_mean: number;
  rate: number | null;
  label?: string;
  focus?: { mean_focus: number | null; n: number };
  /** 0.6 x posterior mean + 0.4 x mean focus (posterior alone until focus is measured) */
  score?: number;
}

export interface Profile {
  learner: Learner;
  stats: { streak_days: number; active_days: number; moments_total: number; moments_restudied: number; lectures: number };
  tally: TallySummary;
  calibrated: boolean;
}

export interface TallySummary {
  forms: Record<Form, FormStat>;
  /** combined ranking: understanding first, attention second (docs/PRODUCT.md §5) */
  rank: Form[];
  rank_understanding?: Form[];
  /** the top of the ranking once enough explanations have been scored, else null */
  preferred?: Form | null;
  pick: Form;
  enough_data: boolean;
  total_attempts: number;
  needed_attempts: number;
  population: Record<Form, { rescues: number; attempts: number }>;
}

export interface ReviewStart {
  card: Card | null;
  progress: Progress;
  tally: TallySummary;
}

export interface ReviewAnswer {
  outcome: "hit" | "miss";
  correct_index: number;
  explanation: string;
  credited_form: Form | null;
  next: Card | null;
  done: boolean;
  progress: Progress;
  tally: TallySummary;
}

export interface ReviewNext {
  outcome?: "drop";
  next: Card | null;
  done: boolean;
  progress: Progress;
  tally: TallySummary;
}

export interface LossMapBin {
  t: number;
  loss: number | null;
  n: number;
}
export interface LossMapSegment {
  index: number;
  id: string;
  title: string;
  t_start: number;
  t_end: number;
  score: number | null;
  rank?: number;
}
export interface LossMap {
  ready: boolean;
  n: number;
  reason?: string;
  bin_seconds: number;
  n_bins: number;
  bins?: LossMapBin[];
  peak?: { t_start: number; t_end: number; score: number | null };
  segments?: LossMapSegment[];
  ranking?: string[];
  lecture?: { id: string; title: string; duration: number | null };
}

export interface Doctor {
  keys: { deepgram: boolean; openai: boolean; openrouter: boolean; gemini: boolean };
  deepgram: { ok: boolean; reason?: string; status?: number };
  tts?: { ok: boolean; model: string };
  openai: { ok: boolean; model: string; reason?: string; alternatives?: string[]; required?: boolean };
  openrouter: { ok: boolean; model: string; reason?: string; required?: boolean };
  gemini: { ok: boolean; model: string; reason?: string; required?: boolean };
  llm_provider: "openai" | "openrouter" | "gemini";
  headset: { port: string | null; kind: string; setting: string | null; bridge?: string | null };
  totem: { port: string | null; kind: string; setting: string | null; hint?: string | null };
  serial_ports: { device: string; description: string; hwid?: string; vid?: number | null }[];
  platform?: string;
  frontend_built: boolean;
  data_dir: string;
  baseline_seconds: number;
}

export interface QuizItem {
  id: string;
  question: string;
  options: string[];
  segment: string | null;
}
export interface QuizAnswerRow {
  session_id: string;
  item_id: string;
  phase: "before" | "after";
  choice: number | null;
  correct: number;
}
export interface QuizGet {
  items: QuizItem[];
  answers: QuizAnswerRow[];
}
export interface QuizResult {
  phase: string;
  score: number;
  total: number;
  per_item: { item_id: string; choice: number; correct: boolean }[];
}

export interface LectureFull extends LectureLite {
  words?: Word[];
  media_path?: string | null;
  word_count?: number;
  quiz?: unknown[];
}

export interface EventsResponse {
  session_id: string;
  events: (ServerMsg & { t?: number; wall?: number })[];
}
