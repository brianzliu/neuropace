import { api } from "./api";

/** Reuse the dashboard's learner; a fresh browser uses the backend default. */
export async function activeLearnerId(): Promise<string> {
  let selected: string | null = null;
  try { selected = localStorage.getItem("reflow.learner"); } catch { /* storage can be disabled */ }
  return selected || (await api.learner("me")).id;
}
