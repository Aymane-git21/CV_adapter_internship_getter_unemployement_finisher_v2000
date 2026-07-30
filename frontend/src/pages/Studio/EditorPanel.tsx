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
      <div className="grid h-full place-items-center text-text/70">
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
    <div className="flex h-full min-h-0 flex-col bg-transparent">
      <div className="flex shrink-0 items-center justify-between border-b border-black/10 px-2">
        <div role="tablist" className="flex">
          {tabs.map((tb) => (
            <button
              key={tb}
              role="tab"
              aria-selected={tab === tb}
              onClick={() => setTab(tb)}
              className={`border-b-2 px-3.5 py-2.5 text-[13px] font-semibold transition-colors ${
                tab === tb ? "border-flame-500 text-text" : "border-transparent text-text/60 hover:text-text"
              }`}
            >
              {labels[tb]}
            </button>
          ))}
        </div>
        {syncing && <Loader2 size={13} className="mr-2 animate-spin text-primary/80" />}
      </div>

      {doc.mode === "source" && !isMessage && tab === "content" && (
        <div className="flex items-center justify-between gap-3 border-b border-black/10 bg-flame-950/60 px-3 py-2 text-[12px] text-primary/80">
          <span>{t("studio.sourceMode.banner")}</span>
          <button
            onClick={() => void ctl.revertToData()}
            className="shrink-0 rounded border border-flame-500/40 px-2 py-1 text-[11px] hover:bg-primary/20"
          >
            {t("studio.sourceMode.revert")}
          </button>
        </div>
      )}

      <div className="min-h-0 flex-1">
        {tab === "content" && <ContentEditor ctl={ctl} />}
        {tab === "source" && !isMessage && <SourceEditor ctl={ctl} />}
        {tab === "chat" &&
          ((doc.settings?.compiler ?? "typst") === "latex" && doc.mode === "source" ? (
            <div className="p-4 text-[12.5px] leading-relaxed text-text/60">
              {t("studio.chat.latexsource")}
            </div>
          ) : (
            <ChatPanel ctl={ctl} />
          ))}
      </div>
    </div>
  );
}
