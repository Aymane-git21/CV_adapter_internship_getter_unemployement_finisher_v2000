/* API client + shared types (mirrors backend/app/schemas.py). */

export interface Contacts {
  email: string; phone: string; location: string;
  linkedin: string; github: string; website: string;
}
export interface ExperienceItem {
  title: string; company: string; location: string;
  start: string; end: string; bullets: string[];
}
export interface EducationItem {
  degree: string; school: string; location: string;
  start: string; end: string; details: string[];
}
export interface SkillGroup { category: string; items: string[] }
export interface ProjectItem { name: string; tech: string; description: string }
export interface LanguageItem { name: string; level: string }
export interface CertificationItem { name: string; issuer: string; year: string }

export interface CVData {
  full_name: string; headline: string; contacts: Contacts; summary: string;
  experience: ExperienceItem[]; education: EducationItem[]; skills: SkillGroup[];
  projects: ProjectItem[]; languages: LanguageItem[]; interests: string[];
  certifications: CertificationItem[];
}

export interface LetterData {
  sender: { full_name: string; email: string; phone: string; location: string };
  recipient: { name: string; company: string; address_lines: string[] };
  date_str: string; subject: string; greeting: string;
  paragraphs: string[]; closing: string; signature: string;
}

export interface DocSettings {
  template: string; accent: string; density: string;
  show_photo: boolean; font_scale: number; lang: string;
}

export interface JobEvent { ts: string; step: string; message: string; pct: number }

export interface DocSummary {
  id: string; kind: "cv" | "letter" | "message"; title: string;
  template?: string; score_before?: number | null; score_after?: number | null;
}

export interface JobSnapshot {
  id: string; status: "queued" | "running" | "completed" | "failed" | "unknown";
  title: string | null; company: string | null; language: string;
  events: JobEvent[]; error: string | null; created_at: string | null;
  documents?: DocSummary[];
}

export interface DocumentPayload {
  id: string; job_id: string | null; kind: "cv" | "letter" | "message";
  title: string; template: string; settings: DocSettings;
  data: CVData | LetterData | null; source: string | null;
  mode: "data" | "source"; text_content: string | null; photo_id: string | null;
  score_before: number | null; score_after: number | null;
  keywords: { matched: string[]; missing: string[] } | null;
  svgs: string[] | null;
}

export interface Quota {
  plan: string; label: string; daily_limit: number; used_today: number;
  remaining_today: number; parallel: number; templates: string[];
}

export interface Me {
  authenticated: boolean; id?: number; email?: string; plan?: string;
  language?: string; quota: Quota;
}

export interface TemplateMeta { id: string; label: string; vibe: string; default_accent: string }
export interface PlanMeta {
  key: string; label: string; daily: number; parallel: number;
  templates: string[]; price_eur: number;
}
export interface AppConfig {
  billing_enabled: boolean; google_client_id: string | null; adsense_client: string | null;
  ai_mode: "gemini" | "offline"; byok_enabled: boolean;
  templates: TemplateMeta[]; plans: PlanMeta[]; all_templates: string[];
}

export interface HistoryEntry {
  id: string; status: string; title: string; company: string | null; language: string;
  created_at: string | null; score_before: number | null; score_after: number | null;
  documents: { id: string; kind: string; title: string }[];
}

export interface MasterCVMeta {
  id: number; name: string; is_default: boolean; data: CVData | null;
  has_raw_text: boolean; updated_at: string | null;
}

/* ── client ──────────────────────────────────────────────────────────────── */

export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(status: number, message: string, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export const byokStore = {
  get(): string | null {
    return localStorage.getItem("cvg_byok");
  },
  set(key: string | null) {
    if (key) localStorage.setItem("cvg_byok", key);
    else localStorage.removeItem("cvg_byok");
  },
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && typeof init.body === "string") headers.set("Content-Type", "application/json");
  const byok = byokStore.get();
  if (byok) headers.set("X-User-Gemini-Key", byok);

  const res = await fetch(path, { credentials: "include", ...init, headers });
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    let code: string | undefined;
    try {
      const body = await res.json();
      const detail = body.detail ?? body;
      if (typeof detail === "string") message = detail;
      else if (detail?.message) { message = detail.message; code = detail.code; }
      else if (detail?.diagnostics) { message = detail.diagnostics; code = "compile_error"; }
      else if (Array.isArray(detail) && detail[0]?.msg) message = detail[0].msg;
    } catch { /* keep default */ }
    throw new ApiError(res.status, message, code);
  }
  const ct = res.headers.get("content-type") ?? "";
  return (ct.includes("application/json") ? res.json() : res.blob()) as Promise<T>;
}

export const api = {
  me: () => request<Me>("/api/auth/me"),
  register: (email: string, password: string) =>
    request<Me>("/api/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }),
  login: (email: string, password: string) =>
    request<Me>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  googleLogin: (credential: string) =>
    request<Me>("/api/auth/google", { method: "POST", body: JSON.stringify({ credential }) }),
  logout: () => request<{ ok: true }>("/api/auth/logout", { method: "POST" }),

  config: () => request<AppConfig>("/api/config"),
  history: () => request<HistoryEntry[]>("/api/history"),
  feedback: (name: string, email: string, message: string) =>
    request<{ ok: true }>("/api/feedback", { method: "POST", body: JSON.stringify({ name, email, message }) }),
  validateByok: (key: string) =>
    request<{ ok: true }>("/api/byok/validate", { method: "POST", body: JSON.stringify({ key }) }),

  cvs: () => request<MasterCVMeta[]>("/api/cvs"),
  createCv: (name: string, raw_text: string) =>
    request<MasterCVMeta>("/api/cvs", { method: "POST", body: JSON.stringify({ name, raw_text }) }),
  updateCv: (id: number, body: { name?: string; data?: CVData }) =>
    request<MasterCVMeta>(`/api/cvs/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteCv: (id: number) => request<{ ok: true }>(`/api/cvs/${id}`, { method: "DELETE" }),
  setDefaultCv: (id: number) => request<{ ok: true }>(`/api/cvs/${id}/default`, { method: "POST" }),
  uploadCvPdf: (file: File, name: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("name", name);
    return request<MasterCVMeta>("/api/cvs/upload", { method: "POST", body: form });
  },
  uploadPhoto: (blob: Blob) => {
    const form = new FormData();
    form.append("file", blob, "photo.jpg");
    return request<{ id: string }>("/api/photos", { method: "POST", body: form });
  },

  generate: (body: {
    job_descriptions: string[]; master_cv_id?: number | null; cv_text?: string | null;
    language: string; template: string; accent: string; show_photo: boolean;
    photo_id?: string | null; save_master?: boolean;
  }) => request<{ jobs: string[] }>("/api/generate", { method: "POST", body: JSON.stringify(body) }),

  job: (id: string) => request<JobSnapshot>(`/api/jobs/${id}`),

  document: (id: string) => request<DocumentPayload>(`/api/documents/${id}`),
  updateDocument: (id: string, body: { data?: object; settings?: DocSettings; text_content?: string }) =>
    request<DocumentPayload>(`/api/documents/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  compile: (id: string, source?: string) =>
    request<{ ok: boolean; pages: number; svgs: string[]; diagnostics: string; saved: boolean; mode: string }>(
      `/api/documents/${id}/compile`,
      { method: "POST", body: JSON.stringify({ source: source ?? null }) },
    ),
  chat: (id: string, message: string) =>
    request<{ ok: boolean; reply: string; data?: object; source?: string; svgs?: string[]; text_content?: string; diagnostics?: string }>(
      `/api/documents/${id}/chat`,
      { method: "POST", body: JSON.stringify({ message }) },
    ),

  billingCheckout: (plan: string) =>
    request<{ url: string }>("/api/billing/checkout", { method: "POST", body: JSON.stringify({ plan }) }),
  billingPortal: () => request<{ url: string }>("/api/billing/portal", { method: "POST" }),
};

export function jobEvents(jobId: string, onSnapshot: (s: JobSnapshot) => void): () => void {
  const es = new EventSource(`/api/jobs/${jobId}/events`);
  es.onmessage = (e) => {
    try {
      const snap = JSON.parse(e.data) as JobSnapshot;
      onSnapshot(snap);
      if (snap.status === "completed" || snap.status === "failed" || snap.status === "unknown") es.close();
    } catch { /* ignore malformed frames */ }
  };
  es.onerror = () => { /* the browser auto-reconnects; final states close above */ };
  return () => es.close();
}
