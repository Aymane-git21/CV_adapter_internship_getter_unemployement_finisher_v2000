/* Layout settings popover in the preview toolbar. First consumer of
   ctl.updateSettings; card-list options per the house pattern (no segments). */
import { Settings2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useI18n } from "../../i18n";
import type { DocController } from "./useDocument";

const MODES = ["paged", "continuous"] as const;

export function SettingsPopover({ ctl }: { ctl: DocController }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const doc = ctl.doc;

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  if (!doc || doc.kind === "message") return null;
  const settings = doc.settings;
  const sourceLocked = doc.mode === "source";

  const pick = (page_mode: string) => {
    if (sourceLocked || page_mode === (settings.page_mode ?? "paged")) return;
    void ctl.updateSettings({ ...settings, page_mode });
  };

  return (
    <div className="relative" ref={rootRef}>
      <button
        onClick={() => setOpen((o) => !o)}
        className={`grid size-7 place-items-center rounded text-text/70 hover:glass-panel hover:text-text ${open ? "glass-panel text-text" : ""}`}
        aria-label={t("studio.settings.title")}
        title={t("studio.settings.title")}
      >
        <Settings2 size={13} />
      </button>
      {open && (
        <div className="glass-panel absolute left-0 top-full z-20 mt-2 w-64 rounded-lg border border-black/10 p-3 shadow-lg">
          <p className="eyebrow mb-3">{t("studio.pagemode.title")}</p>
          <div className="space-y-2">
            {MODES.map((m) => (
              <button
                key={m}
                onClick={() => pick(m)}
                disabled={sourceLocked}
                className={`block w-full rounded-lg border px-3.5 py-2.5 text-left transition-colors ${
                  (settings.page_mode ?? "paged") === m
                    ? "border-flame-500 bg-flame-950"
                    : "border-black/10 glass-panel hover:border-ink-600"
                } ${sourceLocked ? "cursor-not-allowed opacity-50" : ""}`}
              >
                <span className="block text-[13px] font-medium">{t(`studio.pagemode.${m}`)}</span>
                <span className="block text-[11px] text-text/50">{t(`studio.pagemode.${m}.desc`)}</span>
              </button>
            ))}
          </div>
          {sourceLocked && (
            <p className="mt-2 text-[11px] text-text/50">{t("studio.settings.sourcelock")}</p>
          )}
        </div>
      )}
    </div>
  );
}
