import { api } from "./api";
import { readLocalSetting } from "./storage";

/** Reuse the dashboard's learner; a fresh browser uses the backend default. */
export async function activeLearnerId(): Promise<string> {
  let selected: string | null = null;
  selected = readLocalSetting("learner");
  return selected || (await api.learner("me")).id;
}
