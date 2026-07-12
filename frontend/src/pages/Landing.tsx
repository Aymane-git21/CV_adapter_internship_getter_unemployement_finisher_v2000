/* Landing — "Your CV has 7 seconds." The hero is the product itself: a real
   compiled document being scanned the way a recruiter scans it. */
import { motion, useInView, useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  Columns2, FileSearch, Gauge, KeyRound, Languages, Timer,
} from "lucide-react";
import heroCv from "../assets/hero_cv.jpg";
import logoUrl from "../assets/CVglowup_logo.svg";
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
    languages: "English, French & German — site, documents, lettres de motivation and Anschreiben.",
    faqEyebrow: "Questions",
    faq: [
      ["Does it invent experience I don't have?", "No. The generator is instructed to rephrase, reorder and emphasize — never to fabricate employers, dates or numbers. Everything stays editable, and the source of truth is your master CV."],
      ["What's the catch with the free plan?", "Three generations a day, two templates, one job at a time. Paid plans raise the limits; your own API key removes them entirely."],
      ["Can I edit the result?", "Everything. Structured forms for quick changes, the full Typst source for control, and a chat assistant for \"make it punchier\". The page re-typesets live."],
      ["Why Typst instead of LaTeX?", "Same typographic quality, a thousandth of the wait. Compiles take milliseconds, so the preview follows your keystrokes."],
      ["What about my data?", "Documents live in your account, deletable anytime. Guest documents are reachable only by their secret link. Bring-your-own keys are never stored server-side."],
    ],
    footerBlurb: "CV Glowup typesets careers.",
    marquee: ["Product Manager", "Software Engineer", "Data Analyst", "UX Designer", "Sales Executive", "Marketing Lead", "Consultant", "Project Manager", "DevOps Engineer", "Account Manager"],
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
    languages: "Français, anglais & allemand — site, CV, lettres de motivation et Anschreiben.",
    faqEyebrow: "Questions",
    faq: [
      ["Est-ce que ça invente des expériences ?", "Non. Le générateur reformule, réordonne et met en valeur — jamais il n'invente employeurs, dates ou chiffres. Tout reste éditable, et votre CV de référence fait foi."],
      ["Le piège du plan gratuit ?", "Trois générations par jour, deux modèles, une offre à la fois. Les plans payants montent les limites ; votre propre clé API les supprime."],
      ["Je peux éditer le résultat ?", "Tout. Formulaires pour les retouches rapides, source Typst complète pour le contrôle, et un assistant pour « rends ça plus percutant ». La page se recompose en direct."],
      ["Pourquoi Typst plutôt que LaTeX ?", "La même qualité typographique, mille fois moins d'attente. La compilation prend des millisecondes, l'aperçu suit vos frappes."],
      ["Et mes données ?", "Vos documents vivent dans votre compte, supprimables à tout moment. Les clés API personnelles ne sont jamais stockées côté serveur."],
    ],
    footerBlurb: "CV Glowup compose des carrières.",
    marquee: ["Chef de projet", "Ingénieur logiciel", "Data Analyst", "Designer UX", "Commercial", "Responsable marketing", "Consultant", "Product Manager", "Ingénieur DevOps", "Chargé de clientèle"],
  },
  de: {
    eyebrow: "Recruiter entscheiden schnell",
    title1: "Ihr Lebenslauf hat",
    title2: "7 Sekunden.",
    title3: "Nutzen Sie jede davon.",
    sub: "Fügen Sie eine Stellenanzeige ein. CV Glowup schreibt Ihren Lebenslauf und Ihr Anschreiben darauf zu, setzt beides in Millisekunden — und zeigt Ihnen die fertige Seite, während Sie editieren: Formulare, Quelltext oder Chat.",
    ctaPrimary: "Lebenslauf anpassen — kostenlos",
    ctaSecondary: "Preise ansehen",
    ctaNote: "Erste Generierung kostenlos. Ohne Konto, ohne Karte.",
    statHuman: "dauert der erste Blick eines Recruiters auf einen Lebenslauf",
    statAts: "der großen Unternehmen filtern Lebensläufe zuerst per Software",
    statTypst: "zum Setzen Ihrer Seite — live, während Sie tippen",
    howEyebrow: "So funktioniert es",
    how: [
      ["Stellenanzeige einfügen", "Eine oder mehrere — jede läuft parallel in ihrem eigenen Tab."],
      ["Zusehen, wie sich die Dokumente schreiben", "Lebenslauf, Anschreiben und Kontaktnachricht, zugeschnitten auf die Stelle und live auf einer echten A4-Seite gesetzt."],
      ["Alles bearbeiten, auf drei Wegen", "Strukturierte Formulare, der rohe Typst-Quelltext, oder sagen Sie dem Assistenten einfach, was er ändern soll."],
    ],
    featEyebrow: "Gebaut für den Bewerbungsmarathon",
    features: [
      ["Parallele Bewerbungen", "Bis zu zehn Stellen auf einmal. Jede Stelle bekommt ihren eigenen Tab, ihren eigenen Lebenslauf, ihr eigenes Anschreiben.", Columns2],
      ["Ein Match-Score, der nicht lügt", "Keywords werden einmal extrahiert, dann werden beide Versionen an derselben Liste gemessen. Das Vorher/Nachher-Delta wird berechnet, nicht generiert.", FileSearch],
      ["Satz in Millisekunden", "Eine Typst-Engine ersetzt LaTeX: Die Seite rendert bei jeder Änderung in ~0,2 s neu. Keine Warteschlangen, kein Warten auf PDFs.", Gauge],
      ["Ihr Schlüssel, Ihre Regeln", "Hinterlegen Sie Ihren eigenen Gemini-API-Schlüssel und generieren Sie unbegrenzt, kostenlos. Der Schlüssel bleibt in Ihrem Browser — wir speichern ihn nie.", KeyRound],
    ],
    languages: "Deutsch, Englisch & Französisch — Website, Dokumente, Anschreiben und lettres de motivation.",
    faqEyebrow: "Fragen",
    faq: [
      ["Erfindet es Erfahrung, die ich nicht habe?", "Nein. Der Generator formuliert um, ordnet neu und betont — er erfindet nie Arbeitgeber, Daten oder Zahlen. Alles bleibt editierbar, und Ihr Master-Lebenslauf ist die einzige Quelle der Wahrheit."],
      ["Wo ist der Haken beim Gratis-Plan?", "Drei Generierungen pro Tag, zwei Vorlagen, eine Stelle auf einmal. Bezahlte Pläne erhöhen die Limits; Ihr eigener API-Schlüssel hebt sie komplett auf."],
      ["Kann ich das Ergebnis bearbeiten?", "Alles. Strukturierte Formulare für schnelle Änderungen, der volle Typst-Quelltext für Kontrolle, und ein Chat-Assistent für „mach es prägnanter“. Die Seite setzt sich live neu."],
      ["Warum Typst statt LaTeX?", "Dieselbe typografische Qualität, ein Tausendstel der Wartezeit. Kompilieren dauert Millisekunden, die Vorschau folgt Ihren Tastenanschlägen."],
      ["Was passiert mit meinen Daten?", "Dokumente liegen in Ihrem Konto und sind jederzeit löschbar. Gast-Dokumente sind nur über ihren geheimen Link erreichbar. Eigene API-Schlüssel werden nie serverseitig gespeichert."],
    ],
    footerBlurb: "CV Glowup setzt Karrieren.",
    marquee: ["Projektmanager", "Softwareentwickler", "Data Analyst", "UX-Designer", "Vertriebsleiter", "Marketing Manager", "Berater", "Product Manager", "DevOps Engineer", "Key Account Manager"],
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
      <div className="absolute -left-3 -top-3 z-10 flex items-center gap-1.5 rounded-lg border border-danger/40 glass-panel px-2.5 py-1.5 shadow-xl sm:-left-5 sm:-top-5">
        <Timer size={13} className="text-danger" />
        <span className="font-mono text-[13px] font-medium tabular-nums text-danger">
          {count.toFixed(1)}s
        </span>
      </div>
      {/* scan line */}
      {!reduced && (
        <motion.div
          className="pointer-events-none absolute inset-x-0 z-10 h-20"
          style={{
            background:
              "linear-gradient(to bottom, transparent, rgba(217,99,40,0.14) 70%, rgba(217,99,40,0.5))",
            borderBottom: "1.5px solid rgba(217,99,40,0.8)",
          }}
          initial={{ top: "-10%" }}
          animate={{ top: ["−10%", "92%"] }}
          transition={{ duration: 7, repeat: Infinity, repeatDelay: 2, ease: "linear" }}
        />
      )}
    </>
  );
}

/* Number that counts up when scrolled into view. */
function CountUp({ to, decimals = 0, suffix = "" }: { to: number; decimals?: number; suffix?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const reduced = useReducedMotion();
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (!inView) return;
    if (reduced) {
      setValue(to);
      return;
    }
    const started = performance.now();
    const duration = 1200;
    let raf = 0;
    const tick = (now: number) => {
      const p = Math.min(1, (now - started) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      setValue(to * eased);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [inView, to, reduced]);
  return (
    <span ref={ref}>
      {value.toFixed(decimals)}
      {suffix}
    </span>
  );
}

export default function Landing() {
  const { lang } = useI18n();
  const me = useSession((s) => s.me);
  const c = copy[lang];

  return (
    <div>
      {/* ── hero ─────────────────────────────────────────────────────────── */}
      <section className="relative overflow-hidden border-b border-black/10">
        {/* drifting ember glow */}
        <div
          className="ember pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(900px 500px at 75% 30%, rgba(218,111,47,0.16), transparent 65%)",
          }}
        />
        {/* logo watermark */}
        <img
          src={logoUrl}
          alt=""
          aria-hidden="true"
          className="pointer-events-none absolute -right-24 -top-24 w-[420px] opacity-[0.05] blur-[1px]"
        />
        <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-6 py-16 lg:grid-cols-[1.05fr_0.95fr] lg:py-24">
          <div>
            <motion.p
              className="eyebrow mb-4 text-danger"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
            >
              {c.eyebrow}
            </motion.p>
            <motion.h1
              className="mb-6 font-sans text-[2.6rem] font-bold leading-[1.08] tracking-tight sm:text-[3.4rem] text-text"
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.06 }}
            >
              {c.title1}{" "}
              <span className="flame-text whitespace-nowrap">{c.title2}</span>
              <br />
              <span className="text-text">{c.title3}</span>
            </motion.h1>
            <motion.p
              className="mb-8 max-w-xl text-[15.5px] leading-relaxed text-text/70"
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
                className="btn-flame rounded-lg px-6 py-3 text-[15px] font-semibold"
              >
                {c.ctaPrimary}
              </Link>
              <Link to="/pricing" className="text-[14px] text-text/70 underline-offset-4 hover:text-text hover:underline">
                {c.ctaSecondary}
              </Link>
            </motion.div>
            <p className="mt-4 font-mono text-[11.5px] text-text/50">{c.ctaNote}</p>
          </div>

          {/* the paper under the recruiter's scan */}
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

      {/* ── role marquee ─────────────────────────────────────────────────── */}
      <section className="marquee-mask overflow-hidden border-b border-black/10 py-3" aria-hidden="true">
        <div className="marquee-track gap-3">
          {[...c.marquee, ...c.marquee].map((role, i) => (
            <span
              key={i}
              className="whitespace-nowrap rounded-full border border-black/10 glass-panel px-3.5 py-1 font-mono text-[11.5px] text-text/60"
            >
              {role}
            </span>
          ))}
        </div>
      </section>

      {/* ── stats strip ──────────────────────────────────────────────────── */}
      <section className="border-b border-black/10 glass-panel">
        <div className="mx-auto grid max-w-6xl gap-6 px-6 py-8 sm:grid-cols-3">
          <div className="flex items-baseline gap-3">
            <span className="font-mono text-2xl font-semibold tabular-nums text-danger">
              <CountUp to={7.4} decimals={1} suffix="s" />
            </span>
            <span className="text-[13px] leading-snug text-text/70">{c.statHuman}</span>
          </div>
          <div className="flex items-baseline gap-3">
            <span className="font-mono text-2xl font-semibold tabular-nums text-text">
              <CountUp to={99} suffix="%" />
            </span>
            <span className="text-[13px] leading-snug text-text/70">{c.statAts}</span>
          </div>
          <div className="flex items-baseline gap-3">
            <span className="font-mono text-2xl font-semibold tabular-nums text-flame-600">
              <CountUp to={0.2} decimals={1} suffix="s" />
            </span>
            <span className="text-[13px] leading-snug text-text/70">{c.statTypst}</span>
          </div>
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
              <div className="mb-3 font-mono text-[13px] text-flame-600">0{i + 1}</div>
              <h3 className="mb-2 font-sans text-lg font-semibold text-text">{title}</h3>
              <p className="text-[14px] leading-relaxed text-text/70">{body}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ── features ─────────────────────────────────────────────────────── */}
      <section className="border-y border-black/10 glass-panel">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <p className="eyebrow mb-10">{c.featEyebrow}</p>
          <div className="grid gap-5 sm:grid-cols-2">
            {(c.features as [string, string, typeof Columns2][]).map(([title, body, Icon], i) => (
              <motion.div
                key={title}
                className="card-lift rounded-xl border border-white/40 glass-panel p-6"
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-60px" }}
                transition={{ delay: i * 0.06 }}
              >
                <span className="mb-4 grid size-9 place-items-center rounded-lg bg-flame-950 text-flame-600">
                  <Icon size={17} />
                </span>
                <h3 className="mb-2 text-[15px] font-semibold text-text">{title}</h3>
                <p className="text-[13.5px] leading-relaxed text-text/70">{body}</p>
              </motion.div>
            ))}
          </div>
          <p className="mt-8 flex items-center gap-2 font-mono text-[12px] text-text/50">
            <Languages size={13} className="text-flame-600" /> {c.languages}
          </p>
        </div>
      </section>

      {/* ── FAQ ──────────────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-3xl px-6 py-20">
        <p className="eyebrow mb-8">{c.faqEyebrow}</p>
        <div className="divide-y divide-black/10 border-y border-black/10">
          {c.faq.map(([q, a]) => (
            <details key={q} className="group py-4">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-[15px] font-medium text-text">
                {q}
                <span className="font-mono text-text/50 transition-transform group-open:rotate-45">+</span>
              </summary>
              <p className="pt-3 text-[14px] leading-relaxed text-text/70">{a}</p>
            </details>
          ))}
        </div>
        <div className="mt-12 text-center">
          <Link
            to="/studio"
            className="btn-flame inline-block rounded-lg px-6 py-3 text-[15px] font-semibold"
          >
            {c.ctaPrimary}
          </Link>
        </div>
      </section>

      {/* ── footer ───────────────────────────────────────────────────────── */}
      <footer className="border-t border-black/10">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 py-8">
          <p className="flex items-center gap-2.5 font-sans text-[14px] font-medium text-text/70">
            <img src={logoUrl} alt="" className="size-6" aria-hidden="true" />
            {c.footerBlurb}
          </p>
          <p className="font-mono text-[11px] text-text/50">
            © {new Date().getFullYear()} cvglowup.com
            {me?.authenticated ? "" : " · GDPR-friendly · no tracking ads on paid plans"}
          </p>
        </div>
      </footer>
    </div>
  );
}
