import os
os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "true"
os.environ["GRPC_POLL_STRATEGY"] = "poll"
os.environ["NO_GCE_CHECK"] = "true"
os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
import sys
import re
import time
import json
import subprocess
import concurrent.futures
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

# Job Description provided by the user
job_description = """
localisation : Pantin (93)

Au sein de notre DSI Groupe, l'équipe Core IA conçoit, modélise et développe les solutions d'Intelligence Artificielle transverses pour l'ensemble des domaines métiers et fonctions d'Hermès.

Sous la responsabilité du Responsable Core IA, vous jouez un rôle clé dans la concrétisation de la vision algorithmique de la maison en traduisant les besoins métiers en solutions d'IA performantes et industrialisées.

Missions principales

Évaluer la faisabilité technique des cas d'usage IA en amont de tout engagement projet
Concevoir les architectures de solutions IA de bout en bout : choix du modèle LLM, base de données (vector store, Feature Store, SQL/NoSQL), patterns d'intégration, exposition API et front-end
Définir le contrat d'intégration des modèles ML à destination du Lead ML Engineer
Concevoir des solutions pensées pour leur exploitabilité dès l'origine (seuils de drift, stratégies de rollback, runbooks) dont le Lead ML Engineer assurera l'opération
Piloter le delivery des projets IA en coordination avec les Data Scientists, le Lead ML Engineer et les Product Manager
Maintenir les designs de référence AI : catalogue de patterns validés, recommandations technologiques, arbitrages make-vs-buy sur les composants IA
Contribuer à la Gouvernance IA de la Maison sur les volets relevant de son expertise
Soumettre les choix d'architecture structurants à la Design Authority et défendre ses propositions ; intégrer les retours de validation dans les designs
Contribuer activement à l'évolution de SecuredGPT et être un utilisateur de référence de LLMHub pour remonter les besoins terrain
Assurer la veille technologique IA de la Direction Data
Anticiper les évolutions de l'écosystème et traduire ces perspectives en orientations concrètes pour la roadmap IA de la Maison
Faciliter la collaboration entre l'équipe Core AI, le Lead ML Engineer et la Design Authority pour garantir la cohérence technique de bout en bout

Profil souhaité

5 ans d'expériences minimum en ingénierie IA ou architecture de solutions data, avec une exposition aux projets ML en production
Maîtrise des architectures cloud et des patterns de déploiement IA, du modèle jusqu'au front-end
Expertise des LLM et de leurs patterns d'usage : RAG, agents, function calling, évaluation, optimisation
Connaissance des bases de données modernes et des pratiques MLOps suffisante pour concevoir des architectures exploitables
Capacité à produire des dossiers d'architecture rigoureux et à les défendre face à une Design Authority technique
Aptitude à maintenir une veille technologique structurée et à en extraire des orientations actionnables
Sens de la pédagogie pour dialogue avec des Data Scientists, un Lead ML Engineer, des métiers et une Design Authority

Employeur responsable, nous nous engageons dans l'éthique, les diversités et l'inclusion, rejoignez l'aventure d'Hermès !

"Créateur, artisan et marchand d’objets de haute qualité, Hermès est, depuis 1837, une maison française, familiale et indépendante qui emploie près de 25 185 collaborateurs dans le monde. Animé par un esprit d’entreprendre continu et une exigence constante, Hermès cultive la liberté et l’autonomie de chacun grâce à un management responsable. L’entreprise perpétue la transmission de savoir-faire d’exception par un ancrage territorial fort dans le respect des hommes et de la nature – source de matières d’exception. Seize métiers artisanaux irriguent la créativité de la maison dont les collections rayonnent dans près 300 magasins dans le monde."
"""

def clean_markdown(text):
    if text.startswith("```latex"): text = text[8:]
    elif text.startswith("```json"): text = text[7:]
    elif text.startswith("```"): text = text[3:]
    if text.endswith("```"): text = text[:-3]
    text = text.replace("**", "")
    return text.strip()

def extract_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except:
                pass
    return None

def compile_latex(file_path, output_dir):
    pdflatex_cmd = 'pdflatex'
    if os.name == 'nt':  # Windows
        potential_path = r'C:\Users\ayman\AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe'
        if os.path.exists(potential_path):
            pdflatex_cmd = potential_path
            
    result = subprocess.run(
        [pdflatex_cmd, '-interaction=nonstopmode', '-output-directory', output_dir, file_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
        check=False
    )
    
    stdout_str = result.stdout.decode('utf-8', errors='replace')
    stderr_str = result.stderr.decode('utf-8', errors='replace')
    
    if result.returncode != 0:
        full_log = stdout_str + stderr_str
        error_lines = [line for line in full_log.split('\n') if line.strip().startswith('!') or "Fatal error" in line]
        error_details = "\n".join(error_lines[:5]) if error_lines else full_log[-1000:]
        raise Exception(f"Compilation failed for {os.path.basename(file_path)}. Details: {error_details}")
    
    pdf_filename = os.path.basename(file_path).replace('.tex', '.pdf')
    pdf_path = os.path.join(output_dir, pdf_filename)
    if not os.path.exists(pdf_path):
        raise Exception(f"PDF missing after compilation: {pdf_filename}")
    
    return pdf_path

def main():
    print("================================================================")
    print("   CV Adapter - Parallel CLI adaptation runner (gemini-2.5-flash)")
    print("================================================================")
    
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY not found in .env file.")
        sys.exit(1)
        
    genai.configure(api_key=GEMINI_API_KEY, transport="rest")
    model = genai.GenerativeModel('gemini-2.5-flash')

    # Read templates and master CV
    try:
        with open('CV.tex', 'r', encoding='utf-8') as f:
            cv_template = f.read()
        with open('CoverLetter.tex', 'r', encoding='utf-8') as f:
            cl_template = f.read()
    except FileNotFoundError as e:
        print(f"Error: Required LaTeX templates not found. {e}")
        sys.exit(1)
        
    master_cv_path = 'master_cv.md'
    if not os.path.exists(master_cv_path):
        print(f"Error: {master_cv_path} not found.")
        sys.exit(1)
        
    with open(master_cv_path, 'r', encoding='utf-8') as f:
        cv_text = f.read()

    # Create dummy output directory if it doesn't exist
    output_dir = './outputs'
    os.makedirs(output_dir, exist_ok=True)
    
    # Define Prompts
    analysis_prompt = f"""
    Act as an expert ATS (Applicant Tracking System) scanner.
    Compare the following CV against the Job Description.
    
    JOB DESCRIPTION:
    {job_description}

    CV CONTENT:
    {cv_text}

    Return a ONLY a JSON object with this exact structure:
    {{
        "job_title": "extracted job title",
        "company": "extracted company name",
        "ats_score": 85,
        "missing_keywords": ["keyword1", "keyword2", "keyword3"],
        "cv_improvements": "Short summary of what to change in the CV content to target this job."
    }}
    """

    cv_prompt = f"""
    You are an expert CV tailor.
    I have a Master CV (Markdown) containing all my experiences, and a Job Description.
    I also have a LaTeX CV template.

    Your task is to rewrite the BODY of the LaTeX CV to target the Job Description, using the data from the Master CV.
    
    GUIDELINES:
    1. **Strict Structure & Commands**: 
       - You MUST use the custom LaTeX commands defined in the template: `\\entry` and `\\project`.
       - The `\\entry` command has exactly four arguments: `\\entry{{Job/Degree Title}}{{Dates}}{{Company/University}}{{Location}}`.
       - **CRITICAL**: Do NOT place bullet points, long text, or `itemize`/`enumerate` environments inside the arguments of `\\entry`. The fourth argument (Location) must be a short string (e.g. "Paris, France" or "Remote").
       - **CRITICAL**: Any descriptive text or bullet points related to an entry must be placed immediately **after** the `\\entry` command as plain text, NOT inside its arguments.
       - **CRITICAL**: Do NOT use `\\begin{{itemize}}` or `\\end{{itemize}}` list environments in the CV, as they are not supported in this layout and cause compilation errors. Instead, write descriptions as plain lines separated by `\\\\` or double spaces, or write them out as simple paragraphs, following the template's exact style.
    2. **Content**: Select the most relevant projects/experiences. Rewrite the 'Profil' and job-specific titles.
    3. **No Markdown**: Do NOT use markdown formatting (no **, no # headers). Use LaTeX commands (\\textbf{{...}}).
    4. **Language**: Write strictly in EN (English).
    5. **Reference**: Do strictly follow the template's custom commands.
    6. **ONE PAGE ONLY**: Keep it concise.
    7. **Output Format**: generate ONLY the LaTeX content for the body. Do NOT include \\documentclass, preamble, \\begin{{document}} or \\end{{document}}.
    8. **Escaping**: You MUST escape special LaTeX characters: & -> \\&, % -> \\%, # -> \\#, _ -> \\_.

    Master CV (Source of Truth):
    {cv_text}

    Job Description:
    {job_description}

    LaTeX CV Template (Structure to follow):
    {cv_template}
    
    Return ONLY the content that goes INSIDE \\begin{{document}} ... \\end{{document}}.
    """

    cl_prompt = f"""
    You are an expert career coach.
    I have a master LaTeX Cover Letter template and a Job Description.
    
    Your task is to generate a COMPLETE, READY-TO-COMPILE LaTeX file for the Cover Letter.
    
    JOB DESCRIPTION:
    {job_description}
    
    CANDIDATE CV:
    {cv_text}
    
    MASTER TEMPLATE:
    {cl_template}
    
    INSTRUCTIONS:
    1. **Full File**: Return the ENTIRE LaTeX file, from \\documentclass to \\end{{document}}.
    2. **Modification**: 
       - Update the `\\recipientblock` with real data from the JD (Company, Address, Manager Name).
       - Update the `\\subject` line.
       - Write a professional 3-paragraph body using `\\opening`, text, and `\\closing`.
    3. **Language**: Write strictly in EN.
    4. **Safety**: 
       - You MUST escape special characters (& -> \\&, # -> \\#, etc.).
       - Do NOT invent new commands. Use ONLY commands defined in the provided template.
       - Ensure `\\makeextraheader` is preserved.
    
    Return ONLY the raw LaTeX code (no markdown backticks if possible, or inside a latex block).
    """

    msg_prompt = f"""
    Act as the candidate described in the CV.
    Write a short, engaging LinkedIn outreach message (<1000 chars) to a recruiter for this Job.
    
    CONTEXT:
    - My CV: {cv_text}
    - Job Description: {job_description}

    INSTRUCTIONS:
    1. **Language**: Write strictly in English.
    2. **No Placeholders**: You MUST fill in the names/skills/company.
       - Candidate Name: Extract from CV (if not found, use "The Candidate").
       - Recruiter Name: "Hiring Team" (unless specific name found in JD).
       - Company: Extract from JD.
       - Skills: select real skills from CV relevant to JD.
    3. **Tone**: Professional, brief, and not robotic.
    
    Return ONLY the message text (Subject + Body).
    """

    print("Submitting parallel Gemini API calls...")
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_analysis = executor.submit(model.generate_content, analysis_prompt)
        future_cv = executor.submit(model.generate_content, cv_prompt)
        future_cl = executor.submit(model.generate_content, cl_prompt)
        future_msg = executor.submit(model.generate_content, msg_prompt)

        # Wait and extract initial analysis
        initial_analysis = extract_json(future_analysis.result().text)
        if not initial_analysis:
            initial_analysis = {
                "job_title": "Job Application", "company": "Unknown", 
                "ats_score": 70, "missing_keywords": [], "cv_improvements": ""
            }
        print(f"Initial ATS Match Score: {initial_analysis.get('ats_score', 0)}%")

        # Wait and extract CV text
        cv_body = clean_markdown(future_cv.result().text)
        print("CV adaptation text generated.")
        
        if "\\begin{document}" in cv_template:
            preamble = cv_template.split("\\begin{document}")[0]
            cv_latex = f"{preamble}\\begin{{document}}\n{cv_body}\n\\end{{document}}"
        else:
            cv_latex = cv_body

        # Submit final ATS scoring and CV compilation
        final_analysis_prompt = f"""
        Act as an expert ATS scanner.
        Score the following OPTIMIZED CV content against the Job Description.

        JOB DESCRIPTION:
        {job_description}

        OPTIMIZED CV CONTENT (LaTeX):
        {cv_body}

        Return a ONLY a JSON object with this exact structure:
        {{
            "job_title": "{initial_analysis.get('job_title')}", 
            "company": "{initial_analysis.get('company')}",
            "ats_score": 95,
            "missing_keywords": [],
            "cv_improvements": ""
        }}
        """
        future_final_analysis = executor.submit(model.generate_content, final_analysis_prompt)
        
        cv_tex_path = os.path.join(output_dir, 'CV_adapted.tex')
        with open(cv_tex_path, 'w', encoding='utf-8') as f:
            f.write(cv_latex)
        future_cv_compile = executor.submit(compile_latex, cv_tex_path, output_dir)

        # Wait and extract Cover Letter text
        cl_latex = clean_markdown(future_cl.result().text)
        print("Cover Letter text generated.")
        
        cl_tex_path = os.path.join(output_dir, 'CoverLetter_adapted.tex')
        with open(cl_tex_path, 'w', encoding='utf-8') as f:
            f.write(cl_latex)
        future_cl_compile = executor.submit(compile_latex, cl_tex_path, output_dir)

        # Get final scoring results
        final_analysis = extract_json(future_final_analysis.result().text)
        if not final_analysis:
            final_analysis = initial_analysis
            final_analysis['ats_score'] += 10
        print(f"Optimized ATS Match Score: {final_analysis.get('ats_score', 0)}%")

        # Compile PDF documents
        print("Compiling LaTeX documents to PDF in parallel...")
        cv_pdf_path = future_cv_compile.result()
        cl_pdf_path = future_cl_compile.result()
        print(f"CV PDF generated at: {cv_pdf_path}")
        print(f"Cover Letter PDF generated at: {cl_pdf_path}")

        # Get outreach message
        msg_content = clean_markdown(future_msg.result().text)
        msg_path = os.path.join(output_dir, 'LinkedIn_message.txt')
        with open(msg_path, 'w', encoding='utf-8') as f:
            f.write(msg_content)
        print(f"Outreach message saved to: {msg_path}")

    elapsed = time.time() - start_time
    print("================================================================")
    print(f"Success! Adaptation complete in {elapsed:.2f} seconds.")
    print("================================================================")

if __name__ == "__main__":
    main()
