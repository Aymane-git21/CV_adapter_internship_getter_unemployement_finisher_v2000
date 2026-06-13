/* Landing — "Your CV has 7 seconds." The hero is the product itself: a real
   compiled document being scanned the way a recruiter scans it. */
import { motion, useReducedMotion } from "motion/react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Columns2, FileSearch, Gauge, KeyRound, MessageSquareText, Timer,
} from "lucide-react";
import heroCv from "../assets/hero_cv.jpg";
import { useI18n } from "../i18n";
import { useSession } from "../store";

const copy = {
  en: {
    eyebrow: "Recruiters decide fast",
    title1: "Your CV has",
    title2: "7 seconds.",
    title3: "Make every one count.",
    sub: "Paste a job posting. CV Glowup rewrites your CV and cover letter around it, typesets them in milliseconds, and shows you the recruiter-ready page as you edit — forms, raw source, or chat.",
    ctaPrimary: "Tailor my CV — free",
    ctaSecondary: "See pricing",
    ctaNote: "First generation free. No account, no card.",
    statHuman: "average first look a recruiter gives a CV",
    statAts: "of large companies screen CVs with software first",
    statTypst: "to typeset your page — live, as you type",
    howEyebrow: "How it works",
    how: [
      ["Paste the job posting", "One or several — each runs in parallel, in its own tab."],
      ["Watch the documents write themselves", "CV, cover letter and outreach message, tailored to the posting and typeset live on a real A4 page."],
      ["Edit anything, three ways", "Structured forms, the raw Typst source, or just tell the assistant what to change."],
    ],
    featEyebrow: "Built for the application grind",
    features: [
      ["Parallel applications", "Queue up to ten postings at once. Every job gets its own tab, its own CV, its own letter.", Columns2],
      ["A match score that doesn't lie", "Keywords are extracted once, then both versions are measured against the same list. The before/after delta is computed, not generated.", FileSearch],
      ["Millisecond typesetting", "A Typst engine replaces LaTeX: the page re-renders in ~0.2 s on every edit. No queues, no waiting for PDFs.", Gauge],
      ["Your key, your rules", "Plug in your own Gemini API key and generate without limits, free. The key stays in your browser — we never store it.", KeyRound],
    ],
    languages: "English & French — site, documents and lettres de motivation.",
    faqEyebrow: "Questions",
    faq: [
      ["Does it invent experience I don't have?", "No. The generator is instructed to rephrase, reorder and emphasize — never to fabricate employers, dates or numbers. Everything stays editable, and the source of truth is your master CV."],
      ["What's the catch with the free plan?", "Three generations a day, two templates, one job at a time. Paid plans raise the limits; your own API key removes them entirely."],
      ["Can I edit the result?", "Everything. Structured forms for quick changes, the full Typst source for control, and a chat assistant for \"make it punchier\". The page re-typesets live."],
      ["Why Typst instead of LaTeX?", "Same typographic quality, a thousandth of the wait. Compiles take milliseconds, so the preview follows your keystrokes."],
      ["What about my data?", "Documents live in your account, deletable anytime. Guest documents are reachable only by their secret link. Bring-your-own keys are never stored server-side."],
    ],
    footerBlurb: "CV Glowup typesets careers.",
  },
  fr: {
    eyebrow: "Les recruteurs décident vite",
    title1: "Votre CV a",
    title2: "7 secondes.",
    title3: "Faites-les compter.",
    sub: "Collez une offre d'emploi. CV Glowup réécrit votre CV et votre lettre de motivation pour cette offre, les compose en quelques millisecondes, et vous montre la page finale pendant que vous éditez — formulaires, source, ou chat.",
    ctaPrimary: "Adapter mon CV — gratuit",
    ctaSecondary: "Voir les tarifs",
    ctaNote: "Première génération gratuite. Sans compte, sans carte.",
    statHuman: "de premier regard d'un recruteur sur un CV",
    statAts: "des grandes entreprises filtrent les CV par logiciel",
    statTypst: "pour composer votre page — en direct",
    howEyebrow: "Comment ça marche",
    how: [
      ["Collez l'offre d'emploi", "Une ou plusieurs — chacune tourne en parallèle, dans son propre onglet."],
      ["Les documents s'écrivent sous vos yeux", "CV, lettre de motivation et message d'approche, adaptés à l'offre et composés en direct sur une vraie page A4."],
      ["Éditez tout, de trois façons", "Formulaires structurés, source Typst, ou demandez simplement à l'assistant."],
    ],
    featEyebrow: "Conçu pour la chasse aux offres",
    features: [
      ["Candidatures en parallèle", "Jusqu'à dix offres à la fois. Chaque poste a son onglet, son CV, sa lettre.", Columns2],
      ["Un score qui ne ment pas", "Les mots-clés sont extraits une fois, puis les deux versions sont mesurées contre la même liste. Le delta avant/après est calculé, pas généré.", FileSearch],
      ["Composition en millisecondes", "Un moteur Typst remplace LaTeX : la page se recompose en ~0,2 s à chaque édition. Pas de file d'attente.", Gauge],
      ["Votre clé, vos règles", "Branchez votre propre clé API Gemini et générez sans limite, gratuitement. La clé reste dans votre navigateur.", KeyRound],
    ],
    languages: "Français & anglais — site, CV et lettres de motivation.",
    faqEyebrow: "Questions",
    faq: [
      ["Est-ce que ça invente des expériences ?", "Non. Le générateur reformule, réordonne et met en valeur — jamais il n'invente employeurs, dates ou chiffres. Tout reste éditable, et votre CV de référence fait foi."],
      ["Le piège du plan gratuit ?", "Trois générations par jour, deux modèles, une offre à la fois. Les plans payants montent les limites ; votre propre clé API les supprime."],
      ["Je peux éditer le résultat ?", "Tout. Formulaires pour les retouches rapides, source Typst complète pour le contrôle, et un assistant pour « rends ça plus percutant ». La page se recompose en direct."],
      ["Pourquoi Typst plutôt que LaTeX ?", "La même qualité typographique, mille fois moins d'attente. La compilation prend des millisecondes, l'aperçu suit vos frappes."],
      ["Et mes données ?", "Vos documents vivent dans votre compte, supprimables à tout moment. Les clés API personnelles ne sont jamais stockées côté serveur."],
    ],
    footerBlurb: "CV Glowup compose des carrières.",
  },
};

function ScanOverlay() {
  const reduced = useReducedMotion();
  const [count, setCount] = useState(7.0);
  useEffect(() => {
    if (reduced) return;
    const started = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const elapsed = ((now - started) / 1000) % 9; // 7s countdown + 2s hold
      setCount(Math.max(0, 7 - elapsed));
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [reduced]);

  return (
    <>
      {/* countdown chip */}
      <div className="absolute -left-3 -top-3 z-10 flex items-center gap-1.5 rounded-lg border border-signal-500/40 bg-ink-950/95 px-2.5 py-1.5 shadow-xl sm:-left-5 sm:-top-5">
        <Timer size={13} className="text-signal-400" />
        <span className="font-mono text-[13px] font-medium tabular-nums text-signal-400">
          {count.toFixed(1)}s
        </span>
      </div>
      {/* scan line */}
      {!reduced && (
        <motion.div
          className="pointer-events-none absolute inset-x-0 z-10 h-20"
          style={{
            background:
              "linear-gradient(to bottom, transparent, rgba(61,127,255,0.14) 70%, rgba(61,127,255,0.5))",
            borderBottom: "1.5px solid rgba(61,127,255,0.8)",
          }}
          initial={{ top: "-10%" }}
          animate={{ top: ["−10%", "92%"] }}
          transition={{ duration: 7, repeat: Infinity, repeatDelay: 2, ease: "linear" }}
        />
      )}
    </>
  );
}

export default function Landing() {
  const { lang, t } = useI18n();
  const me = useSession((s) => s.me);
  const c = copy[lang];

  return (
    <div>
      {/* ── hero ─────────────────────────────────────────────────────────── */}
      <section className="relative overflow-hidden border-b border-ink-800">
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(900px 500px at 75% 30%, rgba(61,127,255,0.09), transparent 65%)",
          }}
        />
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-6 py-16 lg:grid-cols-[1.05fr_0.95fr] lg:py-24">
          <div>
            <motion.p
              className="eyebrow mb-4 text-signal-400"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
            >
              {c.eyebrow}
            </motion.p>
            <motion.h1
              className="mb-6 font-serif text-[2.6rem] font-semibold leading-[1.08] tracking-tight sm:text-[3.4rem]"
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.06 }}
            >
              {c.title1}{" "}
              <span className="whitespace-nowrap text-signal-400">{c.title2}</span>
              <br />
              <span className="text-fg">{c.title3}</span>
            </motion.h1>
            <motion.p
              className="mb-8 max-w-xl text-[15.5px] leading-relaxed text-fg-dim"
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.12 }}
            >
              {c.sub}
            </motion.p>
            <motion.div
              className="flex flex-wrap items-center gap-4"
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.18 }}
            >
              <Link
                to="/studio"
                className="rounded-lg bg-blue-500 px-6 py-3 text-[15px] font-semibold text-white shadow-[0_0_40px_-8px] shadow-blue-500/70 transition hover:bg-blue-400"
              >
                {c.ctaPrimary}
              </Link>
              <Link to="/pricing" className="text-[14px] text-fg-dim underline-offset-4 hover:text-fg hover:underline">
                {c.ctaSecondary}
              </Link>
            </motion.div>
            <p className="mt-4 font-mono text-[11.5px] text-fg-faint">{c.ctaNote}</p>
          </div>

          {/* the paper in the dark */}
          <motion.div
            className="relative mx-auto w-full max-w-[420px]"
            initial={{ opacity: 0, y: 24, rotate: 0.8 }}
            animate={{ opacity: 1, y: 0, rotate: 0.8 }}
            transition={{ delay: 0.15, duration: 0.7 }}
          >
            <ScanOverlay />
            <div className="sheet overflow-hidden">
              <img src={heroCv} alt="A tailored CV, typeset by CV Glowup" className="block w-full" />
            </div>
          </motion.div>
        </div>
      </section>

      {/* ── stats strip ──────────────────────────────────────────────────── */}
      <section className="border-b border-ink-800 bg-ink-900/50">
        <div className="mx-auto grid max-w-6xl gap-6 px-6 py-8 sm:grid-cols-3">
          {[
            ["7.4s", c.statHuman, "text-signal-400"],
            ["99%", c.statAts, "text-fg"],
            ["0.2s", c.statTypst, "text-blue-300"],
          ].map(([n, label, color]) => (
            <div key={n as string} className="flex items-baseline gap-3">
              <span className={`font-mono text-2xl font-semibold tabular-nums ${color}`}>{n}</span>
              <span className="text-[13px] leading-snug text-fg-dim">{label}</span>
            </div>
          ))}
        </div>
      </section>

      {/* ── how it works ─────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-6xl px-6 py-20">
        <p className="eyebrow mb-10">{c.howEyebrow}</p>
        <div className="grid gap-10 md:grid-cols-3">
          {c.how.map(([title, body], i) => (
            <motion.div
              key={title}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ delay: i * 0.08 }}
            >
              <div className="mb-3 font-mono text-[13px] text-blue-300">0{i + 1}</div>
              <h3 className="mb-2 font-serif text-lg font-semibold">{title}</h3>
              <p className="text-[14px] leading-relaxed text-fg-dim">{body}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ── features ─────────────────────────────────────────────────────── */}
      <section className="border-y border-ink-800 bg-ink-900/40">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <p className="eyebrow mb-10">{c.featEyebrow}</p>
          <div className="grid gap-5 sm:grid-cols-2">
            {(c.features as [string, string, typeof Columns2][]).map(([title, body, Icon], i) => (
              <motion.div
                key={title}
                className="rounded-xl border border-ink-700 bg-ink-900 p-6"
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-60px" }}
                transition={{ delay: i * 0.06 }}
              >
                <Icon size={18} className="mb-4 text-blue-300" />
                <h3 className="mb-2 text-[15px] font-semibold">{title}</h3>
                <p className="text-[13.5px] leading-relaxed text-fg-dim">{body}</p>
              </motion.div>
            ))}
          </div>
          <p className="mt-8 flex items-center gap-2 font-mono text-[12px] text-fg-faint">
            <MessageSquareText size={13} /> {c.languages}
          </p>
        </div>
      </section>

      {/* ── FAQ ──────────────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-3xl px-6 py-20">
        <p className="eyebrow mb-8">{c.faqEyebrow}</p>
        <div className="divide-y divide-ink-800 border-y border-ink-800">
          {c.faq.map(([q, a]) => (
            <details key={q} className="group py-4">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-[15px] font-medium text-fg">
                {q}
                <span className="font-mono text-fg-faint transition-transform group-open:rotate-45">+</span>
              </summary>
              <p className="pt-3 text-[14px] leading-relaxed text-fg-dim">{a}</p>
            </details>
          ))}
        </div>
        <div className="mt-12 text-center">
          <Link
            to="/studio"
            className="inline-block rounded-lg bg-blue-500 px-6 py-3 text-[15px] font-semibold text-white shadow-[0_0_40px_-8px] shadow-blue-500/70 transition hover:bg-blue-400"
          >
            {c.ctaPrimary}
          </Link>
        </div>
      </section>

      {/* ── footer ───────────────────────────────────────────────────────── */}
      <footer className="border-t border-ink-800">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 py-8">
          <p className="font-serif text-[14px] text-fg-dim">{c.footerBlurb}</p>
          <p className="font-mono text-[11px] text-fg-faint">
            © {new Date().getFullYear()} cvglowup.com
            {me?.authenticated ? "" : " · GDPR-friendly · no tracking ads on paid plans"}
          </p>
        </div>
      </footer>
    </div>
  );
}
