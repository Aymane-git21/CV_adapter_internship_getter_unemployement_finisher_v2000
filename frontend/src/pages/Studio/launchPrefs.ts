/* Sticky Tailor-CV choices. Saved at the moment the user presses Tailor CV,
   restored on the next NewJobPanel mount. Per-browser (localStorage), same
   vanilla pattern as the open-tabs store; version-keyed so a future shape
   change just orphans the old blob instead of misparsing it. */

export interface LaunchPrefs {
  language: "en" | "fr" | "de";
  intensity: "reshape" | "minor" | "major" | "max_ats";
  template: string;
  accent: string;
  compiler: "typst" | "latex";
  cvMode: "saved" | "paste" | "upload";
  savedCvId: number | null;
  saveMaster: boolean;
}

const KEY = "cvg_launch_prefs.v1";

const LANGUAGES = new Set(["en", "fr", "de"]);
const INTENSITIES = new Set(["reshape", "minor", "major", "max_ats"]);
const COMPILERS = new Set(["typst", "latex"]);
const CV_MODES = new Set(["saved", "paste", "upload"]);
const ACCENT_RE = /^#[0-9a-fA-F]{6}$/;

/* Entitlement-dependent fields (template, compiler) are validated for shape
   only; the component downgrades locked values once config/quota arrive. */
const FIELD_OK: { [K in keyof LaunchPrefs]: (v: unknown) => v is LaunchPrefs[K] } = {
  language: (v): v is LaunchPrefs["language"] => typeof v === "string" && LANGUAGES.has(v),
  intensity: (v): v is LaunchPrefs["intensity"] => typeof v === "string" && INTENSITIES.has(v),
  template: (v): v is string => typeof v === "string" && v.length > 0,
  accent: (v): v is string => typeof v === "string" && ACCENT_RE.test(v),
  compiler: (v): v is LaunchPrefs["compiler"] => typeof v === "string" && COMPILERS.has(v),
  cvMode: (v): v is LaunchPrefs["cvMode"] => typeof v === "string" && CV_MODES.has(v),
  savedCvId: (v): v is number | null => v === null || (typeof v === "number" && Number.isInteger(v)),
  saveMaster: (v): v is boolean => typeof v === "boolean",
};

export function saveLaunchPrefs(prefs: LaunchPrefs): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(prefs));
  } catch {
    /* storage unavailable or full: sticky choices are a nicety, not a feature gate */
  }
}

export function loadLaunchPrefs(): Partial<LaunchPrefs> {
  let raw: string | null = null;
  try {
    raw = localStorage.getItem(KEY);
  } catch {
    return {};
  }
  if (!raw) return {};
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return {};
  }
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) return {};

  const out: Partial<LaunchPrefs> = {};
  for (const key of Object.keys(FIELD_OK) as (keyof LaunchPrefs)[]) {
    const value = (parsed as Record<string, unknown>)[key];
    if (FIELD_OK[key](value)) (out as Record<string, unknown>)[key] = value;
  }
  return out;
}
