/* Right pane: the paper. Live SVG pages, zoom, score card, downloads. */
import { Download, FileCode2, Loader2, Minus, Plus, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../../api";
import { useI18n } from "../../i18n";
import { SettingsPopover } from "./SettingsPopover";
import type { DocController } from "./useDocument";

/* Warm-compiler chip: shows starting -> warm; X clears this doc's remote
   compile cache (never scales the service down). */
function LatexChip({ ctl }: { ctl: DocController }) {
  const { t } = useI18n();
  const [warm, setWarm] = useState<boolean | null>(null);
  const [ended, setEnded] = useState(false);
  const doc = ctl.doc;
  const active = (doc?.settings.compiler ?? "typst") === "latex";

  useEffect(() => {
    if (!active) return;
    let stop = false;
    let timer: number | undefined;
    const poll = async () => {
      try {
        const s = await api.latexStatus();
        if (stop) return;
        setWarm(s.warm);
        if (!s.warm) timer = window.setTimeout(() => void poll(), 5000);
      } catch {
        if (!stop) timer = window.setTimeout(() => void poll(), 8000);
      }
    };
    void poll();
    return () => { stop = true; window.clearTimeout(timer); };
  }, [active, doc?.id]);

  if (!active || !doc) return null;
  const end = async () => {
    try {
      await api.latexEndSession(doc.id);
      setEnded(true);
      window.setTimeout(() => setEnded(false), 2500);
    } catch { /* cache clear is best effort */ }
  };
  return (
    <span className="ml-1.5 flex items-center gap-1 rounded-full border border-black/10 glass-panel py-0.5 pl-2 pr-1 font-mono text-[10.5px] text-text/70">
      <span className={`size-1.5 rounded-full ${warm ? "bg-ok-400" : "animate-pulse bg-signal-500"}`} />
      {ended ? t("studio.latex.ended") : warm ? t("studio.latex.active") : t("studio.latex.starting")}
      <button onClick={() => void end()} title={t("studio.latex.end")} aria-label={t("studio.latex.end")}
              className="grid size-4 place-items-center rounded-full text-text/50 hover:bg-black/10 hover:text-text">
        <X size={9} />
      </button>
    </span>
  );
}

function ScoreCard({ ctl }: { ctl: DocController }) {
  const { t } = useI18n();
  const doc = ctl.doc;
  if (!doc || doc.kind !== "cv" || doc.score_after == null) return null;
  const missing = doc.keywords?.missing ?? [];
  return (
    <div className="border-b border-black/10 glass-panel/60 px-4 py-2.5">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5">
        <span className="eyebrow">{t("studio.score.title")}</span>
        <span className="text-[15px] font-semibold tabular-nums">
          <span className="text-text/50">{doc.score_before}%</span>
          <span className="mx-1.5 text-text/50">→</span>
          <span className="font-bold text-ok-400">{doc.score_after}%</span>
        </span>
        {missing.length > 0 ? (
          <span className="flex flex-wrap items-center gap-1.5">
            <span className="text-[12px] font-semibold text-text/60">
              {t("studio.score.missing")}:
            </span>
            {missing.slice(0, 5).map((k) => (
              <span key={k} className="rounded-full border border-signal-500/25 bg-signal-950 px-2 py-0.5 text-[12px] font-medium text-danger">
                {k}
              </span>
            ))}
            {missing.length > 5 && (
              <span className="text-[12px] font-medium text-text/50">+{missing.length - 5}</span>
            )}
          </span>
        ) : (
          <span className="text-[12px] font-medium text-ok-400">{t("studio.score.none")}</span>
        )}
      </div>
    </div>
  );
}

export function Preview({ ctl }: { ctl: DocController }) {
  const { t } = useI18n();
  const [zoom, setZoom] = useState(1);
  const { doc, svgs, syncing } = ctl;

  if (!doc) return <div className="h-full glass-panel" />;

  if (doc.kind === "message") {
    return (
      <div className="grid h-full place-items-center overflow-y-auto glass-panel p-8">
        <div className="sheet w-full max-w-md p-8">
          <p className="whitespace-pre-wrap font-sans text-[13.5px] leading-relaxed text-neutral-800">
            {doc.text_content}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col glass-panel">
      <ScoreCard ctl={ctl} />

      <div className="flex shrink-0 items-center justify-between border-b border-black/10 px-4 py-1.5">
        <div className="flex items-center gap-1">
          <button
            onClick={() => setZoom((z) => Math.max(0.5, +(z - 0.15).toFixed(2)))}
            className="grid size-7 place-items-center rounded text-text/70 hover:glass-panel hover:text-text"
            aria-label="Zoom out"
          >
            <Minus size={13} />
          </button>
          <button
            onClick={() => setZoom(1)}
            className="rounded px-2 py-1 text-[12px] font-medium tabular-nums text-text/70 hover:glass-panel hover:text-text"
          >
            {zoom === 1 ? t("studio.preview.fit") : `${Math.round(zoom * 100)}%`}
          </button>
          <button
            onClick={() => setZoom((z) => Math.min(2, +(z + 0.15).toFixed(2)))}
            className="grid size-7 place-items-center rounded text-text/70 hover:glass-panel hover:text-text"
            aria-label="Zoom in"
          >
            <Plus size={13} />
          </button>
          <span className="mx-1 h-4 w-px bg-black/10" />
          <SettingsPopover ctl={ctl} />
          <LatexChip ctl={ctl} />
          {syncing && <Loader2 size={12} className="ml-2 animate-spin text-primary/80" />}
        </div>
        <div className="flex items-center gap-2">
          {(doc.settings.compiler ?? "typst") === "latex" ? (
            <a
              href={`/api/documents/${doc.id}/source.tex`}
              className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[12px] font-medium text-text/70 hover:glass-panel hover:text-text"
              title={t("studio.download.tex")}
            >
              <FileCode2 size={13} /> .tex
            </a>
          ) : (
          <a
            href={`/api/documents/${doc.id}/source.typ`}
            className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[12px] font-medium text-text/70 hover:glass-panel hover:text-text"
            title={t("studio.download.typ")}
          >
            <FileCode2 size={13} /> .typ
          </a>
          )}
          <a
            href={`/api/documents/${doc.id}/pdf`}
            className="flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-[12px] font-medium text-white hover:bg-primary/90"
          >
            <Download size={13} /> {t("studio.download.pdf")}
          </a>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto p-6">
        {doc.settings.overflowed && (
          <div className="mx-auto mb-3 max-w-[880px] rounded-md border border-signal-500/30 bg-signal-950 p-2.5">
            <p className="eyebrow mb-1 text-danger">{t("studio.overflow.title")}</p>
            <p className="text-[12px] leading-relaxed text-danger/90">{t("studio.overflow.body")}</p>
          </div>
        )}
        {ctl.diagnostics && (
          <div className="mx-auto mb-3 max-h-32 max-w-[880px] overflow-y-auto rounded-md border border-signal-500/30 bg-signal-950 p-2.5">
            <p className="eyebrow mb-1 text-danger">{t("studio.compile.error")}</p>
            <pre className="whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-danger/90">{ctl.diagnostics}</pre>
          </div>
        )}
        <div className="mx-auto space-y-6 transition-[width] duration-200" style={{ width: `${zoom * 100}%`, maxWidth: zoom === 1 ? "880px" : undefined }}>
          {svgs ? (
            svgs.map((svg, i) => (
              <div key={i} className="sheet overflow-hidden" dangerouslySetInnerHTML={{ __html: svg }} />
            ))
          ) : (
            <div className="sheet grid aspect-[1/1.414] place-items-center">
              <Loader2 size={22} className="animate-spin text-neutral-400" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
