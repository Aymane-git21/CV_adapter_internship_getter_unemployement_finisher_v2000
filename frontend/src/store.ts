/* Global state: session, app config, and the studio workspace. */
import { create } from "zustand";
import {
  api, jobEvents,
  type AppConfig, type DocumentPayload, type JobSnapshot, type Me,
} from "./api";

interface SessionState {
  me: Me | null;
  config: AppConfig | null;
  authOpen: boolean;
  bootstrap: () => Promise<void>;
  refreshMe: () => Promise<void>;
  setAuthOpen: (open: boolean) => void;
  logout: () => Promise<void>;
}

export const useSession = create<SessionState>((set) => ({
  me: null,
  config: null,
  authOpen: false,
  bootstrap: async () => {
    const [me, config] = await Promise.all([api.me().catch(() => null), api.config().catch(() => null)]);
    set({ me, config });
  },
  refreshMe: async () => set({ me: await api.me().catch(() => null) }),
  setAuthOpen: (authOpen) => set({ authOpen }),
  logout: async () => {
    await api.logout().catch(() => undefined);
    set({ me: await api.me().catch(() => null) });
  },
}));

/* ── studio ──────────────────────────────────────────────────────────────── */

const TABS_KEY = "cvg_open_jobs";

function loadTabIds(): string[] {
  try {
    return JSON.parse(localStorage.getItem(TABS_KEY) ?? "[]");
  } catch {
    return [];
  }
}
function saveTabIds(ids: string[]) {
  localStorage.setItem(TABS_KEY, JSON.stringify(ids.slice(-12)));
}

export type DocKind = "cv" | "letter" | "message";

interface StudioState {
  jobs: Record<string, JobSnapshot>;
  tabOrder: string[];
  activeJobId: string | null;
  activeKind: DocKind;
  docs: Record<string, DocumentPayload>; // by document id
  svgCache: Record<string, string[]>;
  unsubscribers: Record<string, () => void>;

  restoreTabs: () => Promise<void>;
  openJobs: (ids: string[]) => void;
  closeJob: (id: string) => void;
  setActive: (jobId: string, kind?: DocKind) => void;
  setActiveKind: (kind: DocKind) => void;
  watchJob: (id: string) => void;
  loadDocument: (docId: string) => Promise<DocumentPayload>;
  applyDocument: (doc: DocumentPayload) => void;
  setSvgs: (docId: string, svgs: string[]) => void;
}

export const useStudio = create<StudioState>((set, get) => ({
  jobs: {},
  tabOrder: [],
  activeJobId: null,
  activeKind: "cv",
  docs: {},
  svgCache: {},
  unsubscribers: {},

  restoreTabs: async () => {
    const ids = loadTabIds();
    if (!ids.length) return;
    const snaps = await Promise.all(ids.map((id) => api.job(id).catch(() => null)));
    const jobs: Record<string, JobSnapshot> = {};
    const order: string[] = [];
    snaps.forEach((s, i) => {
      if (s && s.status !== "unknown") {
        jobs[ids[i]] = s;
        order.push(ids[i]);
      }
    });
    set((st) => ({ jobs: { ...st.jobs, ...jobs }, tabOrder: order, activeJobId: order.at(-1) ?? null }));
    order.forEach((id) => {
      const s = jobs[id];
      if (s.status === "queued" || s.status === "running") get().watchJob(id);
    });
    saveTabIds(order);
  },

  openJobs: (ids) => {
    set((st) => {
      const order = [...st.tabOrder.filter((x) => !ids.includes(x)), ...ids];
      saveTabIds(order);
      return { tabOrder: order, activeJobId: ids[0] ?? st.activeJobId, activeKind: "cv" };
    });
    ids.forEach((id) => get().watchJob(id));
  },

  closeJob: (id) => {
    get().unsubscribers[id]?.();
    set((st) => {
      const order = st.tabOrder.filter((x) => x !== id);
      saveTabIds(order);
      const { [id]: _gone, ...jobs } = st.jobs;
      return {
        tabOrder: order,
        jobs,
        activeJobId: st.activeJobId === id ? (order.at(-1) ?? null) : st.activeJobId,
      };
    });
  },

  setActive: (jobId, kind) =>
    set((st) => ({ activeJobId: jobId, activeKind: kind ?? st.activeKind })),
  setActiveKind: (kind) => set({ activeKind: kind }),

  watchJob: (id) => {
    const st = get();
    st.unsubscribers[id]?.();
    const off = jobEvents(id, (snap) => {
      set((s) => ({ jobs: { ...s.jobs, [id]: snap } }));
    });
    set((s) => ({ unsubscribers: { ...s.unsubscribers, [id]: off } }));
  },

  loadDocument: async (docId) => {
    const cached = get().docs[docId];
    if (cached) return cached;
    const doc = await api.document(docId);
    get().applyDocument(doc);
    return doc;
  },

  applyDocument: (doc) =>
    set((st) => ({
      docs: { ...st.docs, [doc.id]: { ...doc, svgs: null } },
      svgCache: doc.svgs ? { ...st.svgCache, [doc.id]: doc.svgs } : st.svgCache,
    })),

  setSvgs: (docId, svgs) =>
    set((st) => ({ svgCache: { ...st.svgCache, [docId]: svgs } })),
}));
