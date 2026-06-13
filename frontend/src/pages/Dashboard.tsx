/* Dashboard — application history, reopenable in the studio. */
import { ArrowRight, FileText, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type HistoryEntry } from "../api";
import { AdSlot } from "../components/AdSlot";
import { useI18n } from "../i18n";
import { useSession, useStudio } from "../store";

const copy = {
  en: {
    eyebrow: "Your applications",
    title: "Everything you've tailored",
    empty: "Nothing here yet — generate your first application and it will land here.",
    start: "Open the studio",
    open: "Open",
    loginFirst: "Log in to see your application history.",
  },
  fr: {
    eyebrow: "Vos candidatures",
    title: "Tout ce que vous avez adapté",
    empty: "Rien ici pour l'instant — générez votre première candidature et elle apparaîtra ici.",
    start: "Ouvrir le studio",
    open: "Ouvrir",
    loginFirst: "Connectez-vous pour voir votre historique.",
  },
};

export default function Dashboard() {
  const { lang } = useI18n();
  const c = copy[lang];
  const me = useSession((s) => s.me);
  const setAuthOpen = useSession((s) => s.setAuthOpen);
  const openJobs = useStudio((s) => s.openJobs);
  const navigate = useNavigate();
  const [rows, setRows] = useState<HistoryEntry[] | null>(null);

  useEffect(() => {
    if (!me?.authenticated) return;
    void api.history().then(setRows).catch(() => setRows([]));
  }, [me?.authenticated]);

  if (me && !me.authenticated) {
    return (
      <div className="grid min-h-[60vh] place-items-center px-6 text-center">
        <div>
          <p className="mb-4 text-fg-dim">{c.loginFirst}</p>
          <button
            onClick={() => setAuthOpen(true)}
            className="rounded-lg bg-blue-500 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-400"
          >
            Log in
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-6 py-14">
      <p className="eyebrow mb-3">{c.eyebrow}</p>
      <h1 className="mb-10 font-serif text-3xl font-semibold tracking-tight">{c.title}</h1>

      {rows === null ? (
        <div className="grid place-items-center py-20 text-fg-dim">
          <Loader2 className="animate-spin" size={20} />
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-xl border border-dashed border-ink-600 p-12 text-center">
          <FileText size={28} className="mx-auto mb-4 text-fg-faint" />
          <p className="mb-6 text-[14.5px] text-fg-dim">{c.empty}</p>
          <button
            onClick={() => navigate("/studio")}
            className="rounded-lg bg-blue-500 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-400"
          >
            {c.start}
          </button>
        </div>
      ) : (
        <div className="divide-y divide-ink-800 rounded-xl border border-ink-800 bg-ink-900/50">
          {rows.map((r) => (
            <div key={r.id} className="flex items-center gap-4 px-5 py-4">
              <div className="min-w-0 flex-1">
                <p className="truncate text-[14.5px] font-medium">
                  {r.title}
                  {r.company && <span className="text-fg-dim"> — {r.company}</span>}
                </p>
                <p className="mt-0.5 font-mono text-[11px] text-fg-faint">
                  {r.created_at ? new Date(r.created_at).toLocaleDateString(lang) : ""}
                  {" · "}
                  {r.documents.length} docs · {r.language.toUpperCase()}
                </p>
              </div>
              {r.score_before != null && r.score_after != null && (
                <span className="hidden font-mono text-[12.5px] sm:block">
                  <span className="text-fg-faint">{r.score_before}%</span>
                  <span className="mx-1 text-fg-faint">→</span>
                  <span className="font-semibold text-ok-400">{r.score_after}%</span>
                </span>
              )}
              <span
                className={`hidden rounded-full px-2 py-0.5 font-mono text-[10px] uppercase sm:block ${
                  r.status === "completed"
                    ? "bg-ok-950 text-ok-400"
                    : r.status === "failed"
                      ? "bg-signal-950 text-signal-400"
                      : "bg-ink-800 text-fg-dim"
                }`}
              >
                {r.status}
              </span>
              <button
                onClick={() => {
                  openJobs([r.id]);
                  navigate("/studio");
                }}
                className="flex items-center gap-1.5 rounded-md border border-ink-700 px-3 py-1.5 text-[13px] text-fg-dim transition hover:border-blue-500 hover:text-fg"
              >
                {c.open} <ArrowRight size={13} />
              </button>
            </div>
          ))}
        </div>
      )}
      <AdSlot slot="dashboard-footer" className="mt-8" />
    </div>
  );
}
