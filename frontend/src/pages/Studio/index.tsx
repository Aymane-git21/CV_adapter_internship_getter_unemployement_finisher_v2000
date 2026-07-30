/* The Studio — Overleaf-style split workspace with parallel job tabs. */
import { CheckCircle2, Loader2, Plus, X, XCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import type { JobSnapshot } from "../../api";
import { AdSlot } from "../../components/AdSlot";
import { useI18n } from "../../i18n";
import { useSession, useStudio, type DocKind } from "../../store";
import { EditorPanel } from "./EditorPanel";
import { NewJobPanel } from "./NewJobPanel";
import { Preview } from "./Preview";
import { useDocument } from "./useDocument";

function JobTab({ job, active, onSelect, onClose }: {
  job: JobSnapshot; active: boolean; onSelect: () => void; onClose: () => void;
}) {
  const icon =
    job.status === "completed" ? <CheckCircle2 size={13} className="text-ok-400" />
    : job.status === "failed" ? <XCircle size={13} className="text-danger" />
    : <Loader2 size={13} className="animate-spin text-primary/80" />;
  return (
    <div
      role="tab"
      aria-selected={active}
      onClick={onSelect}
      className={`group flex max-w-56 cursor-pointer items-center gap-2 border-r border-black/10 px-3.5 py-2 text-[13px] transition-colors ${
        active ? "bg-ink-850 text-text" : "bg-transparent text-text/70 hover:glass-panel hover:text-text"
      }`}
    >
      {icon}
      <span className="truncate">{job.title ?? "…"}</span>
      <button
        onClick={(e) => { e.stopPropagation(); onClose(); }}
        className="ml-1 hidden rounded p-0.5 text-text/50 hover:bg-ink-700 hover:text-text group-hover:block"
        aria-label="Close tab"
      >
        <X size={12} />
      </button>
    </div>
  );
}

const STEP_STAGE: Record<string, number> = {
  analyze: 1,
  analyzed: 1,
  generate: 2,
  generated: 2,
  render: 3,
  done: 4,
};

function ProgressView({ job }: { job: JobSnapshot }) {
  const { t } = useI18n();
  const last = job.events.at(-1);
  const pct = last?.pct ?? 0;
  const stage = job.events.reduce((max, ev) => Math.max(max, STEP_STAGE[ev.step] ?? max), 1);
  const stages = [
    { n: 1, label: t("studio.progress.analyze") },
    { n: 2, label: t("studio.progress.generate") },
    { n: 3, label: t("studio.progress.render") },
    { n: 4, label: t("studio.progress.done") },
  ];
  return (
    <div className="grid h-full place-items-center p-6">
      <div className="w-full max-w-2xl">
        <div className="mb-2 flex items-baseline justify-between gap-3">
          <p className="eyebrow">{t("studio.progress.title")}</p>
          <span className="text-[12px] font-semibold tabular-nums text-text/60">{pct}%</span>
        </div>
        <div className="mb-5 h-1 overflow-hidden rounded-full glass-panel">
          <div
            className="h-full rounded-full bg-primary transition-all duration-700"
            style={{ width: `${Math.max(4, pct)}%` }}
          />
        </div>
        <div className="grid gap-6 sm:grid-cols-[1fr_200px]">
          <div className="space-y-3 self-start rounded-lg border border-black/10 glass-panel p-4">
            {stages.map((s) => (
              <div key={s.n} className="flex items-start gap-2.5">
                {s.n < stage ? (
                  <CheckCircle2 size={13} className="mt-px shrink-0 text-ok-400" />
                ) : s.n === stage ? (
                  <Loader2 size={13} className="mt-px shrink-0 animate-spin text-primary" />
                ) : (
                  <span className="mt-px grid size-[13px] shrink-0 place-items-center text-text/30">
                    <span className="size-1.5 rounded-full bg-current" />
                  </span>
                )}
                <div className="min-w-0">
                  <p className={`text-[13px] ${s.n <= stage ? "text-text" : "text-text/40"}`}>{s.label}</p>
                  {s.n === stage && last && (
                    <p className="mt-0.5 truncate font-mono text-[11px] text-text/50">{last.message}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
          <div className="sheet mx-auto aspect-[1/1.414] w-full max-w-[200px] p-5 sm:mx-0 sm:max-w-none">
            <div className="skeleton-shimmer mb-4 h-4 w-1/2" />
            <div className="skeleton-shimmer mb-5 h-2 w-1/3" />
            <div className="skeleton-shimmer mb-2.5 h-2 w-full" />
            <div className="skeleton-shimmer mb-2.5 h-2 w-5/6" />
            <div className="skeleton-shimmer mb-5 h-2 w-2/3" />
            <div className="skeleton-shimmer mb-2.5 h-2 w-full" />
            <div className="skeleton-shimmer mb-2.5 h-2 w-3/4" />
            <div className="skeleton-shimmer h-2 w-1/2" />
          </div>
        </div>
        <AdSlot slot="studio-progress" className="mt-6" />
      </div>
    </div>
  );
}

function FailedView({ job, onClose }: { job: JobSnapshot; onClose: () => void }) {
  const { t } = useI18n();
  return (
    <div className="grid h-full place-items-center p-6">
      <div className="max-w-md text-center">
        <XCircle size={32} className="mx-auto mb-3 text-danger" />
        <h2 className="mb-2 font-sans text-lg font-semibold">{t("studio.failed")}</h2>
        <p className="mb-5 text-sm text-text/70">{job.error}</p>
        <button
          onClick={onClose}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90"
        >
          {t("studio.retry")}
        </button>
      </div>
    </div>
  );
}

function Workspace({ job }: { job: JobSnapshot }) {
  const activeKind = useStudio((s) => s.activeKind);
  const setActiveKind = useStudio((s) => s.setActiveKind);
  const { t } = useI18n();
  const me = useSession((s) => s.me);
  const setAuthOpen = useSession((s) => s.setAuthOpen);

  const activeDoc = useMemo(
    () => job.documents?.find((d) => d.kind === activeKind) ?? job.documents?.[0] ?? null,
    [job.documents, activeKind],
  );
  const ctl = useDocument(activeDoc?.id ?? null);

  const kinds: DocKind[] = ["cv", "letter", "message"];

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex shrink-0 items-center justify-between border-b border-black/10 glass-panel/60 px-3">
        <div role="tablist" className="flex">
          {kinds.map((k) => (
            <button
              key={k}
              role="tab"
              aria-selected={activeKind === k}
              onClick={() => setActiveKind(k)}
              className={`border-b-2 px-3.5 py-2.5 text-[13px] transition-colors ${
                activeKind === k
                  ? "border-flame-500 text-text"
                  : "border-transparent text-text/70 hover:text-text"
              }`}
            >
              {t(`studio.doc.${k}` as Parameters<typeof t>[0])}
            </button>
          ))}
        </div>
        {me && !me.authenticated && (
          <button
            onClick={() => setAuthOpen(true)}
            className="hidden rounded-md border border-flame-500/40 bg-flame-950 px-3 py-1.5 text-xs text-primary/80 hover:bg-primary/20 lg:block"
          >
            {t("studio.guest.cta")}
          </button>
        )}
      </div>

      <div className="min-h-0 flex-1">
        <PanelGroup direction="horizontal" autoSaveId="cvg-studio">
          <Panel defaultSize={44} minSize={28} className="min-w-0">
            <EditorPanel ctl={ctl} />
          </Panel>
          <PanelResizeHandle className="w-px bg-ink-700 transition-colors hover:bg-primary data-[resize-handle-state=drag]:bg-primary" />
          <Panel minSize={30} className="min-w-0">
            <Preview ctl={ctl} />
          </Panel>
        </PanelGroup>
      </div>
    </div>
  );
}

export default function Studio() {
  const { t } = useI18n();
  const jobs = useStudio((s) => s.jobs);
  const tabOrder = useStudio((s) => s.tabOrder);
  const activeJobId = useStudio((s) => s.activeJobId);
  const setActive = useStudio((s) => s.setActive);
  const closeJob = useStudio((s) => s.closeJob);
  const restoreTabs = useStudio((s) => s.restoreTabs);
  const [showNew, setShowNew] = useState(false);

  useEffect(() => {
    void restoreTabs();
  }, [restoreTabs]);

  const activeJob = activeJobId ? jobs[activeJobId] : null;
  const showNewPanel = showNew || tabOrder.length === 0;

  return (
    <div className="flex h-full min-h-0 flex-col bg-transparent">
      {/* job tab strip */}
      <div className="flex h-9 shrink-0 items-stretch border-b border-black/10 bg-transparent">
        <div className="flex flex-1 items-stretch overflow-x-auto">
          {tabOrder.map((id) =>
            jobs[id] ? (
              <JobTab
                key={id}
                job={jobs[id]}
                active={id === activeJobId && !showNew}
                onSelect={() => { setShowNew(false); setActive(id); }}
                onClose={() => closeJob(id)}
              />
            ) : null,
          )}
        </div>
        <button
          onClick={() => setShowNew(true)}
          className={`flex items-center gap-1.5 border-l border-black/10 px-3.5 text-[13px] transition-colors ${
            showNewPanel ? "bg-ink-850 text-text" : "text-text/70 hover:text-text"
          }`}
        >
          <Plus size={14} className="text-primary/80" />
          <span className="hidden sm:inline">{t("studio.newJob")}</span>
        </button>
      </div>

      <div className="min-h-0 flex-1">
        {showNewPanel ? (
          <NewJobPanel onLaunched={() => setShowNew(false)} />
        ) : !activeJob ? null : activeJob.status === "failed" ? (
          <FailedView job={activeJob} onClose={() => closeJob(activeJob.id)} />
        ) : activeJob.status !== "completed" ? (
          <ProgressView job={activeJob} />
        ) : (
          <Workspace job={activeJob} />
        )}
      </div>
    </div>
  );
}
