/* Left pane: Content | Source | Assistant tabs + the source-mode banner. */
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { useI18n } from "../../i18n";
import { ChatPanel } from "./ChatPanel";
import { ContentEditor } from "./ContentEditor";
import { SourceEditor } from "./SourceEditor";
import type { DocController } from "./useDocument";

type PanelTab = "content" | "source" | "chat";

export function EditorPanel({ ctl }: { ctl: DocController }) {
  const { t } = useI18n();
  const [tab, setTab] = useState<PanelTab>("content");
  const { doc, loading, syncing } = ctl;

  if (loading || !doc) {
    return (
      <div className="grid h-full place-items-center text-fg-dim">
        <Loader2 className="animate-spin" size={20} />
      </div>
    );
  }

  const isMessage = doc.kind === "message";
  const tabs: PanelTab[] = isMessage ? ["content", "chat"] : ["content", "source", "chat"];
  const labels: Record<PanelTab, string> = {
    content: t("studio.panel.content"),
    source: t("studio.panel.source"),
    chat: t("studio.panel.chat"),
  };

  return (
    <div className="flex h-full min-h-0 flex-col bg-ink-950">
      <div className="flex shrink-0 items-center justify-between border-b border-ink-800 px-2">
        <div role="tablist" className="flex">
          {tabs.map((tb) => (
            <button
              key={tb}
              role="tab"
              aria-selected={tab === tb}
              onClick={() => setTab(tb)}
              className={`px-3 py-2 font-mono text-[11px] uppercase tracking-wider transition-colors ${
                tab === tb ? "text-fg" : "text-fg-faint hover:text-fg-dim"
              }`}
            >
              {labels[tb]}
            </button>
          ))}
        </div>
        {syncing && <Loader2 size={13} className="mr-2 animate-spin text-blue-300" />}
      </div>

      {doc.mode === "source" && !isMessage && tab === "content" && (
        <div className="flex items-center justify-between gap-3 border-b border-ink-800 bg-blue-950/60 px-3 py-2 text-[12px] text-blue-300">
          <span>{t("studio.sourceMode.banner")}</span>
          <button
            onClick={() => void ctl.revertToData()}
            className="shrink-0 rounded border border-blue-500/40 px-2 py-1 text-[11px] hover:bg-blue-500/20"
          >
            {t("studio.sourceMode.revert")}
          </button>
        </div>
      )}

      <div className="min-h-0 flex-1">
        {tab === "content" && <ContentEditor ctl={ctl} />}
        {tab === "source" && !isMessage && <SourceEditor ctl={ctl} />}
        {tab === "chat" && <ChatPanel ctl={ctl} />}
      </div>
    </div>
  );
}
