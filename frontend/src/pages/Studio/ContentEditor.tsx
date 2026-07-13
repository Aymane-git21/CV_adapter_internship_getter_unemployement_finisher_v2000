/* Structured editor — CV form, letter form, or outreach message. */
import { Plus, Trash2 } from "lucide-react";
import type { CVData, LetterData } from "../../api";
import { useI18n } from "../../i18n";
import type { DocController } from "./useDocument";

const inputCls =
  "w-full rounded-md border border-black/10 glass-panel px-2.5 py-2 text-[13px] placeholder:text-text/50 focus:border-flame-500";
const areaCls = `${inputCls} resize-y leading-relaxed`;

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block font-mono text-[10.5px] uppercase tracking-wider text-text/50">{label}</span>
      {children}
    </label>
  );
}

function Section({ title, onAdd, addLabel, children }: {
  title: string; onAdd?: () => void; addLabel?: string; children: React.ReactNode;
}) {
  return (
    <section className="border-b border-black/10 px-4 py-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="eyebrow">{title}</h3>
        {onAdd && (
          <button onClick={onAdd} className="flex items-center gap-1 text-[12px] text-primary/80 hover:text-flame-400">
            <Plus size={12} /> {addLabel}
          </button>
        )}
      </div>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

function EntryCard({ onRemove, children }: { onRemove: () => void; children: React.ReactNode }) {
  return (
    <div className="relative rounded-lg border border-black/10 glass-panel/60 p-3">
      <button
        onClick={onRemove}
        className="absolute right-2 top-2 rounded p-1 text-text/50 hover:bg-ink-700 hover:text-danger"
        aria-label="Remove entry"
      >
        <Trash2 size={12} />
      </button>
      <div className="space-y-2.5">{children}</div>
    </div>
  );
}

/* ── CV form ─────────────────────────────────────────────────────────────── */

function CVForm({ ctl }: { ctl: DocController }) {
  const { t } = useI18n();
  const data = ctl.doc?.data as CVData;
  const set = (patch: Partial<CVData>) => ctl.updateData({ ...data, ...patch });

  const upd = <K extends keyof CVData>(key: K, idx: number, patch: object) => {
    const arr = [...(data[key] as object[])];
    arr[idx] = { ...arr[idx], ...patch };
    set({ [key]: arr } as Partial<CVData>);
  };
  const rm = <K extends keyof CVData>(key: K, idx: number) =>
    set({ [key]: (data[key] as object[]).filter((_, i) => i !== idx) } as Partial<CVData>);
  const add = <K extends keyof CVData>(key: K, item: object) =>
    set({ [key]: [...(data[key] as object[]), item] } as Partial<CVData>);

  return (
    <div>
      <Section title={t("ed.identity")}>
        <div className="grid grid-cols-2 gap-2.5">
          <Field label={t("ed.fullName")}>
            <input className={inputCls} value={data.full_name} onChange={(e) => set({ full_name: e.target.value })} />
          </Field>
          <Field label={t("ed.headline")}>
            <input className={inputCls} value={data.headline} onChange={(e) => set({ headline: e.target.value })} />
          </Field>
        </div>
        <Field label={t("ed.summary")}>
          <textarea rows={3} className={areaCls} value={data.summary} onChange={(e) => set({ summary: e.target.value })} />
        </Field>
        <div className="grid grid-cols-2 gap-2.5">
          {(["email", "phone", "location", "linkedin", "github", "website"] as const).map((k) => (
            <Field key={k} label={k}>
              <input
                className={inputCls}
                value={data.contacts[k]}
                onChange={(e) => set({ contacts: { ...data.contacts, [k]: e.target.value } })}
              />
            </Field>
          ))}
        </div>
      </Section>

      <Section
        title={t("ed.experience")}
        addLabel={t("ed.addEntry")}
        onAdd={() => add("experience", { title: "", company: "", location: "", start: "", end: "", bullets: [] })}
      >
        {data.experience.map((job, i) => (
          <EntryCard key={i} onRemove={() => rm("experience", i)}>
            <div className="grid grid-cols-2 gap-2.5 pr-6">
              <input className={inputCls} placeholder="Title" value={job.title} onChange={(e) => upd("experience", i, { title: e.target.value })} />
              <input className={inputCls} placeholder="Company" value={job.company} onChange={(e) => upd("experience", i, { company: e.target.value })} />
            </div>
            <div className="grid grid-cols-3 gap-2.5">
              <input className={inputCls} placeholder="Start" value={job.start} onChange={(e) => upd("experience", i, { start: e.target.value })} />
              <input className={inputCls} placeholder="End" value={job.end} onChange={(e) => upd("experience", i, { end: e.target.value })} />
              <input className={inputCls} placeholder="Location" value={job.location} onChange={(e) => upd("experience", i, { location: e.target.value })} />
            </div>
            <Field label={t("ed.bullets")}>
              <textarea
                rows={3}
                className={areaCls}
                value={job.bullets.join("\n")}
                onChange={(e) => upd("experience", i, { bullets: e.target.value.split("\n").filter((b) => b.trim() !== "" || e.target.value.endsWith("\n")) })}
              />
            </Field>
          </EntryCard>
        ))}
      </Section>

      <Section
        title={t("ed.education")}
        addLabel={t("ed.addEntry")}
        onAdd={() => add("education", { degree: "", school: "", location: "", start: "", end: "", details: [] })}
      >
        {data.education.map((ed, i) => (
          <EntryCard key={i} onRemove={() => rm("education", i)}>
            <div className="grid grid-cols-2 gap-2.5 pr-6">
              <input className={inputCls} placeholder="Degree" value={ed.degree} onChange={(e) => upd("education", i, { degree: e.target.value })} />
              <input className={inputCls} placeholder="School" value={ed.school} onChange={(e) => upd("education", i, { school: e.target.value })} />
            </div>
            <div className="grid grid-cols-3 gap-2.5">
              <input className={inputCls} placeholder="Start" value={ed.start} onChange={(e) => upd("education", i, { start: e.target.value })} />
              <input className={inputCls} placeholder="End" value={ed.end} onChange={(e) => upd("education", i, { end: e.target.value })} />
              <input className={inputCls} placeholder="Location" value={ed.location} onChange={(e) => upd("education", i, { location: e.target.value })} />
            </div>
          </EntryCard>
        ))}
      </Section>

      <Section
        title={t("ed.skills")}
        addLabel={t("ed.addEntry")}
        onAdd={() => add("skills", { category: "", items: [] })}
      >
        {data.skills.map((g, i) => (
          <EntryCard key={i} onRemove={() => rm("skills", i)}>
            <div className="grid grid-cols-[1fr_2fr] gap-2.5 pr-6">
              <input className={inputCls} placeholder="Category" value={g.category} onChange={(e) => upd("skills", i, { category: e.target.value })} />
              <input
                className={inputCls}
                placeholder="item, item, item"
                value={g.items.join(", ")}
                onChange={(e) => upd("skills", i, { items: e.target.value.split(",").map((s) => s.trimStart()) })}
              />
            </div>
          </EntryCard>
        ))}
      </Section>

      <Section
        title={t("ed.projects")}
        addLabel={t("ed.addEntry")}
        onAdd={() => add("projects", { name: "", tech: "", description: "" })}
      >
        {data.projects.map((p, i) => (
          <EntryCard key={i} onRemove={() => rm("projects", i)}>
            <div className="grid grid-cols-2 gap-2.5 pr-6">
              <input className={inputCls} placeholder="Name" value={p.name} onChange={(e) => upd("projects", i, { name: e.target.value })} />
              <input className={inputCls} placeholder="Tech" value={p.tech} onChange={(e) => upd("projects", i, { tech: e.target.value })} />
            </div>
            <input className={inputCls} placeholder="Description" value={p.description} onChange={(e) => upd("projects", i, { description: e.target.value })} />
          </EntryCard>
        ))}
      </Section>

      <Section title={`${t("ed.languages")} · ${t("ed.interests")}`}>
        <div className="grid grid-cols-2 gap-2.5">
          <Field label={t("ed.languages")}>
            <textarea
              rows={3}
              className={areaCls}
              placeholder="French | native"
              value={data.languages.map((l) => (l.level ? `${l.name} | ${l.level}` : l.name)).join("\n")}
              onChange={(e) =>
                set({
                  languages: e.target.value.split("\n").filter(Boolean).map((line) => {
                    // "|" is the documented separator; "—" kept for old muscle memory
                    const [name, level = ""] = line.split(/[|—]/).map((s) => s.trim());
                    return { name, level };
                  }),
                })
              }
            />
          </Field>
          <Field label={t("ed.interests")}>
            <textarea
              rows={3}
              className={areaCls}
              value={data.interests.join("\n")}
              onChange={(e) => set({ interests: e.target.value.split("\n").filter((s, i, a) => s.trim() !== "" || i === a.length - 1) })}
            />
          </Field>
        </div>
      </Section>
    </div>
  );
}

/* ── Letter form ─────────────────────────────────────────────────────────── */

function LetterForm({ ctl }: { ctl: DocController }) {
  const { t } = useI18n();
  const data = ctl.doc?.data as LetterData;
  const set = (patch: Partial<LetterData>) => ctl.updateData({ ...data, ...patch });

  return (
    <div>
      <Section title={t("ed.recipient")}>
        <div className="grid grid-cols-2 gap-2.5">
          <input className={inputCls} placeholder="Name" value={data.recipient.name}
            onChange={(e) => set({ recipient: { ...data.recipient, name: e.target.value } })} />
          <input className={inputCls} placeholder="Company" value={data.recipient.company}
            onChange={(e) => set({ recipient: { ...data.recipient, company: e.target.value } })} />
        </div>
        <textarea rows={2} className={areaCls} placeholder="Address lines"
          value={data.recipient.address_lines.join("\n")}
          onChange={(e) => set({ recipient: { ...data.recipient, address_lines: e.target.value.split("\n") } })} />
      </Section>
      <Section title={t("ed.subject")}>
        <input className={inputCls} value={data.subject} onChange={(e) => set({ subject: e.target.value })} />
        <input className={inputCls} placeholder={t("ed.greeting")} value={data.greeting}
          onChange={(e) => set({ greeting: e.target.value })} />
      </Section>
      <Section title={t("ed.paragraphs")} addLabel={t("ed.addEntry")}
        onAdd={() => set({ paragraphs: [...data.paragraphs, ""] })}>
        {data.paragraphs.map((p, i) => (
          <EntryCard key={i} onRemove={() => set({ paragraphs: data.paragraphs.filter((_, j) => j !== i) })}>
            <textarea rows={4} className={`${areaCls} pr-5`} value={p}
              onChange={(e) => set({ paragraphs: data.paragraphs.map((x, j) => (j === i ? e.target.value : x)) })} />
          </EntryCard>
        ))}
      </Section>
      <Section title={t("ed.closing")}>
        <input className={inputCls} value={data.closing} onChange={(e) => set({ closing: e.target.value })} />
      </Section>
    </div>
  );
}

/* ── Message ─────────────────────────────────────────────────────────────── */

function MessageForm({ ctl }: { ctl: DocController }) {
  const { t } = useI18n();
  const doc = ctl.doc!;
  return (
    <Section title={t("ed.messageText")}>
      <textarea
        rows={14}
        className={areaCls}
        value={doc.text_content ?? ""}
        onChange={(e) => ctl.updateText(e.target.value)}
      />
      <button
        onClick={() => void navigator.clipboard.writeText(doc.text_content ?? "")}
        className="rounded-md border border-black/10 px-3 py-1.5 text-[13px] text-text/70 hover:border-ink-600 hover:text-text"
      >
        {t("studio.copy")}
      </button>
    </Section>
  );
}

export function ContentEditor({ ctl }: { ctl: DocController }) {
  const doc = ctl.doc;
  if (!doc) return null;
  return (
    <div className="h-full overflow-y-auto pb-10">
      {doc.kind === "cv" && doc.data && <CVForm ctl={ctl} />}
      {doc.kind === "letter" && doc.data && <LetterForm ctl={ctl} />}
      {doc.kind === "message" && <MessageForm ctl={ctl} />}
    </div>
  );
}
