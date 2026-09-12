/* Profile: what CV Glowup knows about you. Edits the master CV data every
   tailored CV is generated from, with the studio's structured form. Saving is
   explicit (this is the source of truth, not a draft): the bar at the bottom
   tracks unsaved changes, Save stores them, Discard reverts to what is saved. */
import { Check, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, ApiError, type MasterCVMeta } from "../api";
import { useI18n } from "../i18n";
import { useSession } from "../store";
import { CVForm } from "./Studio/ContentEditor";
import { isDirty, normalizeCv, pickInitialCv, type ProfileDraft } from "./profileState";

export default function Profile() {
  const { t } = useI18n();
  const me = useSession((s) => s.me);
  const setAuthOpen = useSession((s) => s.setAuthOpen);
  const [params, setParams] = useSearchParams();

  const [rows, setRows] = useState<MasterCVMeta[] | null>(null);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [draft, setDraft] = useState<ProfileDraft | null>(null);
  const [saving, setSaving] = useState(false);
  const [justSaved, setJustSaved] = useState(false);
  const [error, setError] = useState("");

  const authed = !!me?.authenticated;
  const active = rows?.find((r) => r.id === activeId) ?? null;
  const saved: ProfileDraft | null = active ? { name: active.name, data: normalizeCv(active.data) } : null;
  const dirty = !!draft && !!saved && isDirty(draft, saved);

  const open = (cv: MasterCVMeta) => {
    setActiveId(cv.id);
    setDraft({ name: cv.name, data: normalizeCv(cv.data) });
    setJustSaved(false);
    setError("");
    setParams({ cv: String(cv.id) }, { replace: true });
  };

  const edit = (patch: Partial<ProfileDraft>) => {
    setDraft((d) => (d ? { ...d, ...patch } : d));
    setJustSaved(false);
  };

  useEffect(() => {
    if (!authed) return;
    let cancelled = false;
    api
      .cvs()
      .then((list) => {
        if (cancelled) return;
        setRows(list);
        const initial = pickInitialCv(list, Number(params.get("cv")) || null);
        if (initial) open(initial);
      })
      .catch((e) => {
        if (cancelled) return;
        setRows([]);
        setError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      cancelled = true;
    };
    // Loads once per login: ?cv= is read on arrival, then kept in sync by open().
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authed]);

  // Closing or reloading the tab with unsaved edits asks first.
  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const save = async () => {
    if (!draft || !active) return;
    setSaving(true);
    setError("");
    try {
      const updated = await api.updateCv(active.id, { name: draft.name, data: draft.data });
      setRows((rs) => (rs ?? []).map((r) => (r.id === updated.id ? updated : r)));
      // The server trims and drops blank entries: show exactly what it stored.
      setDraft({ name: updated.name, data: normalizeCv(updated.data) });
      setJustSaved(true);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("profile.saveFailed"));
    } finally {
      setSaving(false);
    }
  };

  if (me && !authed) {
    return (
      <div className="grid min-h-[60vh] place-items-center px-6 text-center">
        <div>
          <p className="mb-4 text-text/70">{t("profile.loginFirst")}</p>
          <button onClick={() => setAuthOpen(true)} className="btn-flame rounded-lg px-5 py-2.5 text-sm font-semibold">
            {t("nav.login")}
          </button>
        </div>
      </div>
    );
  }

  if (!me || rows === null) {
    return (
      <div className="grid min-h-[60vh] place-items-center text-text/60">
        <Loader2 size={20} className="animate-spin" aria-label={t("common.loading")} />
      </div>
    );
  }

  const header = (
    <>
      <p className="eyebrow mb-2">{t("profile.eyebrow")}</p>
      <h1 className="font-sans text-3xl font-semibold tracking-tight">{t("profile.title")}</h1>
      <p className="mt-2 max-w-2xl text-[13.5px] leading-relaxed text-text/70">{t("profile.hint")}</p>
    </>
  );

  if (rows.length === 0) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-14">
        {header}
        <div className="mt-6 rounded-xl border border-dashed border-ink-600 glass-panel p-8 text-center">
          <p className="mx-auto mb-4 max-w-md text-[13.5px] leading-relaxed text-text/70">{t("profile.empty")}</p>
          <Link to="/settings" className="btn-flame inline-block rounded-lg px-4 py-2 text-[13px] font-semibold">
            {t("profile.addCv")}
          </Link>
          {error && <p role="alert" className="mt-3 text-[12.5px] text-danger">{error}</p>}
        </div>
      </div>
    );
  }

  if (!draft || !active) return null;

  return (
    <div className="mx-auto max-w-3xl px-6 pt-14">
      {header}
      <Link
        to="/settings"
        className="mt-3 inline-block text-[12.5px] text-primary/80 underline-offset-2 hover:text-flame-400 hover:underline"
      >
        {t("profile.manage")}
      </Link>

      {rows.length > 1 && (
        <div className="mt-6 flex flex-wrap gap-2" role="group" aria-label={t("profile.cvs")}>
          {rows.map((cv) => {
            const current = cv.id === activeId;
            const locked = dirty && !current;
            return (
              <button
                key={cv.id}
                onClick={() => open(cv)}
                disabled={locked}
                aria-pressed={current}
                title={locked ? t("profile.switchBlocked") : undefined}
                className={`rounded-lg border px-3.5 py-2.5 text-left text-[13px] transition-colors ${
                  current
                    ? "border-flame-500 bg-flame-950 text-text"
                    : "border-black/10 glass-panel text-text/70 hover:border-ink-600"
                } ${locked ? "cursor-not-allowed opacity-50" : ""}`}
              >
                <span className="block font-medium">{cv.name}</span>
                <span className="font-mono text-[11px] text-text/50">
                  {cv.data?.full_name || "·"}
                  {cv.is_default ? ` · ${t("profile.default")}` : ""}
                </span>
              </button>
            );
          })}
        </div>
      )}

      <section className="mt-6 overflow-hidden rounded-xl border border-black/10 glass-panel">
        <div className="border-b border-black/10 px-4 py-4">
          <label className="block">
            <span className="mb-1 block font-mono text-[10.5px] uppercase tracking-wider text-text/50">
              {t("profile.cvName")}
            </span>
            <input
              value={draft.name}
              maxLength={120}
              onChange={(e) => edit({ name: e.target.value })}
              className="w-full rounded-md border border-black/10 glass-panel px-2.5 py-2 text-[13px] focus:border-flame-500"
            />
          </label>
        </div>
        <CVForm data={draft.data} onChange={(data) => edit({ data })} />
      </section>

      <div className="sticky bottom-0 z-10 -mx-6 mt-6 border-t border-black/10 bg-[#FFFDFA]/90 px-6 py-3 backdrop-blur">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span
            aria-live="polite"
            className={`flex items-center gap-1.5 text-[12.5px] ${dirty ? "font-medium text-flame-700" : "text-text/60"}`}
          >
            {!dirty && justSaved && <Check size={13} className="text-ok-400" aria-hidden="true" />}
            {dirty ? t("profile.unsaved") : justSaved ? t("profile.saved") : t("profile.upToDate")}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                if (saved) setDraft(saved);
                setError("");
              }}
              disabled={!dirty || saving}
              className="rounded-md border border-black/10 px-3.5 py-2 text-[13px] text-text/70 hover:border-ink-600 hover:text-text disabled:opacity-40"
            >
              {t("profile.discard")}
            </button>
            <button
              onClick={() => void save()}
              disabled={!dirty || saving}
              className="btn-flame flex items-center gap-1.5 rounded-md px-4 py-2 text-[13px] font-semibold disabled:opacity-40 disabled:shadow-none"
            >
              {saving && <Loader2 size={13} className="animate-spin" aria-hidden="true" />}
              {t("profile.save")}
            </button>
          </div>
        </div>
        {error && <p role="alert" className="mt-2 text-[12.5px] text-danger">{error}</p>}
      </div>
    </div>
  );
}
