/* Pricing — three plans + the BYOK escape hatch, billing env-gated. */
import { Check, KeyRound } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api";
import { useI18n } from "../i18n";
import { useSession } from "../store";

const copy = {
  en: {
    eyebrow: "Pricing",
    title: "Pay for volume, not for quality.",
    sub: "Every plan produces the same recruiter-ready documents. Plans only change how many and how fast.",
    perMonth: "/month",
    free: "Free",
    current: "Current plan",
    upgrade: "Get {plan}",
    cancelAnytime: "Cancel anytime.",
    soon: "Online payment opens soon. Email us to upgrade early.",
    manage: "Manage subscription",
    login: "Log in to upgrade",
    start: "Start free",
    byokTitle: "Bring your own key",
    byokPrice: "Free, unlimited",
    byokBody: "Paste your own Gemini API key (Google gives one free at aistudio.google.com) and generate without daily limits, every template unlocked. The key never leaves your browser except to call Gemini for your own requests.",
    byokCta: "Set up my key",
    rows: {
      daily: "generations / day",
      parallel: "job postings in parallel",
      parallelOne: "job posting at a time",
      templates: "templates",
      editing: "Live editor, source & chat",
      letters: "CV + cover letter + outreach",
    },
  },
  fr: {
    eyebrow: "Tarifs",
    title: "Payez le volume, pas la qualité.",
    sub: "Tous les plans produisent les mêmes documents prêts pour les recruteurs. Seuls le volume et la vitesse changent.",
    perMonth: "/mois",
    free: "Gratuit",
    current: "Plan actuel",
    upgrade: "Passer à {plan}",
    cancelAnytime: "Annulable à tout moment.",
    soon: "Le paiement en ligne arrive. Écrivez-nous pour un accès anticipé.",
    manage: "Gérer l'abonnement",
    login: "Connectez-vous pour évoluer",
    start: "Commencer gratuitement",
    byokTitle: "Votre propre clé API",
    byokPrice: "Gratuit, illimité",
    byokBody: "Collez votre clé API Gemini (gratuite sur aistudio.google.com) et générez sans limite quotidienne, tous les modèles débloqués. La clé ne quitte votre navigateur que pour appeler Gemini.",
    byokCta: "Configurer ma clé",
    rows: {
      daily: "générations / jour",
      parallel: "offres en parallèle",
      parallelOne: "offre à la fois",
      templates: "modèles",
      editing: "Éditeur live, source & chat",
      letters: "CV + lettre + message",
    },
  },
  de: {
    eyebrow: "Preise",
    title: "Zahlen Sie für Volumen, nicht für Qualität.",
    sub: "Jeder Plan liefert dieselben recruiter-fertigen Dokumente. Pläne ändern nur, wie viele und wie schnell.",
    perMonth: "/Monat",
    free: "Kostenlos",
    current: "Aktueller Plan",
    upgrade: "{plan} holen",
    cancelAnytime: "Jederzeit kündbar.",
    soon: "Online-Zahlung startet bald. Schreiben Sie uns für ein frühes Upgrade.",
    manage: "Abo verwalten",
    login: "Zum Upgraden anmelden",
    start: "Kostenlos starten",
    byokTitle: "Eigener API-Schlüssel",
    byokPrice: "Kostenlos, unbegrenzt",
    byokBody: "Fügen Sie Ihren eigenen Gemini-API-Schlüssel ein (kostenlos bei aistudio.google.com) und generieren Sie ohne Tageslimits, alle Vorlagen freigeschaltet. Der Schlüssel verlässt Ihren Browser nur, um Gemini für Ihre eigenen Anfragen aufzurufen.",
    byokCta: "Schlüssel einrichten",
    rows: {
      daily: "Generierungen / Tag",
      parallel: "Stellen parallel",
      parallelOne: "Stelle auf einmal",
      templates: "Vorlagen",
      editing: "Live-Editor, Quelltext & Chat",
      letters: "Lebenslauf + Anschreiben + Nachricht",
    },
  },
};

export default function Pricing() {
  const { lang } = useI18n();
  const c = copy[lang];
  const me = useSession((s) => s.me);
  const config = useSession((s) => s.config);
  const setAuthOpen = useSession((s) => s.setAuthOpen);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const checkout = async (plan: string) => {
    if (!me?.authenticated) {
      setAuthOpen(true);
      return;
    }
    setBusy(plan);
    setError("");
    try {
      const { url } = await api.billingCheckout(plan);
      window.location.href = url;
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Checkout failed.");
    } finally {
      setBusy("");
    }
  };

  const plans = config?.plans ?? [];

  return (
    <div className="mx-auto max-w-6xl px-6 py-16">
      <p className="eyebrow mb-3">{c.eyebrow}</p>
      <h1 className="mb-3 font-sans text-3xl font-semibold tracking-tight sm:text-4xl">{c.title}</h1>
      <p className="mb-12 max-w-2xl text-[15px] text-text/70">{c.sub}</p>

      {error && <p className="mb-6 text-sm text-danger">{error}</p>}

      <div className="grid gap-5 md:grid-cols-3">
        {plans.map((p) => {
          const highlight = p.key === "plus";
          const isCurrent = me?.authenticated && me.plan === p.key;
          return (
            <div
              key={p.key}
              className={`card-lift rounded-2xl border p-6 ${
                highlight
                  ? "border-flame-500/60 bg-flame-950 shadow-lg shadow-flame-500/20"
                  : "border-black/10 glass-panel"
              }`}
            >
              <h2 className="mb-1 text-[15px] font-semibold">{p.label}</h2>
              <p className="mb-5">
                <span className="font-mono text-3xl font-semibold">
                  {p.price_eur === 0 ? c.free : `${p.price_eur}€`}
                </span>
                {p.price_eur > 0 && <span className="text-[13px] text-text/70">{c.perMonth}</span>}
              </p>
              <ul className="mb-6 space-y-2.5 text-[13.5px] text-text/70">
                <li className="flex gap-2"><Check size={15} className="mt-0.5 shrink-0 text-ok-400" />
                  <span><strong className="text-text">{p.daily >= 1000 ? "∞" : p.daily}</strong> {c.rows.daily}</span></li>
                <li className="flex gap-2"><Check size={15} className="mt-0.5 shrink-0 text-ok-400" />
                  <span><strong className="text-text">{p.parallel}</strong> {p.parallel === 1 ? c.rows.parallelOne : c.rows.parallel}</span></li>
                <li className="flex gap-2"><Check size={15} className="mt-0.5 shrink-0 text-ok-400" />
                  <span><strong className="text-text">{p.templates.length}</strong> {c.rows.templates}</span></li>
                <li className="flex gap-2"><Check size={15} className="mt-0.5 shrink-0 text-ok-400" />{c.rows.editing}</li>
                <li className="flex gap-2"><Check size={15} className="mt-0.5 shrink-0 text-ok-400" />{c.rows.letters}</li>
              </ul>
              {p.price_eur === 0 ? (
                <Link to="/studio" className="block rounded-lg border border-ink-600 py-2.5 text-center text-[14px] text-text/70 transition-colors hover:border-primary hover:text-text">
                  {isCurrent ? c.current : c.start}
                </Link>
              ) : isCurrent ? (
                <button
                  onClick={() => void api.billingPortal().then(({ url }) => (window.location.href = url)).catch(() => {})}
                  className="w-full rounded-lg border border-ink-600 py-2.5 text-[14px] text-text/70 hover:text-text"
                >
                  {c.manage}
                </button>
              ) : config?.billing_enabled ? (
                <>
                  <button
                    onClick={() => void checkout(p.key)}
                    disabled={busy !== ""}
                    className={`w-full rounded-lg py-2.5 text-[14px] font-semibold transition ${
                      highlight ? "btn-flame" : "border border-ink-600 text-text hover:border-primary"
                    } disabled:opacity-50`}
                  >
                    {busy === p.key
                      ? "…"
                      : me?.authenticated
                        ? c.upgrade.replace("{plan}", p.label)
                        : c.login}
                  </button>
                  <p className="mt-2 text-center text-xs text-text/50">{c.cancelAnytime}</p>
                </>
              ) : (
                <a
                  href="mailto:hello@cvglowup.com?subject=Upgrade"
                  className="block rounded-lg border border-ink-600 py-2.5 text-center text-[13px] text-text/70 hover:text-text"
                >
                  {c.soon}
                </a>
              )}
            </div>
          );
        })}
      </div>

      {/* BYOK */}
      <div className="card-lift mt-5 flex flex-col gap-4 rounded-2xl border border-ok-400/25 bg-ok-950 p-6 sm:flex-row sm:items-center">
        <KeyRound size={22} className="shrink-0 text-ok-400" />
        <div className="flex-1">
          <h2 className="text-[15px] font-semibold">
            {c.byokTitle} | <span className="font-mono text-ok-400">{c.byokPrice}</span>
          </h2>
          <p className="mt-1 max-w-3xl text-[13.5px] leading-relaxed text-text/70">{c.byokBody}</p>
        </div>
        <Link
          to="/settings"
          className="shrink-0 rounded-lg border border-ok-400/40 px-4 py-2.5 text-center text-[14px] font-medium text-ok-400 hover:bg-ok-400/10"
        >
          {c.byokCta}
        </Link>
      </div>
    </div>
  );
}
