"""All prompts in one place. Every generation call uses structured output
(response_schema), so prompts focus on quality, not output formatting."""

LANG_NAMES = {"en": "English", "fr": "French", "de": "German"}


def lang_name(code: str) -> str:
    return LANG_NAMES.get(code, "English")


def analyze_prompt(jd: str, cv_text: str) -> str:
    return f"""You are an expert technical recruiter and ATS specialist.

Analyze the JOB DESCRIPTION below (the CANDIDATE CV is given for context only).

Extract:
- job_title: the role title, concise.
- company: the hiring company name ("" if not stated).
- language_detected: "fr" if the job description is French, "de" if German,
  else "en".
- keywords: 12-20 concrete skills/requirements a screening system would scan
  for. Each has term (short, canonical), weight 1-3 (3 = must-have, appears
  repeatedly or in requirements; 1 = nice-to-have), and aliases (other
  spellings/forms likely to appear in a CV, e.g. "k8s" for "Kubernetes",
  "GCP" for "Google Cloud"). Prefer specific technologies and competencies
  over fluffy words.
- recipient_name: the named hiring contact if present, else "".
- recipient_address_lines: postal address lines for the company if present,
  else [].
- notes: 1-2 sentences on what this employer cares about most.

JOB DESCRIPTION:
{jd}

CANDIDATE CV (context):
{cv_text[:6000]}
"""


def parse_cv_prompt(language: str) -> str:
    return f"""Extract this CV/resume into the structured schema, faithfully.

Rules:
- Do NOT invent, embellish, or omit experiences. Transcribe what is there.
- Keep bullet wording close to the original, cleaned of layout artifacts.
- Dates: keep the original display style (e.g. "Mar 2024", "2021 – 2024").
- Group skills into 2-4 sensible categories if the CV lists them flat.
- Write field values in {lang_name(language)} if the CV is in that language;
  otherwise keep the CV's own language.
- contacts: extract email/phone/location/linkedin/github/website when present.
"""


def tailor_cv_prompt(jd: str, analysis_notes: str, keywords: list[str], master_json: str, language: str) -> str:
    return f"""You are an elite CV writer. Rewrite the candidate's master CV so it is
laser-targeted at the job below, in {lang_name(language)}.

HARD RULES — violating any of these makes the output unusable:
1. NEVER invent experiences, employers, dates, degrees, or numbers that are
   not in the master CV. You may rephrase, reorder, emphasize, and cut.
2. Target ONE FULL PAGE of content, no more and not visibly less. When the
   master CV has the material, keep 3-5 experience entries with 3-4 bullets
   each (bullets under 28 words) and keep education, projects, languages and
   certifications. Only cut when the page would overflow; never shrink a
   rich CV to a half-empty page.
3. Weave the job's key terms in naturally WHERE THE CANDIDATE GENUINELY HAS
   the skill: {", ".join(keywords[:14])}.
4. headline: mirror the target role's title language (without lying about
   seniority).
5. summary: 2-3 punchy sentences targeted at THIS job, with the candidate's
   strongest relevant proof points.
6. bullets: start with strong verbs, include real metrics from the master CV
   when available.
7. skills: reorganize so the most job-relevant items come first; drop
   irrelevant ones if space demands.
8. Keep contacts and full_name exactly as in the master CV.
9. Write every field in {lang_name(language)}.
10. Never use an em dash (—) in any field. Use a comma, colon, period, or
   " | " instead.

WHAT THIS EMPLOYER CARES ABOUT: {analysis_notes}

JOB DESCRIPTION:
{jd}

MASTER CV (single source of truth — JSON):
{master_json}
"""


def letter_prompt(jd: str, analysis_notes: str, cv_json: str, language: str) -> str:
    doc_name = {"fr": "lettre de motivation", "de": "Anschreiben"}.get(language, "cover letter")
    default_recipient = {
        "fr": '"Madame, Monsieur"',
        "de": '"Sehr geehrte Damen und Herren"',
    }.get(language, '"Hiring Team"')
    subject_hint = {
        "fr": ' (e.g. "Objet : Candidature au poste de ...")',
        "de": ' (e.g. "Bewerbung als ...")',
    }.get(language, "")
    return f"""Write an outstanding cover letter ({doc_name})
in {lang_name(language)} for the job below, from the candidate described by the CV JSON.

Fill ONLY these fields (the system fills sender/date/signature):
- recipient: name (use the hiring contact if known, else a natural default
  like {default_recipient}), company, address_lines (from the job posting if present).
- subject: one line, mentions the exact role title{subject_hint}.
- greeting: culturally correct salutation.
- paragraphs: exactly 3 paragraphs, 60-100 words each:
  P1 hook — why this company/role specifically, with the candidate's single
  strongest relevant achievement up front. No "I am writing to apply".
  P2 proof — 2-3 concrete results from the CV mapped to the job's needs.
  Use real numbers from the CV only.
  P3 close — what the candidate will bring, confident call to action.
- closing: culturally correct closing line{
        {"fr": " (formule de politesse complète)", "de": ' (e.g. "Mit freundlichen Grüßen")'}.get(language, "")
    }.

Tone: confident, specific, human. Zero clichés, zero placeholders.
Never use an em dash (—) anywhere; use a comma, colon, or period instead.
WHAT THIS EMPLOYER CARES ABOUT: {analysis_notes}

JOB DESCRIPTION:
{jd}

CANDIDATE CV (JSON):
{cv_json}
"""


def outreach_prompt(jd: str, cv_json: str, language: str) -> str:
    return f"""Write a short LinkedIn outreach message (under 700 characters) in
{lang_name(language)} from the candidate to a recruiter about the job below.

Rules: mention the exact role, one concrete relevant achievement with a real
number from the CV, end with a soft ask (15-min chat). No placeholders: if
no recruiter name is known, open naturally without one. Never use an em dash
(—); use a comma, colon, or period instead. Return ONLY the message text.

JOB DESCRIPTION:
{jd[:4000]}

CANDIDATE CV (JSON):
{cv_json}
"""


def edit_cv_prompt(cv_json: str, instruction: str, language: str) -> str:
    return f"""You are editing a candidate's CV data. Apply the instruction below and
return the COMPLETE updated CV in the same schema. Change only what the
instruction requires; keep everything else byte-identical. Never invent
facts. Never use an em dash (—) in text you write; use a comma, colon, or
period instead. Keep the document's language ({lang_name(language)}) unless asked to translate.

INSTRUCTION: {instruction}

CURRENT CV (JSON):
{cv_json}
"""


def edit_letter_prompt(letter_json: str, instruction: str, language: str) -> str:
    return f"""You are editing a cover letter. Apply the instruction and return the
COMPLETE updated letter in the same schema. Change only what is required;
keep the rest identical. Language: {lang_name(language)} unless asked to translate.

INSTRUCTION: {instruction}

CURRENT LETTER (JSON):
{letter_json}
"""


def edit_source_prompt(source: str, instruction: str) -> str:
    return f"""You are editing a Typst document (typst.app markup language, NOT LaTeX).
Apply the instruction and return the COMPLETE updated source file, nothing else.

Rules:
- Keep the #import line and overall structure intact unless asked otherwise.
- Only valid Typst syntax; data lives in the `data` dict literal.
- Strings use double quotes; escape inner quotes as \\".

INSTRUCTION: {instruction}

CURRENT SOURCE:
```typst
{source}
```
Return only the raw updated source (no fences)."""
