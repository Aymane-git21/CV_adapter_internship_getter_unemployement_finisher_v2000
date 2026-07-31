/* Layout + compiler settings popover in the preview toolbar. First consumer
   of ctl.updateSettings; card-list options per the house pattern (no
   segments). The latex card is plan-gated (plus/pro) and onyx/CV-only. */
import { Lock, Settings2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../../api";
import { useI18n } from "../../i18n";
import { useSession } from "../../store";
import type { DocController } from "./useDocument";

const MODES = ["paged", "continuous"] as const;
const COMPILERS = ["typst", "latex"] as const;

export function SettingsPopover({ ctl }: { ctl: DocController }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const config = useSession((s) => s.config);
  const me = useSession((s) => s.me);
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
  const compiler = settings.compiler ?? "typst";
  const latexOffered = !!config?.latex_enabled && doc.kind === "cv";
  const latexPlanOk = !!me?.quota?.latex;
  const latexTemplateOk = settings.template === "onyx";

  const pickMode = (page_mode: string) => {
    if (sourceLocked || compiler === "latex" || page_mode === (settings.page_mode ?? "paged")) return;
    void ctl.updateSettings({ ...settings, page_mode });
  };

  const pickCompiler = (next: string) => {
    if (sourceLocked || next === compiler) return;
    if (next === "latex" && (!latexPlanOk || !latexTemplateOk)) return;
    const patch =
      next === "latex" ? { compiler: next, page_mode: "paged", show_photo: false } : { compiler: next };
    void ctl.updateSettings({ ...settings, ...patch });
    if (next === "latex") void api.latexWarmup().catch(() => undefined);
  };

  const card = (selected: boolean, disabled: boolean) =>
    `block w-full rounded-lg border px-3.5 py-2.5 text-left transition-colors ${
      selected ? "border-flame-500 bg-flame-950" : "border-black/10 glass-panel hover:border-ink-600"
    } ${disabled ? "cursor-not-allowed opacity-50" : ""}`;

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
        <div className="absolute left-0 top-full z-20 mt-2 w-64 rounded-lg border border-black/10 bg-[#FFFDFA] p-3 shadow-xl">
          <p className="eyebrow mb-3">{t("studio.pagemode.title")}</p>
          <div className="space-y-2">
            {MODES.map((m) => {
              const disabled = sourceLocked || (m === "continuous" && compiler === "latex");
              return (
                <button key={m} onClick={() => pickMode(m)} disabled={disabled}
                        className={card((settings.page_mode ?? "paged") === m, disabled)}>
                  <span className="block text-[13px] font-medium">{t(`studio.pagemode.${m}`)}</span>
                  <span className="block text-[11px] text-text/50">
                    {m === "continuous" && compiler === "latex"
                      ? t("studio.pagemode.latexonly")
                      : t(`studio.pagemode.${m}.desc`)}
                  </span>
                </button>
              );
            })}
          </div>

          {latexOffered && (
            <>
              <p className="eyebrow mb-3 mt-4">{t("studio.compiler.title")}</p>
              <div className="space-y-2">
                {COMPILERS.map((c) => {
                  const locked = c === "latex" && !latexPlanOk;
                  const wrongTemplate = c === "latex" && latexPlanOk && !latexTemplateOk;
                  const disabled = sourceLocked || locked || wrongTemplate;
                  return (
                    <button key={c} onClick={() => pickCompiler(c)} disabled={disabled}
                            className={card(compiler === c, disabled)}>
                      <span className="flex items-center gap-1.5 text-[13px] font-medium">
                        {t(`studio.compiler.${c}`)}
                        {locked && <Lock size={11} className="text-text/50" />}
                      </span>
                      <span className="block text-[11px] text-text/50">
                        {locked
                          ? t("studio.compiler.latex.locked")
                          : wrongTemplate
                            ? t("studio.compiler.latex.onyxonly")
                            : t(`studio.compiler.${c}.desc`)}
                      </span>
                    </button>
                  );
                })}
              </div>
            </>
          )}

          {sourceLocked && (
            <p className="mt-2 text-[11px] text-text/50">{t("studio.settings.sourcelock")}</p>
          )}
        </div>
      )}
    </div>
  );
}
