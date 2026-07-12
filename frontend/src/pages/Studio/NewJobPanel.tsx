/* Launch panel: multiple job descriptions in parallel, CV source, look & feel. */
import { Camera, FileUp, Loader2, Lock, Plus, Trash2, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError, byokStore, type MasterCVMeta } from "../../api";
import { useI18n } from "../../i18n";
import { useSession, useStudio } from "../../store";

const ACCENTS = ["#0F62FE", "#1C3B5A", "#0E8A66", "#7C3AED", "#C2551B", "#B42318", "#101828"];

async function squareCrop(file: File, size = 512): Promise<Blob> {
  const img = await createImageBitmap(file);
  const side = Math.min(img.width, img.height);
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  ctx.drawImage(img, (img.width - side) / 2, (img.height - side) / 2, side, side, 0, 0, size, size);
  return new Promise((resolve) => canvas.toBlob((b) => resolve(b!), "image/jpeg", 0.88));
}

export function NewJobPanel({ onLaunched }: { onLaunched: () => void }) {
  const { t, lang } = useI18n();
  const me = useSession((s) => s.me);
  const config = useSession((s) => s.config);
  const refreshMe = useSession((s) => s.refreshMe);
  const setAuthOpen = useSession((s) => s.setAuthOpen);
  const openJobs = useStudio((s) => s.openJobs);

  const authed = !!me?.authenticated;
  const byok = !!byokStore.get();
  const maxParallel = byok ? 3 : (me?.quota.parallel ?? 1);
  const allowedTemplates = byok ? (config?.all_templates ?? []) : (me?.quota.templates ?? ["onyx"]);

  const [jds, setJds] = useState<string[]>([""]);
  const [cvMode, setCvMode] = useState<"saved" | "paste" | "upload">(authed ? "saved" : "paste");
  const [savedCvs, setSavedCvs] = useState<MasterCVMeta[]>([]);
  const [savedCvId, setSavedCvId] = useState<number | null>(null);
  const [cvText, setCvText] = useState("");
  const [saveMaster, setSaveMaster] = useState(true);
  const [uploadedCv, setUploadedCv] = useState<MasterCVMeta | null>(null);
  const [uploading, setUploading] = useState(false);

  const [docLang, setDocLang] = useState(lang);
  const [template, setTemplate] = useState("onyx");
  const [accent, setAccent] = useState("#0F62FE");
  const [photoId, setPhotoId] = useState<string | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const photoRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!authed) return;
    void api.cvs().then((rows) => {
      setSavedCvs(rows);
      const def = rows.find((r) => r.is_default) ?? rows[0];
      if (def) setSavedCvId(def.id);
      else setCvMode("paste");
    }).catch(() => setCvMode("paste"));
  }, [authed]);

  const canUploadPdf = config?.ai_mode === "gemini" || byok;

  const setJd = (i: number, v: string) => setJds((xs) => xs.map((x, j) => (j === i ? v : x)));
  const removeJd = (i: number) => setJds((xs) => xs.filter((_, j) => j !== i));

  const ready = useMemo(() => {
    const filled = jds.filter((j) => j.trim().length >= 80);
    if (filled.length === 0 || filled.length !== jds.filter((j) => j.trim()).length) return false;
    if (cvMode === "saved") return savedCvId != null;
    if (cvMode === "paste") return cvText.trim().length > 60;
    return uploadedCv != null;
  }, [jds, cvMode, savedCvId, cvText, uploadedCv]);

  const launch = async () => {
    setBusy(true);
    setError("");
    try {
      const body = {
        job_descriptions: jds.filter((j) => j.trim()),
        master_cv_id: cvMode === "saved" ? savedCvId : cvMode === "upload" ? (uploadedCv?.id ?? null) : null,
        cv_text: cvMode === "paste" ? cvText : null,
        language: docLang,
        template,
        accent,
        show_photo: !!photoId,
        photo_id: photoId,
        save_master: authed && cvMode === "paste" && saveMaster,
      };
      const res = await api.generate(body);
      openJobs(res.jobs);
      void refreshMe();
      onLaunched();
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.message);
        if (e.code === "guest_limit" && !authed) setAuthOpen(true);
      } else setError("Something went wrong — try again.");
    } finally {
      setBusy(false);
    }
  };

  const onPdfPick = async (f: File | undefined) => {
    if (!f) return;
    setUploading(true);
    setError("");
    try {
      const cv = await api.uploadCvPdf(f, f.name.replace(/\.pdf$/i, ""));
      setUploadedCv(cv);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  };

  const onPhotoPick = async (f: File | undefined) => {
    if (!f) return;
    try {
      const blob = await squareCrop(f);
      const { id } = await api.uploadPhoto(blob);
      setPhotoId(id);
      setPhotoPreview(URL.createObjectURL(blob));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Photo upload failed.");
    }
  };

  const seg = (active: boolean) =>
    `rounded-md px-3 py-1.5 text-[13px] transition-colors ${
      active ? "bg-ink-700 text-text" : "text-text/70 hover:text-text"
    }`;

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto grid max-w-5xl gap-8 p-6 lg:grid-cols-[1fr_minmax(260px,320px)] lg:p-10">
        {/* ── left: the job descriptions ── */}
        <div>
          <p className="eyebrow mb-2">{t("studio.newJob")}</p>
          <h1 className="mb-6 font-sans text-2xl font-semibold tracking-tight">
            {jds.length > 1 ? `${jds.length} ${t("studio.jd.count")}` : t("nav.start")}
          </h1>

          <div className="space-y-3">
            {jds.map((jd, i) => (
              <div key={i} className="relative">
                <textarea
                  value={jd}
                  onChange={(e) => setJd(i, e.target.value)}
                  placeholder={t("studio.jd.placeholder")}
                  rows={jds.length > 1 ? 5 : 9}
                  className="w-full resize-y rounded-lg border border-black/10 glass-panel p-3.5 text-sm leading-relaxed placeholder:text-text/50 focus:border-flame-500"
                />
                {jds.length > 1 && (
                  <button
                    onClick={() => removeJd(i)}
                    className="absolute right-2 top-2 rounded p-1 text-text/50 hover:bg-ink-700 hover:text-text"
                    aria-label={t("ed.remove")}
                  >
                    <X size={14} />
                  </button>
                )}
              </div>
            ))}
          </div>

          {jds.length < maxParallel && (
            <button
              onClick={() => setJds((xs) => [...xs, ""])}
              className="mt-3 flex items-center gap-1.5 text-[13px] text-primary/80 hover:text-flame-400"
            >
              <Plus size={14} /> {t("studio.jd.add")}
              <span className="font-mono text-[11px] text-text/50">({jds.length}/{maxParallel})</span>
            </button>
          )}

          {/* ── CV source ── */}
          <div className="mt-8">
            <p className="eyebrow mb-3">{t("studio.cv.source")}</p>
            <div className="mb-3 inline-flex gap-1 rounded-lg border border-black/10 glass-panel p-1">
              {authed && (
                <button className={seg(cvMode === "saved")} onClick={() => setCvMode("saved")}>
                  {t("studio.cv.saved")}
                </button>
              )}
              <button className={seg(cvMode === "paste")} onClick={() => setCvMode("paste")}>
                {t("studio.cv.paste")}
              </button>
              <button
                className={`${seg(cvMode === "upload")} ${!canUploadPdf ? "opacity-40" : ""}`}
                onClick={() => {
                  if (!canUploadPdf) return;
                  // /api/cvs/upload stores a MasterCV, which needs an account.
                  if (!authed) { setAuthOpen(true); return; }
                  setCvMode("upload");
                }}
                title={!canUploadPdf ? "PDF parsing needs the AI service" : !authed ? "Sign in to upload a PDF" : ""}
              >
                {!authed && canUploadPdf && <Lock size={11} className="mr-1 inline-block opacity-60" />}
                {t("studio.cv.upload")}
              </button>
            </div>

            {cvMode === "saved" && (
              <div className="flex flex-wrap gap-2">
                {savedCvs.map((cv) => (
                  <button
                    key={cv.id}
                    onClick={() => setSavedCvId(cv.id)}
                    className={`rounded-lg border px-3.5 py-2.5 text-left text-[13px] transition-colors ${
                      savedCvId === cv.id
                        ? "border-flame-500 bg-flame-950 text-text"
                        : "border-black/10 glass-panel text-text/70 hover:border-ink-600"
                    }`}
                  >
                    <span className="block font-medium">{cv.name}</span>
                    <span className="font-mono text-[11px] text-text/50">
                      {cv.data?.full_name ?? "—"}{cv.is_default ? " · default" : ""}
                    </span>
                  </button>
                ))}
              </div>
            )}

            {cvMode === "paste" && (
              <>
                <textarea
                  value={cvText}
                  onChange={(e) => setCvText(e.target.value)}
                  placeholder={t("studio.cv.paste.placeholder")}
                  rows={7}
                  className="w-full resize-y rounded-lg border border-black/10 glass-panel p-3.5 font-mono text-[12.5px] leading-relaxed placeholder:font-sans placeholder:text-text/50 focus:border-flame-500"
                />
                {authed && (
                  <label className="mt-2 flex items-center gap-2 text-[13px] text-text/70">
                    <input
                      type="checkbox"
                      checked={saveMaster}
                      onChange={(e) => setSaveMaster(e.target.checked)}
                      className="size-3.5 accent-flame-500"
                    />
                    {t("studio.cv.save")}
                  </label>
                )}
              </>
            )}

            {cvMode === "upload" && (
              <div>
                <input
                  ref={fileRef}
                  type="file"
                  accept="application/pdf"
                  className="hidden"
                  onChange={(e) => void onPdfPick(e.target.files?.[0])}
                />
                <button
                  onClick={() => fileRef.current?.click()}
                  disabled={uploading}
                  className="flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-ink-600 glass-panel px-4 py-7 text-sm text-text/70 transition-colors hover:border-flame-500 hover:text-text"
                >
                  {uploading ? <Loader2 size={16} className="animate-spin" /> : <FileUp size={16} />}
                  {uploadedCv ? `${uploadedCv.name} — ${uploadedCv.data?.full_name ?? "parsed"}` : "PDF, max 8 MB"}
                </button>
              </div>
            )}
          </div>
        </div>

        {/* ── right: look & launch ── */}
        <aside className="space-y-6 lg:pt-12">
          <div>
            <p className="eyebrow mb-3">{t("studio.language")}</p>
            <div className="inline-flex gap-1 rounded-lg border border-black/10 glass-panel p-1">
              {(["en", "fr", "de"] as const).map((l) => (
                <button key={l} className={seg(docLang === l)} onClick={() => setDocLang(l)}>
                  {{ en: "English", fr: "Français", de: "Deutsch" }[l]}
                </button>
              ))}
            </div>
          </div>

          <div>
            <p className="eyebrow mb-3">{t("studio.template")}</p>
            <div className="space-y-2">
              {(config?.templates ?? []).map((tpl) => {
                const locked = !allowedTemplates.includes(tpl.id);
                return (
                  <button
                    key={tpl.id}
                    disabled={locked}
                    onClick={() => { setTemplate(tpl.id); setAccent(tpl.default_accent); }}
                    className={`flex w-full items-center justify-between rounded-lg border px-3.5 py-2.5 text-left transition-colors ${
                      template === tpl.id
                        ? "border-flame-500 bg-flame-950"
                        : "border-black/10 glass-panel hover:border-ink-600"
                    } ${locked ? "opacity-45" : ""}`}
                  >
                    <span>
                      <span className="block text-[13px] font-medium">{tpl.label}</span>
                      <span className="font-mono text-[11px] text-text/50">{tpl.vibe}</span>
                    </span>
                    {locked ? <Lock size={13} className="text-text/50" /> : (
                      <span className="size-3.5 rounded-full" style={{ background: tpl.default_accent }} />
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <p className="eyebrow mb-3">{t("studio.accent")}</p>
            <div className="flex items-center gap-2">
              {ACCENTS.map((c) => (
                <button
                  key={c}
                  onClick={() => setAccent(c)}
                  aria-label={`Accent ${c}`}
                  className={`size-6 rounded-full transition-transform hover:scale-110 ${
                    accent === c ? "ring-2 ring-fg ring-offset-2 ring-offset-ink-950" : ""
                  }`}
                  style={{ background: c }}
                />
              ))}
              <input
                type="color"
                value={accent}
                onChange={(e) => setAccent(e.target.value)}
                className="size-6 cursor-pointer rounded-full border-0 bg-transparent p-0"
                aria-label="Custom accent"
              />
            </div>
          </div>

          <div>
            <p className="eyebrow mb-3">{t("studio.photo")}</p>
            <input
              ref={photoRef}
              type="file"
              accept="image/jpeg,image/png"
              className="hidden"
              onChange={(e) => void onPhotoPick(e.target.files?.[0])}
            />
            {photoPreview ? (
              <div className="flex items-center gap-3">
                <img src={photoPreview} alt="" className="size-12 rounded-full object-cover" />
                <button
                  onClick={() => { setPhotoId(null); setPhotoPreview(null); }}
                  className="flex items-center gap-1.5 text-[13px] text-text/70 hover:text-danger"
                >
                  <Trash2 size={13} /> {t("studio.photo.remove")}
                </button>
              </div>
            ) : (
              <button
                onClick={() => photoRef.current?.click()}
                className="flex items-center gap-2 rounded-lg border border-black/10 glass-panel px-3.5 py-2.5 text-[13px] text-text/70 transition-colors hover:border-ink-600 hover:text-text"
              >
                <Camera size={14} /> {t("studio.photo.add")}
              </button>
            )}
          </div>

          {error && (
            <p className="rounded-lg border border-signal-500/30 bg-signal-950 p-3 text-[13px] text-danger">
              {error}
            </p>
          )}

          <button
            onClick={() => void launch()}
            disabled={!ready || busy}
            className="btn-flame flex w-full items-center justify-center gap-2 rounded-lg py-3 text-sm font-semibold disabled:opacity-40 disabled:shadow-none"
          >
            {busy && <Loader2 size={15} className="animate-spin" />}
            {busy ? t("studio.generating") : t("studio.generate")}
            {jds.filter((j) => j.trim()).length > 1 && !busy && (
              <span className="font-mono text-xs opacity-80">×{jds.filter((j) => j.trim()).length}</span>
            )}
          </button>
        </aside>
      </div>
    </div>
  );
}
