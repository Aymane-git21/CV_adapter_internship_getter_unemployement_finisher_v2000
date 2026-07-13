/* Landing — "Your CV has 7 seconds."
   The hero is a Three.js scene (the tailored page igniting from its edges
   over a bed of embers) and the page is choreographed with GSAP
   ScrollTrigger: staggered headline, scroll-linked camera, counting
   stats, velocity-reactive marquee and a magnetic CTA.
   All motion is gated behind prefers-reduced-motion. */
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { lazy, Suspense, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  ChevronDown, Columns2, FileSearch, Gauge, KeyRound, Languages, Timer,
} from "lucide-react";
import heroCv from "../assets/hero_cv.jpg";
import logoUrl from "../assets/CVglowup_logo.svg";
import { useI18n } from "../i18n";
import { useSession } from "../store";

gsap.registerPlugin(ScrollTrigger);

const HeroScene = lazy(() => import("../components/HeroScene"));

export const copy = {
  en: {
    eyebrow: "on average",
    title1: "Your CV has",
    title2: "7.4 seconds.",
    title3: "to convince recruiters.",
    title4: "Make every one count.",
    sub: "Paste a job posting and a CV, and let us take care of the rest.",
    ctaPrimary: "Tailor my CV | free",
    ctaSecondary: "See pricing",
    ctaNote: "First generation free. No account, no card.",
    statHuman: "average first look a recruiter gives a CV",
    statAts: "of large companies screen CVs with software first",
    statTypst: "to typeset your page, live, as you type",
    howEyebrow: "How it works",
    how: [
      ["Paste the job posting", "One or several: each runs in parallel, in its own tab."],
      ["Watch the documents write themselves", "CV, cover letter and outreach message, tailored to the posting and typeset live on a real A4 page."],
      ["Edit anything, three ways", "Structured forms, the raw Typst source, or just tell the assistant what to change."],
    ],
    featEyebrow: "Built for the application grind",
    features: [
      ["Parallel applications", "Queue up to ten postings at once. Every job gets its own tab, its own CV, its own letter.", Columns2],
      ["A match score that doesn't lie", "Keywords are extracted once, then both versions are measured against the same list. The before/after delta is computed, not generated.", FileSearch],
      ["Millisecond typesetting", "A Typst engine replaces LaTeX: the page re-renders in ~0.2 s on every edit. No queues, no waiting for PDFs.", Gauge],
      ["Your key, your rules", "Plug in your own Gemini API key and generate without limits, free. The key stays in your browser; we never store it.", KeyRound],
    ],
    languages: "English, French & German: site, documents, lettres de motivation and Anschreiben.",
    faqEyebrow: "Questions",
    faq: [
      ["Does it invent experience I don't have?", "No. The generator is instructed to rephrase, reorder and emphasize, never to fabricate employers, dates or numbers. Everything stays editable, and the source of truth is your master CV."],
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
    title3: "pour convaincre les recruteurs.",
    title4: "Faites-les compter.",
    sub: "Collez une offre d'emploi. CV Glowup réécrit votre CV et votre lettre de motivation pour cette offre, les compose en quelques millisecondes, et vous montre la page finale pendant que vous éditez : formulaires, source, ou chat.",
    ctaPrimary: "Adapter mon CV | gratuit",
    ctaSecondary: "Voir les tarifs",
    ctaNote: "Première génération gratuite. Sans compte, sans carte.",
    statHuman: "de premier regard d'un recruteur sur un CV",
    statAts: "des grandes entreprises filtrent les CV par logiciel",
    statTypst: "pour composer votre page, en direct",
    howEyebrow: "Comment ça marche",
    how: [
      ["Collez l'offre d'emploi", "Une ou plusieurs : chacune tourne en parallèle, dans son propre onglet."],
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
    languages: "Français, anglais & allemand : site, CV, lettres de motivation et Anschreiben.",
    faqEyebrow: "Questions",
    faq: [
      ["Est-ce que ça invente des expériences ?", "Non. Le générateur reformule, réordonne et met en valeur, jamais il n'invente employeurs, dates ou chiffres. Tout reste éditable, et votre CV de référence fait foi."],
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
    title3: "um Recruiter zu überzeugen.",
    title4: "Nutzen Sie jede davon.",
    sub: "Fügen Sie eine Stellenanzeige ein. CV Glowup schreibt Ihren Lebenslauf und Ihr Anschreiben darauf zu, setzt beides in Millisekunden, und zeigt Ihnen die fertige Seite, während Sie editieren: Formulare, Quelltext oder Chat.",
    ctaPrimary: "Lebenslauf anpassen | kostenlos",
    ctaSecondary: "Preise ansehen",
    ctaNote: "Erste Generierung kostenlos. Ohne Konto, ohne Karte.",
    statHuman: "dauert der erste Blick eines Recruiters auf einen Lebenslauf",
    statAts: "der großen Unternehmen filtern Lebensläufe zuerst per Software",
    statTypst: "zum Setzen Ihrer Seite, live, während Sie tippen",
    howEyebrow: "So funktioniert es",
    how: [
      ["Stellenanzeige einfügen", "Eine oder mehrere: jede läuft parallel in ihrem eigenen Tab."],
      ["Zusehen, wie sich die Dokumente schreiben", "Lebenslauf, Anschreiben und Kontaktnachricht, zugeschnitten auf die Stelle und live auf einer echten A4-Seite gesetzt."],
      ["Alles bearbeiten, auf drei Wegen", "Strukturierte Formulare, der rohe Typst-Quelltext, oder sagen Sie dem Assistenten einfach, was er ändern soll."],
    ],
    featEyebrow: "Gebaut für den Bewerbungsmarathon",
    features: [
      ["Parallele Bewerbungen", "Bis zu zehn Stellen auf einmal. Jede Stelle bekommt ihren eigenen Tab, ihren eigenen Lebenslauf, ihr eigenes Anschreiben.", Columns2],
      ["Ein Match-Score, der nicht lügt", "Keywords werden einmal extrahiert, dann werden beide Versionen an derselben Liste gemessen. Das Vorher/Nachher-Delta wird berechnet, nicht generiert.", FileSearch],
      ["Satz in Millisekunden", "Eine Typst-Engine ersetzt LaTeX: Die Seite rendert bei jeder Änderung in ~0,2 s neu. Keine Warteschlangen, kein Warten auf PDFs.", Gauge],
      ["Ihr Schlüssel, Ihre Regeln", "Hinterlegen Sie Ihren eigenen Gemini-API-Schlüssel und generieren Sie unbegrenzt, kostenlos. Der Schlüssel bleibt in Ihrem Browser; wir speichern ihn nie.", KeyRound],
    ],
    languages: "Deutsch, Englisch & Französisch: Website, Dokumente, Anschreiben und lettres de motivation.",
    faqEyebrow: "Fragen",
    faq: [
      ["Erfindet es Erfahrung, die ich nicht habe?", "Nein. Der Generator formuliert um, ordnet neu und betont, er erfindet nie Arbeitgeber, Daten oder Zahlen. Alles bleibt editierbar, und Ihr Master-Lebenslauf ist die einzige Quelle der Wahrheit."],
      ["Wo ist der Haken beim Gratis-Plan?", "Drei Generierungen pro Tag, zwei Vorlagen, eine Stelle auf einmal. Bezahlte Pläne erhöhen die Limits; Ihr eigener API-Schlüssel hebt sie komplett auf."],
      ["Kann ich das Ergebnis bearbeiten?", "Alles. Strukturierte Formulare für schnelle Änderungen, der volle Typst-Quelltext für Kontrolle, und ein Chat-Assistent für „mach es prägnanter“. Die Seite setzt sich live neu."],
      ["Warum Typst statt LaTeX?", "Dieselbe typografische Qualität, ein Tausendstel der Wartezeit. Kompilieren dauert Millisekunden, die Vorschau folgt Ihren Tastenanschlägen."],
      ["Was passiert mit meinen Daten?", "Dokumente liegen in Ihrem Konto und sind jederzeit löschbar. Gast-Dokumente sind nur über ihren geheimen Link erreichbar. Eigene API-Schlüssel werden nie serverseitig gespeichert."],
    ],
    footerBlurb: "CV Glowup setzt Karrieren.",
    marquee: ["Projektmanager", "Softwareentwickler", "Data Analyst", "UX-Designer", "Vertriebsleiter", "Marketing Manager", "Berater", "Product Manager", "DevOps Engineer", "Key Account Manager"],
  },
};

/* Words wrapped for the staggered reveal. */
function SplitWords({ text, className = "" }: { text: string; className?: string }) {
  return (
    <>
      {text.split(" ").map((word, i) => (
        <span key={i} className="inline-block overflow-hidden pb-[0.08em] -mb-[0.08em] align-bottom">
          <span className={`hero-word inline-block will-change-transform ${className}`}>{word}&nbsp;</span>
        </span>
      ))}
    </>
  );
}

/* The 7-second countdown chip floating over the scanned page. */
function CountdownChip() {
  const [count, setCount] = useState(7.0);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const started = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const elapsed = ((now - started) / 1000) % 9;
      setCount(Math.max(0, 7 - elapsed));
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);
  return (
    <div className="pointer-events-none absolute right-[8%] top-[16%] z-10 hidden items-center gap-1.5 rounded-lg border border-danger/40 glass-panel px-2.5 py-1.5 shadow-xl lg:flex">
      <Timer size={13} className="text-danger" />
      <span className="font-mono text-[13px] font-medium tabular-nums text-danger">{count.toFixed(1)}s</span>
    </div>
  );
}

export default function Landing() {
  const { lang } = useI18n();
  const me = useSession((s) => s.me);
  const c = copy[lang];

  const rootRef = useRef<HTMLDivElement>(null);
  const heroRef = useRef<HTMLElement>(null);
  const heroContentRef = useRef<HTMLDivElement>(null);
  const fallbackRef = useRef<HTMLDivElement>(null);
  const marqueeRef = useRef<HTMLDivElement>(null);
  const ctaRef = useRef<HTMLAnchorElement>(null);
  const scrollProgress = useRef(0);

  // ---- GSAP choreography (re-runs per language: text nodes change) -------
  useLayoutEffect(() => {
    // The app scrolls inside <main class="overflow-y-auto">, not the window —
    // every trigger must watch that element or it never fires.
    const scroller = rootRef.current?.closest("main") ?? undefined;
    const ctx = gsap.context(() => {
      // Scroll progress feeds the Three.js camera even under reduced motion
      // (it only moves when the user scrolls, which is user-initiated).
      ScrollTrigger.create({
        scroller,
        trigger: heroRef.current,
        start: "top top",
        end: "bottom top",
        onUpdate: (self) => {
          scrollProgress.current = self.progress;
        },
      });

      const mm = gsap.matchMedia();
      mm.add("(prefers-reduced-motion: no-preference)", () => {
        // 1 — headline cascade
        gsap.from(".hero-word", {
          yPercent: 115,
          duration: 0.9,
          ease: "power4.out",
          stagger: 0.045,
          delay: 0.1,
        });
        gsap.from("[data-hero-fade]", {
          y: 18,
          autoAlpha: 0,
          duration: 0.8,
          ease: "power3.out",
          stagger: 0.09,
          delay: 0.55,
        });

        // 2 — hero content drifts up and out as you scroll
        gsap.to(heroContentRef.current, {
          yPercent: -14,
          autoAlpha: 0.1,
          ease: "none",
          scrollTrigger: { scroller, trigger: heroRef.current, start: "top top", end: "bottom top", scrub: true },
        });

        // 3 — marquee scrolls forever, faster while the user scrolls
        const track = marqueeRef.current;
        if (track) {
          const tween = gsap.to(track, { xPercent: -50, repeat: -1, ease: "none", duration: 32 });
          let boost = 1;
          ScrollTrigger.create({
            scroller,
            onUpdate: (self) => {
              boost = 1 + Math.min(3.5, Math.abs(self.getVelocity()) / 350);
            },
          });
          const lerp = () => {
            tween.timeScale(gsap.utils.interpolate(tween.timeScale(), boost, 0.08));
            boost = gsap.utils.interpolate(boost, 1, 0.04);
          };
          gsap.ticker.add(lerp);
          return () => gsap.ticker.remove(lerp);
        }

        return undefined;
      });

      mm.add("(prefers-reduced-motion: no-preference)", () => {
        // 4 — stats count up when they enter
        gsap.utils.toArray<HTMLElement>("[data-count-to]").forEach((node) => {
          const to = parseFloat(node.dataset.countTo!);
          const decimals = parseInt(node.dataset.decimals ?? "0", 10);
          const suffix = node.dataset.suffix ?? "";
          const state = { v: 0 };
          gsap.to(state, {
            v: to,
            duration: 1.4,
            ease: "power3.out",
            scrollTrigger: { scroller, trigger: node, start: "top 88%", once: true },
            onUpdate: () => {
              node.textContent = state.v.toFixed(decimals) + suffix;
            },
          });
        });

        // 5 — section reveals
        gsap.utils.toArray<HTMLElement>("[data-reveal]").forEach((el) => {
          gsap.from(el, {
            y: 42,
            autoAlpha: 0,
            duration: 0.9,
            ease: "power3.out",
            scrollTrigger: { scroller, trigger: el, start: "top 86%", once: true },
            delay: parseFloat(el.dataset.reveal || "0"),
          });
        });

        // 6 — the giant step numbers slide in with scrub
        gsap.utils.toArray<HTMLElement>("[data-step-num]").forEach((el) => {
          gsap.from(el, {
            xPercent: -30,
            autoAlpha: 0,
            ease: "none",
            scrollTrigger: { scroller, trigger: el, start: "top 95%", end: "top 55%", scrub: true },
          });
        });
      });
    }, rootRef);

    return () => ctx.revert();
  }, [lang]);

  // ---- magnetic primary CTA ------------------------------------------------
  useEffect(() => {
    const el = ctaRef.current;
    if (!el || !window.matchMedia("(pointer: fine)").matches) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const xTo = gsap.quickTo(el, "x", { duration: 0.3, ease: "power3.out" });
    const yTo = gsap.quickTo(el, "y", { duration: 0.3, ease: "power3.out" });
    const move = (e: MouseEvent) => {
      const r = el.getBoundingClientRect();
      xTo((e.clientX - (r.left + r.width / 2)) * 0.25);
      yTo((e.clientY - (r.top + r.height / 2)) * 0.35);
    };
    const reset = () => {
      gsap.to(el, { x: 0, y: 0, duration: 0.5, ease: "elastic.out(1, 0.4)" });
    };
    el.addEventListener("mousemove", move);
    el.addEventListener("mouseleave", reset);
    return () => {
      el.removeEventListener("mousemove", move);
      el.removeEventListener("mouseleave", reset);
    };
  }, []);

  const fadeFallback = () => {
    if (fallbackRef.current) gsap.to(fallbackRef.current, { autoAlpha: 0, duration: 0.8 });
  };

  return (
    <div ref={rootRef}>
      {/* ── hero ─────────────────────────────────────────────────────────── */}
      <section
        ref={heroRef}
        className="relative flex min-h-[calc(100vh-3.5rem)] items-center overflow-hidden border-b border-black/10"
      >
        {/* three.js scene */}
        <Suspense fallback={null}>
          <HeroScene progress={scrollProgress} onReady={fadeFallback} />
        </Suspense>

        {/* static fallback until the scene's first frame (or forever without WebGL) */}
        <div ref={fallbackRef} className="pointer-events-none absolute right-[4%] top-1/2 hidden w-[360px] -translate-y-1/2 rotate-1 lg:block">
          <div className="sheet overflow-hidden">
            <img src={heroCv} alt="" className="block w-full" />
          </div>
        </div>

        <CountdownChip />

        <div ref={heroContentRef} className="relative z-10 mx-auto w-full max-w-6xl px-6 py-16">
          <div className="max-w-2xl">
            <p data-hero-fade className="eyebrow mb-5 text-danger">{c.eyebrow}</p>
            <h1 className="mb-7 font-sans text-[2.7rem] font-bold leading-[1.06] tracking-tight text-text sm:text-[4rem]">
              <SplitWords text={c.title1} />
              <SplitWords text={c.title2} className="flame-text" />
              <br />
              <SplitWords text={c.title3} />
              <br />
              <SplitWords text={c.title4} />
            </h1>
            <p data-hero-fade className="mb-9 max-w-xl text-[15.5px] leading-relaxed text-text/70">
              {c.sub}
            </p>
            <div data-hero-fade className="flex flex-wrap items-center gap-5">
              <Link
                ref={ctaRef}
                to="/studio"
                className="btn-flame inline-block rounded-xl px-7 py-3.5 text-[15px] font-semibold"
              >
                {c.ctaPrimary}
              </Link>
              <Link to="/pricing" className="text-[14px] text-text/70 underline-offset-4 hover:text-text hover:underline">
                {c.ctaSecondary}
              </Link>
            </div>
            <p data-hero-fade className="mt-5 font-mono text-[11.5px] text-text/50">{c.ctaNote}</p>
          </div>
        </div>

        {/* scroll hint */}
        <div data-hero-fade className="absolute bottom-5 left-1/2 -translate-x-1/2 text-flame-600">
          <ChevronDown size={18} className="animate-bounce" />
        </div>
      </section>

      {/* ── role marquee ─────────────────────────────────────────────────── */}
      <section className="marquee-mask overflow-hidden border-b border-black/10 py-3" aria-hidden="true">
        <div ref={marqueeRef} className="flex w-max gap-3">
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
        <div className="mx-auto grid max-w-6xl gap-6 px-6 py-10 sm:grid-cols-3">
          <div data-reveal className="flex items-baseline gap-3">
            <span data-count-to="7.4" data-decimals="1" data-suffix="s" className="font-mono text-3xl font-semibold tabular-nums text-danger">7.4s</span>
            <span className="text-[13px] leading-snug text-text/70">{c.statHuman}</span>
          </div>
          <div data-reveal="0.08" className="flex items-baseline gap-3">
            <span data-count-to="99" data-suffix="%" className="font-mono text-3xl font-semibold tabular-nums text-text">99%</span>
            <span className="text-[13px] leading-snug text-text/70">{c.statAts}</span>
          </div>
          <div data-reveal="0.16" className="flex items-baseline gap-3">
            <span data-count-to="0.2" data-decimals="1" data-suffix="s" className="font-mono text-3xl font-semibold tabular-nums text-flame-600">0.2s</span>
            <span className="text-[13px] leading-snug text-text/70">{c.statTypst}</span>
          </div>
        </div>
      </section>

      {/* ── how it works ─────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-6xl px-6 py-24">
        <p data-reveal className="eyebrow mb-12">{c.howEyebrow}</p>
        <div className="space-y-14">
          {c.how.map(([title, body], i) => (
            <div key={title} className="grid items-baseline gap-4 md:grid-cols-[140px_1fr]">
              <div data-step-num className="flame-text font-mono text-[64px] font-bold leading-none md:text-[88px]">
                0{i + 1}
              </div>
              <div data-reveal>
                <h3 className="mb-2 font-sans text-2xl font-semibold tracking-tight text-text">{title}</h3>
                <p className="max-w-2xl text-[15px] leading-relaxed text-text/70">{body}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── features ─────────────────────────────────────────────────────── */}
      <section className="border-y border-black/10 glass-panel">
        <div className="mx-auto max-w-6xl px-6 py-24">
          <p data-reveal className="eyebrow mb-12">{c.featEyebrow}</p>
          <div className="grid gap-5 sm:grid-cols-2">
            {(c.features as [string, string, typeof Columns2][]).map(([title, body, Icon], i) => (
              <div
                key={title}
                data-reveal={String(i * 0.07)}
                className="card-lift rounded-xl border border-white/40 glass-panel p-7"
              >
                <span className="mb-5 grid size-10 place-items-center rounded-lg bg-flame-950 text-flame-600">
                  <Icon size={18} />
                </span>
                <h3 className="mb-2 text-[16px] font-semibold text-text">{title}</h3>
                <p className="text-[13.5px] leading-relaxed text-text/70">{body}</p>
              </div>
            ))}
          </div>
          <p data-reveal className="mt-10 flex items-center gap-2 font-mono text-[12px] text-text/50">
            <Languages size={13} className="text-flame-600" /> {c.languages}
          </p>
        </div>
      </section>

      {/* ── FAQ ──────────────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-3xl px-6 py-24">
        <p data-reveal className="eyebrow mb-8">{c.faqEyebrow}</p>
        <div data-reveal className="divide-y divide-black/10 border-y border-black/10">
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
        <div data-reveal className="mt-14 text-center">
          <Link
            to="/studio"
            className="btn-flame inline-block rounded-xl px-8 py-4 text-[16px] font-semibold"
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
