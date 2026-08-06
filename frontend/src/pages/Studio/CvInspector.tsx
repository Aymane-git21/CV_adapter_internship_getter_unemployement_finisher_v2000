/* Read-only viewer for the data stored on a saved master CV. Opens under the
   chip row in NewJobPanel so the user can check what a CV holds before
   tailoring with it. */
import { X } from "lucide-react";
import type { ReactNode } from "react";
import type { MasterCVMeta } from "../../api";
import { useI18n } from "../../i18n";

function Section({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <p className="mb-1 font-mono text-[10px] uppercase tracking-wider text-text/50">{label}</p>
      {children}
    </div>
  );
}

export function CvInspector({ cv, onClose }: { cv: MasterCVMeta; onClose: () => void }) {
  const { t } = useI18n();
  const d = cv.data;
  const contacts = d
    ? [d.contacts.email, d.contacts.phone, d.contacts.location, d.contacts.linkedin, d.contacts.github, d.contacts.website].filter(Boolean)
    : [];

  return (
    <div className="mt-3 rounded-lg border border-black/10 glass-panel">
      <div className="flex items-center justify-between border-b border-black/10 px-4 py-2.5">
        <p className="eyebrow">
          {t("studio.cv.data.title")}
          <span className="ml-2 normal-case tracking-normal text-text/50">{cv.name}</span>
        </p>
        <button
          onClick={onClose}
          className="rounded p-1 text-text/50 hover:bg-ink-700 hover:text-text"
          aria-label={t("studio.close")}
        >
          <X size={14} />
        </button>
      </div>

      {!d ? (
        <p className="px-4 py-3 text-[13px] text-text/60">{t("studio.cv.data.empty")}</p>
      ) : (
        <div className="max-h-80 space-y-4 overflow-y-auto p-4 text-[13px] leading-relaxed">
          <div>
            <p className="font-medium">{d.full_name || "·"}</p>
            {d.headline && <p className="text-text/70">{d.headline}</p>}
            {contacts.length > 0 && (
              <p className="mt-1 break-words font-mono text-[11px] text-text/50">{contacts.join(" · ")}</p>
            )}
          </div>

          {d.summary && (
            <Section label={t("ed.summary")}>
              <p className="text-text/80">{d.summary}</p>
            </Section>
          )}

          {d.experience.length > 0 && (
            <Section label={t("ed.experience")}>
              <div className="space-y-2.5">
                {d.experience.map((x, i) => (
                  <div key={i}>
                    <div className="flex items-baseline justify-between gap-3">
                      <p className="font-medium">
                        {x.title}
                        {x.company && <span className="font-normal text-text/70"> · {x.company}</span>}
                      </p>
                      {(x.start || x.end) && (
                        <p className="shrink-0 font-mono text-[11px] text-text/50">{[x.start, x.end].filter(Boolean).join("–")}</p>
                      )}
                    </div>
                    {x.bullets.length > 0 && (
                      <ul className="mt-0.5 list-disc space-y-0.5 pl-4 text-text/80">
                        {x.bullets.map((b, j) => <li key={j}>{b}</li>)}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            </Section>
          )}

          {d.education.length > 0 && (
            <Section label={t("ed.education")}>
              <div className="space-y-1.5">
                {d.education.map((e, i) => (
                  <div key={i} className="flex items-baseline justify-between gap-3">
                    <p>
                      {e.degree}
                      {e.school && <span className="text-text/70"> · {e.school}</span>}
                    </p>
                    {(e.start || e.end) && (
                      <p className="shrink-0 font-mono text-[11px] text-text/50">{[e.start, e.end].filter(Boolean).join("–")}</p>
                    )}
                  </div>
                ))}
              </div>
            </Section>
          )}

          {d.skills.length > 0 && (
            <Section label={t("ed.skills")}>
              <div className="space-y-0.5 text-text/80">
                {d.skills.map((g, i) => (
                  <p key={i}>
                    {g.category && <span className="text-text/60">{g.category}: </span>}
                    {g.items.join(", ")}
                  </p>
                ))}
              </div>
            </Section>
          )}

          {d.projects.length > 0 && (
            <Section label={t("ed.projects")}>
              <div className="space-y-1.5 text-text/80">
                {d.projects.map((p, i) => (
                  <p key={i}>
                    <span className="font-medium text-text">{p.name}</span>
                    {p.tech && <span className="font-mono text-[11px] text-text/50"> ({p.tech})</span>}
                    {p.description && <span> {p.description}</span>}
                  </p>
                ))}
              </div>
            </Section>
          )}

          {d.languages.length > 0 && (
            <Section label={t("ed.languages")}>
              <p className="text-text/80">
                {d.languages.map((l) => (l.level ? `${l.name} (${l.level})` : l.name)).join(", ")}
              </p>
            </Section>
          )}

          {d.certifications.length > 0 && (
            <Section label={t("studio.cv.data.certifications")}>
              <div className="space-y-0.5 text-text/80">
                {d.certifications.map((c, i) => (
                  <p key={i}>{[c.name, c.issuer, c.year].filter(Boolean).join(" · ")}</p>
                ))}
              </div>
            </Section>
          )}

          {d.interests.length > 0 && (
            <Section label={t("studio.cv.data.interests")}>
              <p className="text-text/80">{d.interests.join(", ")}</p>
            </Section>
          )}
        </div>
      )}
    </div>
  );
}
