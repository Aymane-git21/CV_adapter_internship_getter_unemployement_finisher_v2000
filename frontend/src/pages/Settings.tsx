/* Settings — master CVs, BYOK key, plan, account. */
import { Check, FileUp, KeyRound, Loader2, Star, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, ApiError, byokStore, type MasterCVMeta } from "../api";
import { useI18n } from "../i18n";
import { useSession } from "../store";

const copy = {
  en: {
    title: "Settings",
    account: "Account",
    plan: "Plan",
    manageBilling: "Manage billing",
    cvs: "Master CVs",
    cvsHint: "The source of truth every tailored CV is built from. Keep one per career direction.",
    addPaste: "Add from text",
    addUpload: "Upload PDF",
    pasteTitle: "Paste your CV",
    name: "Name",
    create: "Create",
    default: "default",
    makeDefault: "Make default",
    byok: "Your Gemini API key",
    byokHint: "Optional. With your own key, generations are unlimited and free. The key stays in this browser (localStorage), is sent only with your own requests, and is never stored on our servers. Get one free at",
    byokPlaceholder: "AIza…",
    byokSave: "Validate & save",
    byokActive: "Key active | unlimited generations",
    byokRemove: "Remove key",
    loginFirst: "Log in to manage your settings.",
    feedback: "Found a bug? Tell us:",
  },
  fr: {
    title: "Réglages",
    account: "Compte",
    plan: "Plan",
    manageBilling: "Gérer la facturation",
    cvs: "CV de référence",
    cvsHint: "La source de vérité dont chaque CV adapté est dérivé. Gardez-en un par direction de carrière.",
    addPaste: "Ajouter depuis du texte",
    addUpload: "Importer un PDF",
    pasteTitle: "Collez votre CV",
    name: "Nom",
    create: "Créer",
    default: "défaut",
    makeDefault: "Définir par défaut",
    byok: "Votre clé API Gemini",
    byokHint: "Optionnel. Avec votre propre clé, les générations sont illimitées et gratuites. La clé reste dans ce navigateur (localStorage), n'est envoyée qu'avec vos propres requêtes, et n'est jamais stockée sur nos serveurs. Clé gratuite sur",
    byokPlaceholder: "AIza…",
    byokSave: "Valider & enregistrer",
    byokActive: "Clé active | générations illimitées",
    byokRemove: "Retirer la clé",
    loginFirst: "Connectez-vous pour gérer vos réglages.",
    feedback: "Un bug ? Dites-le nous :",
  },
  de: {
    title: "Einstellungen",
    account: "Konto",
    plan: "Plan",
    manageBilling: "Abrechnung verwalten",
    cvs: "Master-Lebensläufe",
    cvsHint: "Die Quelle der Wahrheit, aus der jeder angepasste Lebenslauf entsteht. Behalten Sie einen pro Karriererichtung.",
    addPaste: "Aus Text hinzufügen",
    addUpload: "PDF hochladen",
    pasteTitle: "Fügen Sie Ihren Lebenslauf ein",
    name: "Name",
    create: "Erstellen",
    default: "Standard",
    makeDefault: "Als Standard festlegen",
    byok: "Ihr Gemini-API-Schlüssel",
    byokHint: "Optional. Mit Ihrem eigenen Schlüssel sind Generierungen unbegrenzt und kostenlos. Der Schlüssel bleibt in diesem Browser (localStorage), wird nur mit Ihren eigenen Anfragen gesendet und nie auf unseren Servern gespeichert. Kostenlos erhältlich bei",
    byokPlaceholder: "AIza…",
    byokSave: "Prüfen & speichern",
    byokActive: "Schlüssel aktiv | unbegrenzte Generierungen",
    byokRemove: "Schlüssel entfernen",
    loginFirst: "Melden Sie sich an, um Ihre Einstellungen zu verwalten.",
    feedback: "Einen Fehler gefunden? Sagen Sie es uns:",
  },
};

function ByokCard() {
  const { lang } = useI18n();
  const c = copy[lang];
  const [key, setKey] = useState("");
  const [active, setActive] = useState(!!byokStore.get());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const save = async () => {
    setBusy(true);
    setError("");
    try {
      await api.validateByok(key.trim());
      byokStore.set(key.trim());
      setActive(true);
      setKey("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Validation failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-xl border border-black/10 glass-panel p-6">
      <h2 className="mb-1 flex items-center gap-2 text-[15px] font-semibold">
        <KeyRound size={15} className="text-ok-400" /> {c.byok}
      </h2>
      <p className="mb-4 text-[13px] leading-relaxed text-text/70">
        {c.byokHint}{" "}
        <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer" className="text-primary/80 underline-offset-2 hover:underline">
          aistudio.google.com
        </a>.
      </p>
      {active ? (
        <div className="flex flex-wrap items-center gap-4">
          <span className="flex items-center gap-2 rounded-full border border-ok-400/30 bg-ok-950 px-3 py-1.5 font-mono text-[12px] text-ok-400">
            <Check size={13} /> {c.byokActive}
          </span>
          <button
            onClick={() => { byokStore.set(null); setActive(false); }}
            className="text-[13px] text-text/70 hover:text-danger"
          >
            {c.byokRemove}
          </button>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          <input
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder={c.byokPlaceholder}
            className="w-72 max-w-full rounded-md border border-black/10 bg-transparent px-3 py-2 font-mono text-[13px] placeholder:text-text/50 focus:border-flame-500"
          />
          <button
            onClick={() => void save()}
            disabled={busy || key.trim().length < 10}
            className="rounded-md bg-primary px-4 py-2 text-[13px] font-medium text-white hover:bg-primary/90 disabled:opacity-40"
          >
            {busy ? "…" : c.byokSave}
          </button>
        </div>
      )}
      {error && <p className="mt-3 text-[13px] text-danger">{error}</p>}
    </section>
  );
}

function MasterCVs() {
  const { lang } = useI18n();
  const c = copy[lang];
  const [rows, setRows] = useState<MasterCVMeta[]>([]);
  const [pasteOpen, setPasteOpen] = useState(false);
  const [name, setName] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const reload = () => void api.cvs().then(setRows).catch(() => {});
  useEffect(reload, []);

  const createFromText = async () => {
    setBusy(true);
    setError("");
    try {
      await api.createCv(name || "My CV", text);
      setPasteOpen(false);
      setName("");
      setText("");
      reload();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Creation failed.");
    } finally {
      setBusy(false);
    }
  };

  const upload = async (f: File | undefined) => {
    if (!f) return;
    setBusy(true);
    setError("");
    try {
      await api.uploadCvPdf(f, f.name.replace(/\.pdf$/i, ""));
      reload();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Upload failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-xl border border-black/10 glass-panel p-6">
      <h2 className="mb-1 text-[15px] font-semibold">{c.cvs}</h2>
      <p className="mb-4 text-[13px] text-text/70">{c.cvsHint}</p>

      <div className="mb-4 space-y-2">
        {rows.map((cv) => (
          <div key={cv.id} className="flex items-center gap-3 rounded-lg border border-black/10 glass-panel px-3.5 py-2.5">
            <div className="min-w-0 flex-1">
              <p className="truncate text-[13.5px] font-medium">
                {cv.name}
                {cv.is_default && (
                  <span className="ml-2 rounded-full bg-flame-950 px-2 py-0.5 font-mono text-[10px] text-primary/80">
                    {c.default}
                  </span>
                )}
              </p>
              <p className="font-mono text-[11px] text-text/50">{cv.data?.full_name ?? "·"}</p>
            </div>
            {!cv.is_default && (
              <button
                onClick={() => void api.setDefaultCv(cv.id).then(reload)}
                className="grid size-7 place-items-center rounded text-text/50 hover:glass-panel hover:text-text"
                title={c.makeDefault}
              >
                <Star size={13} />
              </button>
            )}
            <button
              onClick={() => void api.deleteCv(cv.id).then(reload)}
              className="grid size-7 place-items-center rounded text-text/50 hover:glass-panel hover:text-danger"
              title="Delete"
            >
              <Trash2 size={13} />
            </button>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setPasteOpen((v) => !v)}
          className="rounded-md border border-black/10 px-3.5 py-2 text-[13px] text-text/70 hover:border-ink-600 hover:text-text"
        >
          {c.addPaste}
        </button>
        <input ref={fileRef} type="file" accept="application/pdf" className="hidden" onChange={(e) => void upload(e.target.files?.[0])} />
        <button
          onClick={() => fileRef.current?.click()}
          disabled={busy}
          className="flex items-center gap-1.5 rounded-md border border-black/10 px-3.5 py-2 text-[13px] text-text/70 hover:border-ink-600 hover:text-text disabled:opacity-50"
        >
          {busy ? <Loader2 size={13} className="animate-spin" /> : <FileUp size={13} />} {c.addUpload}
        </button>
      </div>

      {pasteOpen && (
        <div className="mt-4 space-y-2 rounded-lg border border-black/10 p-4">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={c.name}
            className="w-full rounded-md border border-black/10 bg-transparent px-3 py-2 text-[13px] placeholder:text-text/50 focus:border-flame-500"
          />
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={7}
            placeholder={c.pasteTitle}
            className="w-full rounded-md border border-black/10 bg-transparent px-3 py-2 font-mono text-[12px] placeholder:font-sans placeholder:text-text/50 focus:border-flame-500"
          />
          <button
            onClick={() => void createFromText()}
            disabled={busy || text.trim().length < 60}
            className="rounded-md bg-primary px-4 py-2 text-[13px] font-medium text-white hover:bg-primary/90 disabled:opacity-40"
          >
            {busy ? "…" : c.create}
          </button>
        </div>
      )}
      {error && <p className="mt-3 text-[13px] text-danger">{error}</p>}
    </section>
  );
}

export default function Settings() {
  const { lang, t } = useI18n();
  const c = copy[lang];
  const me = useSession((s) => s.me);
  const config = useSession((s) => s.config);
  const setAuthOpen = useSession((s) => s.setAuthOpen);

  if (me && !me.authenticated) {
    return (
      <div className="grid min-h-[60vh] place-items-center px-6 text-center">
        <div>
          <p className="mb-4 text-text/70">{c.loginFirst}</p>
          <button onClick={() => setAuthOpen(true)} className="btn-flame rounded-lg px-5 py-2.5 text-sm font-semibold">
            {t("nav.login")}
          </button>
          <div className="mx-auto mt-10 max-w-xl text-left">
            <ByokCard />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5 px-6 py-14">
      <h1 className="font-sans text-3xl font-semibold tracking-tight">{c.title}</h1>

      <section className="rounded-xl border border-black/10 glass-panel p-6">
        <h2 className="mb-3 text-[15px] font-semibold">{c.account}</h2>
        <div className="flex flex-wrap items-center gap-x-8 gap-y-2 text-[13.5px]">
          <span className="text-text/70">{me?.email}</span>
          <span className="font-mono text-[12px]">
            {c.plan}: <strong className="uppercase text-primary/80">{me?.plan}</strong>
          </span>
          {config?.billing_enabled && me?.plan !== "free" && (
            <button
              onClick={() => void api.billingPortal().then(({ url }) => (window.location.href = url)).catch(() => {})}
              className="text-[13px] text-text/70 underline-offset-2 hover:text-text hover:underline"
            >
              {c.manageBilling}
            </button>
          )}
        </div>
      </section>

      <MasterCVs />
      <ByokCard />

      <p className="pt-2 text-[12.5px] text-text/50">
        {c.feedback}{" "}
        <a href="mailto:hello@cvglowup.com" className="text-primary/80 underline-offset-2 hover:underline">
          hello@cvglowup.com
        </a>
      </p>
    </div>
  );
}
