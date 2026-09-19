import { useCallback, useEffect, useState } from "react";
import { readLocalSetting, writeLocalSetting } from "./storage";

export type Theme = "auto" | "light" | "dark";
function read(): Theme {
  const v = readLocalSetting("theme");
  return v === "light" || v === "dark" ? v : "auto";
}

export function applyTheme(t: Theme): void {
  const root = document.documentElement;
  if (t === "auto") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", t);
}

/** Theme preference: follows the system by default, persisted per browser. */
export function useTheme(): [Theme, (t: Theme) => void] {
  const [theme, setThemeState] = useState<Theme>(read);
  useEffect(() => applyTheme(theme), [theme]);
  const setTheme = useCallback((t: Theme) => {
    setThemeState(t);
    writeLocalSetting("theme", t);
  }, []);
  return [theme, setTheme];
}
