/* Landing — THE FORGE.
   Drenched dark register: a full-bleed Three.js smolder field where the
   cursor works like a bellows, a scroll-pinned 7.4s recruiter-scan
   countdown scrubbed by GSAP, sticky-stacked steps, a feature ledger
   whose rules ignite on hover, and a molten finale. The floating CV
   sheet is gone: the fire itself is the hero.
   All motion gated behind prefers-reduced-motion. */
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { lazy, Suspense, useLayoutEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { Languages } from "lucide-react";
import logoUrl from "../assets/CVglowup_logo.svg";
import { useI18n } from "../i18n";
import { useSession } from "../store";

gsap.registerPlugin(ScrollTrigger);

const ForgeScene = lazy(() => import("../components/ForgeScene"));

export const copy = {
  en: {
    title1: "Your CV has",
    title2: "7.4 seconds",
    title3: "to convince recruiters.",
    title4: "Make every one count.",
    sub: "Paste a job posting. CV Glowup rewrites your CV and cover letter for that job, typesets them in milliseconds, and shows you the finished page while you edit: forms, source, or chat.",
    ctaPrimary: "Tailor my CV | free",
    ctaSecondary: "See pricing",
    ctaNote: "First generation free. No account, no card.",
    scroll: "scroll",
    scanTitle: "What a recruiter actually reads",
    scan: [
      ["0.0 – 0.9s", "Name and current job title"],
      ["0.9 – 2.3s", "Current company and dates"],
      ["2.3 – 4.4s", "Previous role, promotions"],
      ["4.4 – 6.0s", "Education"],
      ["6.0 – 7.4s", "Skills, keywords, gaps"],
    ],
    scanVerdict: "Then: keep, or reject.",
    scanVerdictSub: "A tailored CV puts the right words exactly where those seconds land.",
    statHuman: "average first look a recruiter gives a CV",
    statAts: "of large companies screen CVs with software first",
    statTypst: "to typeset your page, live, as you type",
    howTitle: "How it works",
    how: [
      ["Paste the job posting", "One or several: each runs in parallel, in its own tab."],
      ["Watch the documents write themselves", "CV, cover letter and outreach message, tailored to the posting and typeset live on a real A4 page."],
      ["Edit anything, three ways", "Structured forms, the raw Typst source, or just tell the assistant what to change."],
    ],
    howModes: ["Forms", "Typst source", "Chat"],
    featTitle: "Built for the application grind",
    features: [
      ["Parallel applications", "Queue up to ten postings at once. Every job gets its own tab, its own CV, its own letter."],
      ["A match score that doesn't lie", "Keywords are extracted once, then both versions are measured against the same list. The before/after delta is computed, not generated."],
      ["Millisecond typesetting", "A Typst engine replaces LaTeX: the page re-renders in ~0.2 s on every edit. No queues, no waiting for PDFs."],
      ["Your key, your rules", "Plug in your own Gemini API key and generate without limits, free. The key stays in your browser; we never store it."],
    ],
    languages: "English, French & German: site, documents, lettres de motivation and Anschreiben.",
    faqTitle: "Questions",
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
    title1: "Votre CV a",
    title2: "7,4 secondes",
    title3: "pour convaincre les recruteurs.",
    title4: "Faites-les toutes compter.",
    sub: "Collez une offre d'emploi. CV Glowup réécrit votre CV et votre lettre de motivation pour cette offre, les compose en quelques millisecondes, et vous montre la page finale pendant que vous éditez : formulaires, source, ou chat.",
    ctaPrimary: "Adapter mon CV | gratuit",
    ctaSecondary: "Voir les tarifs",
    ctaNote: "Première génération gratuite. Sans compte, sans carte.",
    scroll: "défiler",
    scanTitle: "Ce qu'un recruteur lit vraiment",
    scan: [
      ["0,0 – 0,9s", "Nom et poste actuel"],
      ["0,9 – 2,3s", "Entreprise actuelle et dates"],
      ["2,3 – 4,4s", "Poste précédent, évolutions"],
      ["4,4 – 6,0s", "Formation"],
      ["6,0 – 7,4s", "Compétences, mots-clés, trous"],
    ],
    scanVerdict: "Ensuite : gardé, ou écarté.",
    scanVerdictSub: "Un CV adapté place les bons mots exactement là où ces secondes se posent.",
    statHuman: "de premier regard d'un recruteur sur un CV",
    statAts: "des grandes entreprises filtrent les CV par logiciel",
    statTypst: "pour composer votre page, en direct",
    howTitle: "Comment ça marche",
    how: [
      ["Collez l'offre d'emploi", "Une ou plusieurs : chacune tourne en parallèle, dans son propre onglet."],
      ["Les documents s'écrivent sous vos yeux", "CV, lettre de motivation et message d'approche, adaptés à l'offre et composés en direct sur une vraie page A4."],
      ["Éditez tout, de trois façons", "Formulaires structurés, source Typst, ou demandez simplement à l'assistant."],
    ],
    howModes: ["Formulaires", "Source Typst", "Chat"],
    featTitle: "Conçu pour la chasse aux offres",
    features: [
      ["Candidatures en parallèle", "Jusqu'à dix offres à la fois. Chaque poste a son onglet, son CV, sa lettre."],
      ["Un score qui ne ment pas", "Les mots-clés sont extraits une fois, puis les deux versions sont mesurées contre la même liste. Le delta avant/après est calculé, pas généré."],
      ["Composition en millisecondes", "Un moteur Typst remplace LaTeX : la page se recompose en ~0,2 s à chaque édition. Pas de file d'attente."],
      ["Votre clé, vos règles", "Branchez votre propre clé API Gemini et générez sans limite, gratuitement. La clé reste dans votre navigateur."],
    ],
    languages: "Français, anglais & allemand : site, CV, lettres de motivation et Anschreiben.",
    faqTitle: "Questions",
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
    title1: "Ihr Lebenslauf hat",
    title2: "7,4 Sekunden",
    title3: "um Recruiter zu überzeugen.",
    title4: "Nutzen Sie jede davon.",
    sub: "Fügen Sie eine Stellenanzeige ein. CV Glowup schreibt Ihren Lebenslauf und Ihr Anschreiben darauf zu, setzt beides in Millisekunden, und zeigt Ihnen die fertige Seite, während Sie editieren: Formulare, Quelltext oder Chat.",
    ctaPrimary: "Lebenslauf anpassen | kostenlos",
    ctaSecondary: "Preise ansehen",
    ctaNote: "Erste Generierung kostenlos. Ohne Konto, ohne Karte.",
    scroll: "scrollen",
    scanTitle: "Was ein Recruiter wirklich liest",
    scan: [
      ["0,0 – 0,9s", "Name und aktuelle Position"],
      ["0,9 – 2,3s", "Aktuelles Unternehmen und Zeiträume"],
      ["2,3 – 4,4s", "Vorherige Rolle, Beförderungen"],
      ["4,4 – 6,0s", "Ausbildung"],
      ["6,0 – 7,4s", "Fähigkeiten, Keywords, Lücken"],
    ],
    scanVerdict: "Dann: weiter, oder aussortiert.",
    scanVerdictSub: "Ein zugeschnittener Lebenslauf legt die richtigen Wörter genau dorthin, wo diese Sekunden landen.",
    statHuman: "dauert der erste Blick eines Recruiters auf einen Lebenslauf",
    statAts: "der großen Unternehmen filtern Lebensläufe zuerst per Software",
    statTypst: "zum Setzen Ihrer Seite, live, während Sie tippen",
    howTitle: "So funktioniert es",
    how: [
      ["Stellenanzeige einfügen", "Eine oder mehrere: jede läuft parallel in ihrem eigenen Tab."],
      ["Zusehen, wie sich die Dokumente schreiben", "Lebenslauf, Anschreiben und Kontaktnachricht, zugeschnitten auf die Stelle und live auf einer echten A4-Seite gesetzt."],
      ["Alles bearbeiten, auf drei Wegen", "Strukturierte Formulare, der rohe Typst-Quelltext, oder sagen Sie dem Assistenten einfach, was er ändern soll."],
    ],
    howModes: ["Formulare", "Typst-Quelltext", "Chat"],
    featTitle: "Gebaut für den Bewerbungsmarathon",
    features: [
      ["Parallele Bewerbungen", "Bis zu zehn Stellen auf einmal. Jede Stelle bekommt ihren eigenen Tab, ihren eigenen Lebenslauf, ihr eigenes Anschreiben."],
      ["Ein Match-Score, der nicht lügt", "Keywords werden einmal extrahiert, dann werden beide Versionen an derselben Liste gemessen. Das Vorher/Nachher-Delta wird berechnet, nicht generiert."],
      ["Satz in Millisekunden", "Eine Typst-Engine ersetzt LaTeX: Die Seite rendert bei jeder Änderung in ~0,2 s neu. Keine Warteschlangen, kein Warten auf PDFs."],
      ["Ihr Schlüssel, Ihre Regeln", "Hinterlegen Sie Ihren eigenen Gemini-API-Schlüssel und generieren Sie unbegrenzt, kostenlos. Der Schlüssel bleibt in Ihrem Browser; wir speichern ihn nie."],
    ],
    languages: "Deutsch, Englisch & Französisch: Website, Dokumente, Anschreiben und lettres de motivation.",
    faqTitle: "Fragen",
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

/* Words wrapped for the masked cascade reveal. */
function SplitWords({ text, className = "" }: { text: string; className?: string }) {
  return (
    <>
      {text.split(" ").map((word, i) => (
        <span key={i} className="inline-block overflow-hidden pb-[0.1em] -mb-[0.1em] align-bottom">
          <span className={`hero-word inline-block will-change-transform ${className}`}>{word}&nbsp;</span>
        </span>
      ))}
    </>
  );
}

export default function Landing() {
  const { lang } = useI18n();
  const me = useSession((s) => s.me);
  const c = copy[lang];
  const decimal = lang === "en" ? "." : ",";
  const fmt = (v: number, decimals: number) => v.toFixed(decimals).replace(".", decimal);

  const rootRef = useRef<HTMLDivElement>(null);
  const heroRef = useRef<HTMLElement>(null);
  const heroContentRef = useRef<HTMLDivElement>(null);
  const scanRef = useRef<HTMLElement>(null);
  const scanCounterRef = useRef<HTMLDivElement>(null);
  const marqueeRef = useRef<HTMLDivElement>(null);
  const heroCtaRef = useRef<HTMLAnchorElement>(null);
  const finaleCtaRef = useRef<HTMLAnchorElement>(null);
  const scrollProgress = useRef(0);

  // ---- GSAP choreography (re-runs per language: text nodes change) -------
  useLayoutEffect(() => {
    // The app scrolls inside <main class="overflow-y-auto">, not the window:
    // every trigger must watch that element or it never fires.
    const scroller = rootRef.current?.closest("main") ?? undefined;
    const ctx = gsap.context(() => {
      // Scroll progress feeds the Three.js heat even under reduced motion
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
        // 1 — headline cascade out of masks
        gsap.from(".hero-word", {
          yPercent: 118,
          duration: 1.0,
          ease: "power4.out",
          stagger: 0.05,
          delay: 0.15,
        });
        gsap.from("[data-hero-fade]", {
          y: 20,
          autoAlpha: 0,
          duration: 0.9,
          ease: "power3.out",
          stagger: 0.1,
          delay: 0.7,
        });

        // 2 — hero content drifts up and dims as you scroll into the scan
        gsap.to(heroContentRef.current, {
          yPercent: -12,
          autoAlpha: 0.08,
          ease: "none",
          scrollTrigger: { scroller, trigger: heroRef.current, start: "top top", end: "bottom top", scrub: true },
        });

        // 3 — marquee scrolls forever, faster while the user scrolls
        const track = marqueeRef.current;
        if (track) {
          const tween = gsap.to(track, { xPercent: -50, repeat: -1, ease: "none", duration: 34 });
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

      // 4 — THE SCAN: pinned countdown scrubbed by scroll (desktop only;
      // mobile and reduced motion get the plain readable list).
      mm.add("(prefers-reduced-motion: no-preference) and (min-width: 768px)", () => {
        const section = scanRef.current;
        const counter = scanCounterRef.current;
        if (!section || !counter) return;

        const items = gsap.utils.toArray<HTMLElement>("[data-scan-item]", section);
        const verdict = section.querySelector<HTMLElement>("[data-scan-verdict]");
        const state = { v: 7.4 };

        // initial states live here, not in the markup: with reduced motion
        // (or on mobile) everything below stays plainly visible.
        gsap.set(items, { opacity: 0.22 });
        if (verdict) gsap.set(verdict, { autoAlpha: 0 });

        const tl = gsap.timeline({
          scrollTrigger: {
            scroller,
            trigger: section,
            start: "top top",
            end: "+=2800",
            scrub: 0.6,
            pin: true,
            anticipatePin: 1,
          },
        });

        // the seconds drain away over the first 80% of the pin
        tl.to(state, {
          v: 0,
          duration: 0.8,
          ease: "none",
          onUpdate: () => {
            counter.textContent = fmt(state.v, 1);
          },
        }, 0);
        // the numeral heats up as time runs out
        tl.fromTo(counter,
          { color: "#f5ede2", textShadow: "0 0 0px rgba(232,114,44,0)" },
          { color: "#ff9a4d", textShadow: "0 0 40px rgba(232,114,44,0.55)", duration: 0.45, ease: "power1.in" },
          0.35,
        );

        // each gaze line lights while "the recruiter is on it", then cools
        items.forEach((item, i) => {
          const at = 0.04 + i * 0.152;
          tl.fromTo(item, { opacity: 0.22, x: 0 }, { opacity: 1, x: 12, duration: 0.06, ease: "power2.out" }, at);
          tl.to(item, { opacity: 0.38, x: 0, duration: 0.08, ease: "power2.in" }, at + 0.13);
        });

        // the verdict lands after the last second burns
        if (verdict) {
          tl.fromTo(verdict, { autoAlpha: 0, y: 36 }, { autoAlpha: 1, y: 0, duration: 0.12, ease: "power3.out" }, 0.85);
          tl.to(counter, { opacity: 0.12, duration: 0.1 }, 0.85);
        }
      });

      mm.add("(prefers-reduced-motion: no-preference)", () => {
        // 5 — facts count up when they enter
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
              node.textContent = fmt(state.v, decimals) + suffix;
            },
          });
        });

        // 6 — section reveals
        gsap.utils.toArray<HTMLElement>("[data-reveal]").forEach((el) => {
          gsap.from(el, {
            y: 44,
            autoAlpha: 0,
            duration: 0.9,
            ease: "power3.out",
            scrollTrigger: { scroller, trigger: el, start: "top 88%", once: true },
            delay: parseFloat(el.dataset.reveal || "0"),
          });
        });

        // 7 — the A4 sheet writes itself, line by line
        gsap.utils.toArray<HTMLElement>("[data-sheet]").forEach((sheet) => {
          gsap.from(sheet.querySelectorAll(".forge-sheet-line"), {
            scaleX: 0,
            duration: 0.5,
            ease: "power2.out",
            stagger: 0.06,
            scrollTrigger: { scroller, trigger: sheet, start: "top 80%", once: true },
          });
        });

        // 8 — ledger rules draw themselves in as the rows enter
        gsap.utils.toArray<HTMLElement>(".forge-ledger-row").forEach((row, i) => {
          gsap.from(row, {
            autoAlpha: 0,
            y: 28,
            duration: 0.8,
            ease: "power3.out",
            delay: (i % 2) * 0.08,
            scrollTrigger: { scroller, trigger: row, start: "top 90%", once: true },
          });
        });
      });
    }, rootRef);

    return () => ctx.revert();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang]);

  // ---- magnetic CTAs -------------------------------------------------------
  useLayoutEffect(() => {
    if (!window.matchMedia("(pointer: fine)").matches) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const cleanups = [heroCtaRef.current, finaleCtaRef.current].filter(Boolean).map((el) => {
      const xTo = gsap.quickTo(el, "x", { duration: 0.3, ease: "power3.out" });
      const yTo = gsap.quickTo(el, "y", { duration: 0.3, ease: "power3.out" });
      const move = (e: MouseEvent) => {
        const r = el!.getBoundingClientRect();
        xTo((e.clientX - (r.left + r.width / 2)) * 0.25);
        yTo((e.clientY - (r.top + r.height / 2)) * 0.35);
      };
      const reset = () => {
        gsap.to(el, { x: 0, y: 0, duration: 0.5, ease: "power4.out" });
      };
      el!.addEventListener("mousemove", move);
      el!.addEventListener("mouseleave", reset);
      return () => {
        el!.removeEventListener("mousemove", move);
        el!.removeEventListener("mouseleave", reset);
      };
    });
    return () => cleanups.forEach((fn) => fn());
  }, []);

  return (
    <div ref={rootRef} className="forge">
      {/* ── hero: the forge floor ────────────────────────────────────────── */}
      <section ref={heroRef} className="relative flex min-h-[calc(100vh-3.5rem)] items-center overflow-hidden">
        {/* CSS fallback (also the no-WebGL state), WebGL scene above it */}
        <div className="forge-hero-fallback absolute inset-0" aria-hidden="true" />
        <Suspense fallback={null}>
          <ForgeScene progress={scrollProgress} density={340} floor={1} />
        </Suspense>

        <div ref={heroContentRef} className="relative z-10 mx-auto w-full max-w-6xl px-6 py-20">
          <h1 className="forge-display mb-8 max-w-[13ch] text-[clamp(2.9rem,8vw,6rem)] font-bold leading-[0.98]">
            <SplitWords text={c.title1} />
            <br />
            <SplitWords text={c.title2} className="molten molten-breathe" />
            <br />
            <span className="text-[0.62em] font-semibold leading-[1.1] text-[var(--forge-dim)]">
              <SplitWords text={c.title3} />
            </span>
          </h1>
          <p data-hero-fade className="mb-10 max-w-xl text-[15.5px] leading-relaxed text-[var(--forge-dim)]">
            {c.sub}
          </p>
          <div data-hero-fade className="flex flex-wrap items-center gap-6">
            <Link
              ref={heroCtaRef}
              to="/studio"
              className="btn-flame btn-flame--forge inline-block rounded-xl px-8 py-4 text-[15.5px] font-semibold"
            >
              {c.ctaPrimary}
            </Link>
            <Link
              to="/pricing"
              className="text-[14px] text-[var(--forge-dim)] underline-offset-4 hover:text-[var(--forge-ink)] hover:underline"
            >
              {c.ctaSecondary}
            </Link>
          </div>
          <p data-hero-fade className="mt-6 font-mono text-[11.5px] text-[var(--forge-faint)]">{c.ctaNote}</p>
        </div>

        {/* scroll cue */}
        <div data-hero-fade className="absolute bottom-7 left-1/2 flex -translate-x-1/2 flex-col items-center gap-2.5">
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--forge-faint)]">{c.scroll}</span>
          <span className="forge-cue" aria-hidden="true" />
        </div>
      </section>

      {/* ── role marquee ─────────────────────────────────────────────────── */}
      <section className="marquee-mask overflow-hidden border-y border-[var(--forge-line)] py-3.5" aria-hidden="true">
        <div ref={marqueeRef} className="flex w-max gap-3">
          {[...c.marquee, ...c.marquee].map((role, i) => (
            <span key={i} className="forge-stamp rounded-full px-4 py-1 font-mono text-[11px] uppercase tracking-[0.08em]">
              {role}
            </span>
          ))}
        </div>
      </section>

      {/* ── the scan: 7.4 seconds, scrubbed by scroll ────────────────────── */}
      <section ref={scanRef} className="relative overflow-hidden">
        <div className="mx-auto flex min-h-screen max-w-6xl flex-col justify-center px-6 py-24">
          <h2 data-reveal className="forge-display mb-14 text-[clamp(1.7rem,3.4vw,2.6rem)] font-semibold">
            {c.scanTitle}
          </h2>
          <div className="grid items-center gap-12 md:grid-cols-[1fr_auto]">
            <ol className="space-y-6">
              {c.scan.map(([time, label]) => (
                <li key={time} data-scan-item className="flex items-baseline gap-5">
                  <span className="w-[7.5rem] shrink-0 font-mono text-[12.5px] tabular-nums text-[var(--forge-hot)]">{time}</span>
                  <span className="text-[clamp(1.05rem,2vw,1.5rem)] font-medium leading-snug">{label}</span>
                </li>
              ))}
            </ol>
            <div
              ref={scanCounterRef}
              className="forge-display hidden select-none text-right text-[clamp(6rem,17vw,15rem)] font-bold leading-none tabular-nums md:block"
              aria-hidden="true"
            >
              {fmt(7.4, 1)}
            </div>
          </div>
          <div data-scan-verdict className="mt-16">
            <p className="forge-display text-[clamp(1.8rem,4.5vw,3.4rem)] font-bold leading-tight">
              <span className="molten">{c.scanVerdict}</span>
            </p>
            <p className="mt-4 max-w-xl text-[15px] leading-relaxed text-[var(--forge-dim)]">{c.scanVerdictSub}</p>
          </div>
        </div>
      </section>

      {/* ── facts band ───────────────────────────────────────────────────── */}
      <section className="border-y border-[var(--forge-line)] bg-[var(--forge-bg2)]">
        <div className="mx-auto grid max-w-6xl gap-8 px-6 py-12 sm:grid-cols-3">
          <div data-reveal className="flex items-baseline gap-3.5">
            <span data-count-to="7.4" data-decimals="1" data-suffix="s" className="forge-display text-4xl font-bold tabular-nums text-[var(--forge-hot)]">
              {fmt(7.4, 1)}s
            </span>
            <span className="text-[13px] leading-snug text-[var(--forge-dim)]">{c.statHuman}</span>
          </div>
          <div data-reveal="0.08" className="flex items-baseline gap-3.5">
            <span data-count-to="99" data-suffix="%" className="forge-display text-4xl font-bold tabular-nums">
              99%
            </span>
            <span className="text-[13px] leading-snug text-[var(--forge-dim)]">{c.statAts}</span>
          </div>
          <div data-reveal="0.16" className="flex items-baseline gap-3.5">
            <span data-count-to="0.2" data-decimals="1" data-suffix="s" className="forge-display text-4xl font-bold tabular-nums text-[var(--forge-hot)]">
              {fmt(0.2, 1)}s
            </span>
            <span className="text-[13px] leading-snug text-[var(--forge-dim)]">{c.statTypst}</span>
          </div>
        </div>
      </section>

      {/* ── how it works: sticky-stacked panels ──────────────────────────── */}
      <section aria-label={c.howTitle}>
        <div className="mx-auto max-w-6xl px-6 pt-24">
          <h2 data-reveal className="forge-display text-[clamp(1.7rem,3.4vw,2.6rem)] font-semibold">
            {c.howTitle}
          </h2>
        </div>
        {c.how.map(([title, body], i) => (
          <article key={title} className="forge-panel top-0" style={{ zIndex: i + 1 }}>
            <div className="mx-auto grid min-h-[72vh] max-w-6xl content-center items-center gap-12 px-6 py-20 md:grid-cols-2">
              <div>
                <div className="forge-display mb-6 text-[clamp(4rem,9vw,7rem)] font-bold leading-none text-[var(--forge-hot)] opacity-90">
                  {i + 1}
                </div>
                <h3 className="forge-display mb-4 text-[clamp(1.5rem,2.8vw,2.2rem)] font-semibold leading-tight">{title}</h3>
                <p className="max-w-md text-[15px] leading-relaxed text-[var(--forge-dim)]">{body}</p>
              </div>

              {/* one visual world per step */}
              {i === 0 && (
                <div data-reveal aria-hidden="true" className="rounded-lg border border-[var(--forge-line)] bg-black/25 p-6 font-mono text-[12px] leading-loose text-[var(--forge-faint)]">
                  <div className="mb-3 flex items-center gap-2">
                    <span className="size-2 rounded-full bg-[var(--forge-hot)]" />
                    <span className="uppercase tracking-[0.14em] text-[10px]">job-posting.txt</span>
                  </div>
                  {[92, 78, 85, 60, 88, 44].map((w, k) => (
                    <div key={k} className="my-2.5 h-[7px] rounded bg-[rgba(245,237,226,0.13)]" style={{ width: `${w}%` }} />
                  ))}
                  <span className="forge-caret" />
                </div>
              )}
              {i === 1 && (
                <div data-sheet aria-hidden="true" className="forge-sheet mx-auto w-full max-w-[300px] p-7">
                  <div className="mb-1.5 h-[10px] w-2/3 rounded bg-[#3a342c]" />
                  <div className="mb-5 h-[6px] w-1/3 rounded bg-[#b0a894]" />
                  {[100, 92, 96, 74, 0, 88, 95, 70, 0, 90, 82].map((w, k) =>
                    w === 0 ? (
                      <div key={k} className="mb-2 mt-4 h-[7px] w-1/4 rounded bg-[#c2551b]" />
                    ) : (
                      <div key={k} className="forge-sheet-line my-2" style={{ width: `${w}%` }} />
                    ),
                  )}
                </div>
              )}
              {i === 2 && (
                <div data-reveal aria-hidden="true" className="flex flex-col gap-3.5">
                  {c.howModes.map((mode, k) => (
                    <div
                      key={mode}
                      className="flex items-center justify-between rounded-lg border border-[var(--forge-line)] bg-black/25 px-5 py-4"
                      style={{ marginLeft: `${k * 10}%` }}
                    >
                      <span className="text-[14.5px] font-medium">{mode}</span>
                      <span className="font-mono text-[11px] text-[var(--forge-hot)]">{"~0" + decimal + "2s"}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </article>
        ))}
      </section>

      {/* ── feature ledger ───────────────────────────────────────────────── */}
      <section className="relative z-10 border-t border-[var(--forge-line)] bg-[var(--forge-bg)]">
        <div className="mx-auto max-w-6xl px-6 py-24">
          <h2 data-reveal className="forge-display mb-14 text-[clamp(1.7rem,3.4vw,2.6rem)] font-semibold">
            {c.featTitle}
          </h2>
          <div>
            {c.features.map(([title, body]) => (
              <div key={title} className="forge-ledger-row grid gap-3 py-9 md:grid-cols-[1fr_1.3fr] md:gap-12">
                <h3 className="forge-display text-[clamp(1.25rem,2.2vw,1.7rem)] font-semibold leading-snug">{title}</h3>
                <p className="max-w-2xl text-[14.5px] leading-relaxed text-[var(--forge-dim)]">{body}</p>
              </div>
            ))}
          </div>
          <p data-reveal className="mt-12 flex items-center gap-2.5 border-t border-[var(--forge-line)] pt-8 font-mono text-[12px] text-[var(--forge-faint)]">
            <Languages size={13} className="text-[var(--forge-hot)]" /> {c.languages}
          </p>
        </div>
      </section>

      {/* ── FAQ ──────────────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-3xl px-6 py-24">
        <h2 data-reveal className="forge-display mb-10 text-[clamp(1.7rem,3.4vw,2.6rem)] font-semibold">
          {c.faqTitle}
        </h2>
        <div data-reveal>
          {c.faq.map(([q, a]) => (
            <details key={q} className="group py-5">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-[15px] font-medium transition-colors hover:text-[var(--forge-hot)]">
                {q}
                <span className="font-mono text-[var(--forge-faint)] transition-transform duration-300 group-open:rotate-45">+</span>
              </summary>
              <p className="max-w-[68ch] pt-3.5 text-[14px] leading-relaxed text-[var(--forge-dim)]">{a}</p>
            </details>
          ))}
        </div>
      </section>

      {/* ── finale: the last ember ───────────────────────────────────────── */}
      <section className="forge-finale relative overflow-hidden">
        <Suspense fallback={null}>
          <ForgeScene density={140} floor={0.85} />
        </Suspense>
        <div className="relative z-10 mx-auto flex min-h-[80vh] max-w-4xl flex-col items-center justify-center px-6 py-28 text-center">
          <h2 data-reveal className="forge-display mb-10 text-[clamp(2.4rem,6.5vw,5rem)] font-bold leading-[1.02]">
            {c.title4}
          </h2>
          <Link
            ref={finaleCtaRef}
            data-reveal="0.1"
            to="/studio"
            className="btn-flame btn-flame--forge inline-block rounded-xl px-10 py-5 text-[17px] font-semibold"
          >
            {c.ctaPrimary}
          </Link>
          <p data-reveal="0.18" className="mt-7 font-mono text-[11.5px] text-[var(--forge-faint)]">{c.ctaNote}</p>
        </div>
      </section>

      {/* ── footer ───────────────────────────────────────────────────────── */}
      <footer className="relative z-10 border-t border-[var(--forge-line)] bg-[var(--forge-bg)]">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 py-8">
          <p className="flex items-center gap-2.5 text-[14px] font-medium text-[var(--forge-dim)]">
            <img src={logoUrl} alt="" className="size-6" aria-hidden="true" />
            {c.footerBlurb}
          </p>
          <p className="font-mono text-[11px] text-[var(--forge-faint)]">
            © {new Date().getFullYear()} cvglowup.com
            {me?.authenticated ? "" : " · GDPR-friendly · no tracking ads on paid plans"}
          </p>
        </div>
      </footer>
    </div>
  );
}
