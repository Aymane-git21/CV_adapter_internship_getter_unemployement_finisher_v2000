"""All prompts in one place. Every generation call uses structured output
(response_schema), so prompts focus on quality, not output formatting."""
from . import typst_ref

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


_INTENSITY_MANDATES: dict[str, str] = {
    "reshape": """You are an EDITOR, not a writer: do NOT rewrite the wording. Every summary
sentence and every bullet keeps the candidate's own phrasing, apart from
minimal grammar fixes. Your job is structure only: reorder sections and
bullets so the most job-relevant come first, group skills sensibly, and trim
redundancy. Where a rule below asks for rewritten or stronger wording, this
mandate wins: the original phrasing stays.""",
    "minor": """Make MINOR changes only: keep most of the candidate's phrasing. Reorder
content for relevance, tighten wording, and surface skills already present
in the master CV that match the role. Do not restructure roles and do not
write new bullets. Where a rule below asks for fully rewritten wording, this
mandate wins: stay close to the original.""",
    "major": """You are a WRITER, not a copyist. Returning master bullets verbatim or with
one word swapped is a failed output. Every summary sentence and every bullet
must be rewritten in fresh, confident wording that sells the candidate for
THIS job.""",
    "max_ats": """You are a WRITER, not a copyist. Returning master bullets verbatim or with
one word swapped is a failed output. Every summary sentence and every bullet
must be rewritten in fresh, confident wording that sells the candidate for
THIS job.

MAXIMIZE ATS COVERAGE: every keyword from the list below that the master CV
truthfully supports must appear VERBATIM, or via its standard alias. Mirror
the job post's terminology and retitle skill groups to standard names. A
keyword with no support in the master CV must NOT appear.""",
}


def tailor_cv_prompt(
    jd: str, analysis_notes: str, keywords: list[str], master_json: str, language: str,
    rewrite_intensity: str = "major",
) -> str:
    mandate = _INTENSITY_MANDATES.get(rewrite_intensity, _INTENSITY_MANDATES["major"])
    return f"""You are an elite CV writer. Rewrite the candidate's master CV so it is
laser-targeted at the job below, in {lang_name(language)}.

{mandate}

TRUTH BOUNDARY, facts vs wording:
- FACTS are locked: employers, role titles, dates, degrees, certifications,
  numbers/metrics, and technologies must all come from the master CV. Never
  add a number, tool, employer, or credential that is not there.
- WORDING is yours: upgrade weak verbs, cut filler, and spell out the scope,
  impact, and purpose a terse bullet already implies. "Built data pipelines"
  may become "Designed and shipped data pipelines feeding the team's
  production models" when the master CV supports it, but it may NOT gain
  "cutting costs 30%" unless that number is in the master CV.

HARD RULES — violating any of these makes the output unusable:
1. NEVER invent experiences, employers, dates, degrees, or numbers that are
   not in the master CV.
2. ONE PAGE, and the page has a measured budget. Count CONTENT LINES: every
   experience bullet plus every project description. Start from 12 and
   subtract, because the rest of the CV eats the same page:
     - 1 for each experience entry beyond 3
     - 1 for each education entry beyond 2
     - 1 for each skill group beyond 3
   Hard caps regardless: at most 4 experience entries, at most 3 projects.
   These come from compiling the real template, where a lean CV carries 15
   content lines and one with 4 roles, 3 degrees and 4 skill groups carries
   only 8. Spend what you have where it wins THIS job: 4-5 lines on the most
   relevant role, 1-2 on the oldest, and drop any project a stronger
   experience bullet already proves. Cutting is the job, not a failure. Do
   not pad to reach the budget either: a half-empty page fails just as hard
   as one that overflows.
3. Weave the job's key terms in naturally WHERE THE CANDIDATE GENUINELY HAS
   the skill: {", ".join(keywords[:14])}.
4. headline: mirror the target role's title language (without lying about
   seniority). Do not promise a specialism the bullets never evidence: if the
   headline names a domain, something below it must prove the candidate has
   touched that domain.
5. summary: 2-3 sentences that SELL. Open with the candidate's strongest
   identity claim for this role, then the 1-2 proof points this employer
   cares about most. At least one concrete anchor (a number, a named system,
   or a real scale) must appear, taken from the master CV. Zero hedging, no
   "passionate" / "motivated" / "adaptable" filler. It must read noticeably
   stronger than the master summary, not a paraphrase of it.
6. bullets: 14-24 words each, opening with a strong past-tense verb. Length is
   page budget: a bullet under ~14 words occupies one printed line, a longer
   one occupies two, so every wasted word costs space a real fact could use.
   VARY THE
   SHAPE across the CV: AT MOST HALF the bullets may close on a purpose clause
   ("to reduce X", "ensuring Y", "enabling Z"); the rest must land on a result,
   a scale, or the thing itself. Two consecutive bullets may not both close
   that way, and no two bullets in the same entry may open with the same verb. A bullet that says what was built, at
   what scale, and what changed beats one that says what it was for. Use real
   metrics from the master CV wherever they exist; where they do not, state
   concrete scope (systems, teams, volumes, users) instead, and never invent
   a number. Expand a thin master bullet (under 10 words) by unpacking what
   it already implies; tighten a rambling one.
7. BANNED WORDING. Do not introduce these words: robust, critical, strict,
   advanced, comprehensive, cutting-edge, state-of-the-art, seamless,
   high-integrity, high-availability, production-grade, highly reliable,
   leverage, spearhead, passionate, dynamic, innovative, synergy. Keep such a
   word only if the master CV already used it for that fact. Delete any
   adjective whose removal costs no information: "automated test-gated CI/CD
   pipelines guaranteeing robust delivery" is worse than "test-gated CI/CD
   pipelines that cut release time from days to hours".
8. skills: every item must be defensible. List a skill only when the master
   CV evidences it, in a bullet, a project, a degree, or its own skills list.
   Never list a competence the candidate could not be questioned on for five
   minutes. Reorder so the most job-relevant come first and drop the rest.
9. education: degree, school, dates and location carry the entry. Add a
   details line only when it earns the space (a thesis, honours, a genuinely
   relevant specialism). Never write a generic "studied X, Y and Z" line.
10. Keep contacts and full_name exactly as in the master CV.
11. Write every field in {lang_name(language)}.
12. Never use an em dash (—) in any field. Use a comma, colon, period, or
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
    return f"""You are editing a Typst document. Apply the instruction and return the
COMPLETE updated source file, nothing else.

{typst_ref.TYPST_PRIMER}

RULES:
- Change only what the instruction requires; keep everything else intact.
- Keep the #import line and the final #render(...) call unless the
  instruction requires changing them (e.g. switching template).
- The result must compile: balance every parenthesis and bracket, keep
  single-element arrays as ("x",), keep strings double-quoted.

INSTRUCTION: {instruction}

CURRENT SOURCE:
```typst
{source}
```
Return only the raw updated source (no fences)."""


def repair_source_prompt(source: str, diagnostics: str) -> str:
    return f"""The Typst source below fails to compile. Fix it with the SMALLEST
possible change and return the COMPLETE corrected source, nothing else.
Do not rewrite or restructure anything the errors do not require.

{typst_ref.TYPST_PRIMER}

COMPILER ERRORS:
{diagnostics}

SOURCE:
```typst
{source}
```
Return only the raw corrected source (no fences)."""


def edit_message_prompt(text: str, instruction: str) -> str:
    return f"""You are editing a short outreach message (plain text, no markup).
Apply the instruction and return ONLY the complete updated message text.
Keep it under 700 characters, keep real facts unchanged, never use an em
dash (—); use a comma, colon, or period instead.

INSTRUCTION: {instruction}

CURRENT MESSAGE:
{text}"""
