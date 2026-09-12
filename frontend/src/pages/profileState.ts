/* Pure state rules for the profile page, the master CV editor. Kept out of
   the component so they are unit-testable without React. */
import type { CVData, MasterCVMeta } from "../api";

export const EMPTY_CV: CVData = {
  full_name: "", headline: "", summary: "",
  contacts: { email: "", phone: "", location: "", linkedin: "", github: "", website: "" },
  experience: [], education: [], skills: [], projects: [], languages: [], interests: [],
  certifications: [],
};

/* Stored data can be null (a CV not parsed yet) or predate a field: fill every
   key the form reads, so an edit never saves a partial CV. */
export function normalizeCv(data: Partial<CVData> | null | undefined): CVData {
  const d = data ?? {};
  return {
    full_name: d.full_name ?? "",
    headline: d.headline ?? "",
    summary: d.summary ?? "",
    contacts: { ...EMPTY_CV.contacts, ...(d.contacts ?? {}) },
    experience: d.experience ?? [],
    education: d.education ?? [],
    skills: d.skills ?? [],
    projects: d.projects ?? [],
    languages: d.languages ?? [],
    interests: d.interests ?? [],
    certifications: d.certifications ?? [],
  };
}

/* The CV the page opens: the one named in ?cv=, else the default, else the first. */
export function pickInitialCv(rows: readonly MasterCVMeta[], requested: number | null): MasterCVMeta | null {
  return rows.find((r) => r.id === requested) ?? rows.find((r) => r.is_default) ?? rows[0] ?? null;
}

/* Structural equality for JSON-shaped values; object key order is ignored,
   array order is not. */
export function sameJson(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (Array.isArray(a) || Array.isArray(b)) {
    return Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((v, i) => sameJson(v, b[i]));
  }
  if (a && b && typeof a === "object" && typeof b === "object") {
    const ra = a as Record<string, unknown>;
    const rb = b as Record<string, unknown>;
    const keys = Object.keys(ra);
    return keys.length === Object.keys(rb).length && keys.every((k) => k in rb && sameJson(ra[k], rb[k]));
  }
  return false;
}

export interface ProfileDraft { name: string; data: CVData }

/* Unsaved when the name or any field differs from what the server holds. */
export function isDirty(draft: ProfileDraft, saved: ProfileDraft): boolean {
  return draft.name !== saved.name || !sameJson(draft.data, saved.data);
}
