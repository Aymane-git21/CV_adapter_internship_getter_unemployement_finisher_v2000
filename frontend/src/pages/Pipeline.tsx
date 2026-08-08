/* Pipeline — the review queue. One column per status, one card per
   application: generate on inbox, approve once documents are ready, then
   send (or mark applied manually when a posting has no apply email).
   Polls every 15s so postings from the background poller and job
   completions from the studio show up without a manual refresh. */
import { CheckCircle2, ExternalLink, FileText, Inbox as InboxIcon, Loader2, Send } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type PipelineApp } from "../api";
import { useI18n } from "../i18n";
import { useSession } from "../store";

// `as const satisfies` keeps the literal 4-value tuple (so the icon map below
// and the pipeline.col.* lookups stay narrow) while still checking every
// entry is a real PipelineApp["status"].
const COLUMNS = ["inbox", "generated", "approved", "sent"] as const satisfies readonly PipelineApp["status"][];

const COLUMN_ICON: Record<(typeof COLUMNS)[number], typeof InboxIcon> = {
  inbox: InboxIcon,
  generated: FileText,
  approved: CheckCircle2,
  sent: Send,
};

type Act = (id: number, fn: () => Promise<unknown>) => Promise<void>;

function ApplicationCard({ app: a, busy, act }: { app: PipelineApp; busy: boolean; act: Act }) {
  const { t } = useI18n();
  return (
    <article className="card-lift rounded-lg border border-black/10 glass-panel p-3.5">
      <div className="text-[13.5px] font-semibold leading-snug">{a.posting.title}</div>
      <div className="mt-0.5 text-[12px] text-text/70">
        {a.posting.company}
        {a.posting.company && a.posting.location ? " · " : ""}
        {a.posting.location}
      </div>
      <div className="mt-1.5 font-mono text-[10px] uppercase tracking-wider text-text/40">
        {a.posting.source}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {a.status === "inbox" && (
          <button
            disabled={busy}
            onClick={() =>
              act(a.id, () =>
                api.pipelineGenerate([a.id], {
                  template: "onyx", accent: "#C2551B", language: "fr", rewrite_intensity: "major",
                }),
              )
            }
            className="btn-flame flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[12px] font-semibold disabled:opacity-50"
          >
            {busy && <Loader2 size={12} className="animate-spin" />}
            {t("pipeline.generate")}
          </button>
        )}

        {a.status === "generated" && (
          <>
            {a.job_id && (
              <Link
                to={`/studio?job=${a.job_id}`}
                className="rounded-md border border-black/10 px-2.5 py-1.5 text-[12px] text-text/70 hover:border-ink-600 hover:text-text"
              >
                {t("pipeline.viewDocs")}
              </Link>
            )}
            <button
              disabled={busy}
              onClick={() => act(a.id, () => api.pipelineApprove(a.id))}
              className="btn-flame flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[12px] font-semibold disabled:opacity-50"
            >
              {busy && <Loader2 size={12} className="animate-spin" />}
              {t("pipeline.approve")}
            </button>
          </>
        )}

        {a.status === "approved" &&
          (a.posting.apply_email ? (
            <button
              disabled={busy}
              onClick={() => act(a.id, () => api.pipelineSend(a.id, {}))}
              className="btn-flame flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[12px] font-semibold disabled:opacity-50"
            >
              {busy && <Loader2 size={12} className="animate-spin" />}
              {t("pipeline.send")}
            </button>
          ) : (
            <>
              {a.posting.apply_url && (
                <a
                  href={a.posting.apply_url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1 rounded-md border border-black/10 px-2.5 py-1.5 text-[12px] text-text/70 hover:border-ink-600 hover:text-text"
                >
                  {t("pipeline.openPosting")} <ExternalLink size={11} />
                </a>
              )}
              <button
                disabled={busy}
                onClick={() => act(a.id, () => api.pipelineMarkSent(a.id))}
                className="rounded-md border border-black/10 px-2.5 py-1.5 text-[12px] text-text/70 hover:border-ink-600 hover:text-text disabled:opacity-50"
              >
                {t("pipeline.markSent")}
              </button>
            </>
          ))}

        {a.status === "sent" && (
          <span className="flex items-center gap-1.5 font-mono text-[11px] text-ok-400">
            <CheckCircle2 size={12} />
            {a.sent_via} · {a.sent_at?.slice(0, 10)}
          </span>
        )}

        {a.status !== "sent" && (
          <button
            disabled={busy}
            onClick={() => act(a.id, () => api.pipelineReject(a.id, ""))}
            className="ml-auto rounded-md px-2 py-1.5 text-[12px] text-text/50 hover:text-danger disabled:opacity-50"
          >
            {t("pipeline.reject")}
          </button>
        )}
      </div>
    </article>
  );
}

export default function Pipeline() {
  const { t } = useI18n();
  const me = useSession((s) => s.me);
  const setAuthOpen = useSession((s) => s.setAuthOpen);
  const [apps, setApps] = useState<PipelineApp[] | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState("");

  const reload = useCallback(() => {
    api
      .pipeline()
      .then((r) => setApps(r.applications))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  useEffect(() => {
    if (!me?.authenticated) return;
    reload();
    const id = setInterval(reload, 15000);
    return () => clearInterval(id);
  }, [me?.authenticated, reload]);

  const act: Act = async (id, fn) => {
    setBusy(id);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
    setBusy(null);
    reload();
  };

  if (me && !me.authenticated) {
    return (
      <div className="grid min-h-[60vh] place-items-center px-6 text-center">
        <div>
          <p className="mb-4 text-text/70">{t("pipeline.loginFirst")}</p>
          <button onClick={() => setAuthOpen(true)} className="btn-flame rounded-lg px-5 py-2.5 text-sm font-semibold">
            {t("nav.login")}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-6 py-14">
      <div className="mb-10 flex flex-wrap items-center justify-between gap-4">
        <h1 className="font-sans text-3xl font-semibold tracking-tight">{t("pipeline.title")}</h1>
        <Link
          to="/settings"
          className="text-[13px] text-text/70 underline-offset-2 hover:text-text hover:underline"
        >
          {t("pipeline.settingsLink")}
        </Link>
      </div>

      {error && (
        <div className="mb-6 rounded-md border border-signal-500/30 bg-signal-950 px-3.5 py-2.5 text-[13px] text-danger">
          {error}
        </div>
      )}

      {apps === null ? (
        <div className="grid place-items-center py-24 text-text/70">
          <Loader2 className="animate-spin" size={20} />
        </div>
      ) : apps.length === 0 ? (
        <div className="rounded-xl border border-dashed border-ink-600 p-12 text-center">
          <InboxIcon size={28} className="mx-auto mb-4 text-text/50" />
          <p className="text-[14.5px] text-text/70">{t("pipeline.empty")}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
          {COLUMNS.map((col) => {
            const Icon = COLUMN_ICON[col];
            const items = apps.filter((a) => a.status === col);
            return (
              <section key={col}>
                <h2 className="mb-3 flex items-center gap-1.5 font-mono text-[11px] font-semibold uppercase tracking-wider text-text/50">
                  <Icon size={12} />
                  {t(`pipeline.col.${col}`)}
                  <span className="font-normal text-text/30">({items.length})</span>
                </h2>
                <div className="space-y-3">
                  {items.map((a) => (
                    <ApplicationCard key={a.id} app={a} busy={busy === a.id} act={act} />
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
