/* Right pane: the paper. Live SVG pages, zoom, score card, downloads. */
import { Download, FileCode2, Loader2, Minus, Plus } from "lucide-react";
import { useState } from "react";
import { useI18n } from "../../i18n";
import type { DocController } from "./useDocument";

function ScoreCard({ ctl }: { ctl: DocController }) {
  const { t } = useI18n();
  const doc = ctl.doc;
  if (!doc || doc.kind !== "cv" || doc.score_after == null) return null;
  const missing = doc.keywords?.missing ?? [];
  return (
    <div className="border-b border-ink-800 bg-ink-900/60 px-4 py-2.5">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5">
        <span className="eyebrow">{t("studio.score.title")}</span>
        <span className="font-mono text-[13px]">
          <span className="text-fg-faint">{doc.score_before}%</span>
          <span className="mx-1.5 text-fg-faint">→</span>
          <span className="font-semibold text-ok-400">{doc.score_after}%</span>
        </span>
        {missing.length > 0 ? (
          <span className="flex flex-wrap items-center gap-1.5">
            <span className="font-mono text-[10.5px] uppercase tracking-wider text-fg-faint">
              {t("studio.score.missing")}:
            </span>
            {missing.slice(0, 5).map((k) => (
              <span key={k} className="rounded-full border border-signal-500/25 bg-signal-950 px-2 py-0.5 font-mono text-[10.5px] text-signal-400">
                {k}
              </span>
            ))}
            {missing.length > 5 && (
              <span className="font-mono text-[10.5px] text-fg-faint">+{missing.length - 5}</span>
            )}
          </span>
        ) : (
          <span className="font-mono text-[11px] text-ok-400">{t("studio.score.none")}</span>
        )}
      </div>
    </div>
  );
}

export function Preview({ ctl }: { ctl: DocController }) {
  const { t } = useI18n();
  const [zoom, setZoom] = useState(1);
  const { doc, svgs, syncing } = ctl;

  if (!doc) return <div className="h-full bg-ink-900/40" />;

  if (doc.kind === "message") {
    return (
      <div className="grid h-full place-items-center overflow-y-auto bg-ink-900/40 p-8">
        <div className="sheet w-full max-w-md p-8">
          <p className="whitespace-pre-wrap font-sans text-[13.5px] leading-relaxed text-neutral-800">
            {doc.text_content}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col bg-ink-900/40">
      <ScoreCard ctl={ctl} />

      <div className="flex shrink-0 items-center justify-between border-b border-ink-800 px-4 py-1.5">
        <div className="flex items-center gap-1">
          <button
            onClick={() => setZoom((z) => Math.max(0.5, +(z - 0.15).toFixed(2)))}
            className="grid size-7 place-items-center rounded text-fg-dim hover:bg-ink-800 hover:text-fg"
            aria-label="Zoom out"
          >
            <Minus size={13} />
          </button>
          <button
            onClick={() => setZoom(1)}
            className="rounded px-2 py-1 font-mono text-[11px] text-fg-dim hover:bg-ink-800 hover:text-fg"
          >
            {zoom === 1 ? t("studio.preview.fit") : `${Math.round(zoom * 100)}%`}
          </button>
          <button
            onClick={() => setZoom((z) => Math.min(2, +(z + 0.15).toFixed(2)))}
            className="grid size-7 place-items-center rounded text-fg-dim hover:bg-ink-800 hover:text-fg"
            aria-label="Zoom in"
          >
            <Plus size={13} />
          </button>
          {syncing && <Loader2 size={12} className="ml-2 animate-spin text-blue-300" />}
        </div>
        <div className="flex items-center gap-2">
          <a
            href={`/api/documents/${doc.id}/source.typ`}
            className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 font-mono text-[11px] text-fg-dim hover:bg-ink-800 hover:text-fg"
            title={t("studio.download.typ")}
          >
            <FileCode2 size={13} /> .typ
          </a>
          <a
            href={`/api/documents/${doc.id}/pdf`}
            className="flex items-center gap-1.5 rounded-md bg-blue-500 px-3 py-1.5 text-[12px] font-medium text-white hover:bg-blue-400"
          >
            <Download size={13} /> {t("studio.download.pdf")}
          </a>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto p-6">
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
