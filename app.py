import os
import subprocess
import smtplib
import concurrent.futures
import uuid
import threading
import time
import json
import re
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from flask import Flask, render_template, request, send_file, flash, redirect, url_for, jsonify
import google.generativeai as genai
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Change this in production
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'outputs'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# Gemini Configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Global Job Store and Executor
JOBS = {}
executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)

def clean_markdown(text):
    """Removes markdown code block formatting and artifacts."""
    if text.startswith("```latex"): text = text[8:]
    elif text.startswith("```json"): text = text[7:]
    elif text.startswith("```"): text = text[3:]
    if text.endswith("```"): text = text[:-3]
    
    # Remove markdown bolding artifacts
    text = text.replace("**", "")
    
    # Remove potential markdown headers that break LaTeX (# is special in LaTeX)
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        if line.strip().startswith('# '):
            continue # Skip markdown headers
        cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines).strip()

def extract_job_metadata(job_description):
    """
    Extracts Company Name and Job Title for dynamic naming.
    """
    if not GEMINI_API_KEY: return {"company": "Company", "title": "Job", "display_company": "Company", "display_title": "Job"}
    
    try:
        model = genai.GenerativeModel('models/gemini-2.0-flash')
        prompt = f"""
        Extract the 'Company Name' and 'Job Title' from this job description.
        Return a JSON object with keys:
        - 'company': Sanitize for filename (alphanumeric, underscores, hyphens only).
        - 'title': Sanitize for filename (alphanumeric, underscores, hyphens only).
        - 'display_company': The original company name for display.
        - 'display_title': The original job title for display.
        
        Example: 
        {{
            "company": "Google", 
            "title": "Software_Engineer", 
            "display_company": "Google", 
            "display_title": "Software Engineer"
        }}
        
        Job Description:
        {job_description[:2000]}
        """
        response = model.generate_content(prompt)
        text = clean_markdown(response.text)
        data = json.loads(text)
        return data
    except Exception as e:
        print(f"Metadata extraction failed: {e}")
        return {"company": "Company", "title": "Job", "display_company": "Company", "display_title": "Job"}

def adapt_cv_with_gemini(tex_content, job_description, master_cv_content, language="French"):
    if not GEMINI_API_KEY: raise ValueError("Gemini API Key is missing.")
    # Reverting to 3-pro-preview as requested
    model = genai.GenerativeModel('models/gemini-3-pro-preview')

    # Identifies the preamble to ensure we preserve the 'standalone' class packaging
    if "\\begin{document}" in tex_content:
        preamble = tex_content.split("\\begin{document}")[0]
    else:
        # Fallback if the template is malformed
        preamble = "\\documentclass[10pt, varwidth=18.6cm, border=1.2cm]{standalone}\n"

    prompt = f"""
    You are an expert CV tailor.
    I have a Master CV (Markdown) containing all my experiences, and a Job Description.
    I also have a LaTeX CV template.

    Your task is to rewrite the BODY of the LaTeX CV to target the Job Description, using the data from the Master CV.
    
    GUIDELINES:
    1. **Strict Structure**: You MUST use the exact LaTeX commands and structure defined in the template (e.g., use the defined \\entry and \\project commands).
    2. **Content**: Select the most relevant projects/experiences. Rewrite the 'Profile' and 'Title'.
    3. **Translation**: Fully translate ALL content, including section headers (e.g., "Education", "Experience") into the target language.
    4. **No Markdown**: Do NOT use markdown formatting (no **, no # headers). Use LaTeX commands (\\textbf{{...}}).
    5. **Language**: {language}.
    5. **Reference**: Do strictly follow the template's custom commands.
    6. **ONE PAGE ONLY**: Keep it concise.
    7. **Output Format**: generate ONLY the LaTeX content for the body. Do NOT include \\documentclass, preamble, \\begin{{document}} or \\end{{document}}.

    Master CV (Source of Truth):
    {master_cv_content}

    Job Description:
    {job_description}

    LaTeX CV Template (Structure to follow):
    {tex_content}
    
    Return ONLY the content that goes INSIDE \\begin{{document}} ... \\end{{document}}.
    """
    response = model.generate_content(prompt)
    body_content = clean_markdown(response.text)
    
    # Extra safety: remove document tags if the AI ignored instructions
    body_content = body_content.replace("\\begin{document}", "").replace("\\end{document}", "")
    
    return f"{preamble}\\begin{{document}}\n{body_content}\n\\end{{document}}"

def generate_cover_letter(job_description, master_cv_content, cl_tex_content, language="French"):
    if not GEMINI_API_KEY: raise ValueError("Gemini API Key is missing.")
    model = genai.GenerativeModel('models/gemini-3-pro-preview')
    prompt = f"""
    You are an expert career coach.
    Write a compelling CACHE_LETTER_BODY for the following Job Description, based on the candidate's Master CV.
    
    You are NOT generating the full LaTeX file. You are only generating the content that goes inside the body of the letter.

    GUIDELINES:
    1. **Format**: The text will be injected into a LaTeX `letter` environment.
       - The template ALREADY defines the sender/recipient block.
       - You must provide: Subject, Opening, Body, Closing.
       
    2. **Structure to Generate**:
       - `\\subject{{\\textbf{{Objet :}} ...}}` 
       - `\\opening{{Madame, Monsieur,}}` (or specific Name if known)
       - **BODY PARAGRAPHS**: 3-4 paragraphs.
       - `\\closing{{Je vous prie d’agréer...}}` 
       - Do NOT include `\\end{{letter}}` or `\\begin{{letter}}`.
       - Do NOT include `\\signature{{...}}` (handled by template).
       
    3. **Styling Constraints (STRICT)**:
       - **NO BOLD TEXT in the body paragraphs**.
       - **NO LONG HYPHENS** (use standard hyphens).
       - **No Markdown**: Pure LaTeX.
       
    4. **Content**: Professional, enthusiastic, tailored to the job.
    5. **Language**: {language}.
    6. **No Placeholders**: Do not include bracketed text `[...]`.
    
    Master CV:
    {master_cv_content}
    
    Job Description:
    {job_description}
    
    Return ONLY the valid LaTeX code commands (subject, opening, body, closing).
    """
    response = model.generate_content(prompt)
    body_content = clean_markdown(response.text)
    
    # Inject into template
    if "% <BODY_CONTENT>" in cl_tex_content:
        final_latex = cl_tex_content.replace("% <BODY_CONTENT>", body_content)
    else:
        # Fallback: Insert before \end{document}
        final_latex = cl_tex_content.replace("\\end{document}", f"\n{body_content}\n\\end{{document}}")
        
    return final_latex

def generate_short_message(job_description, master_cv_content, language="French"):
    if not GEMINI_API_KEY: raise ValueError("Gemini API Key is missing.")
    model = genai.GenerativeModel('models/gemini-3-pro-preview')
    prompt = f"""
    Write a short, professional email body (or LinkedIn message) to apply for this internship.
    
    GUIDELINES:
    1. **Length**: STRICTLY LESS THAN 1000 CHARACTERS.
    2. **Language**: {language}.
    3. **No Markdown**: Pure text.

    Master CV:
    {master_cv_content}

    Job Description:
    {job_description}

    Return ONLY the text of the message.
    """
    response = model.generate_content(prompt)
    return response.text.strip()

def compile_latex(tex_path, output_dir):
    pdflatex_path = r'C:\Users\ayman\AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe'
    pdf_filename = os.path.splitext(os.path.basename(tex_path))[0] + ".pdf"
    expected_pdf_path = os.path.join(output_dir, pdf_filename)

    try:
        result = subprocess.run([pdflatex_path, '-interaction=nonstopmode', '-output-directory', output_dir, tex_path], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if os.path.exists(expected_pdf_path):
            return expected_pdf_path
        else:
            raise RuntimeError(f"LaTeX compilation failed. Return code: {result.returncode}")
    except Exception as e:
        raise RuntimeError(f"LaTeX compilation error: {str(e)}")

def send_email(cv_pdf_path, cover_letter_pdf_path, email_body, recipient_email):
    sender_email = os.getenv('GMAIL_USER')
    sender_password = os.getenv('GMAIL_PASSWORD').replace(" ", "")

    if not sender_email or not sender_password: return

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = "Candidature - Stage"

    msg.attach(MIMEText(email_body, 'plain'))

    for path in [cv_pdf_path, cover_letter_pdf_path]:
        if path and os.path.exists(path):
            try:
                with open(path, "rb") as attachment:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename= {os.path.basename(path)}")
                msg.attach(part)
            except Exception as e:
                print(f"Failed to attach {path}: {e}")

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())
        server.quit()
    except Exception as e:
        print(f"Failed to send email: {e}")

def process_application(job_id, job_description, recipient_email, tex_content, cl_tex_content, master_cv_content, language="French"):
    JOBS[job_id]['status'] = 'processing'
    JOBS[job_id]['logs'].append("Starting analysis...")
    
    try:
        # Handle Language-specific LaTeX settings (Babel)
        if language == "English":
            tex_content = tex_content.replace("{french}", "{english}")
            cl_tex_content = cl_tex_content.replace("{french}", "{english}")

        # 1. Start Metadata Extraction first (Blocking for better quality context)
        # We need the title for the Cover Letter header
        future_meta = executor.submit(extract_job_metadata, job_description)
        meta = future_meta.result()
        
        company = meta.get('company', 'Company')
        title = meta.get('title', 'Job')
        display_title = meta.get('display_title', title)
        
        JOBS[job_id]['logs'].append(f"Identified Job: {title} at {company}")

        # Update Cover Letter Title dynamically
        cl_tex_adapted = re.sub(
            r'\\newcommand\{\\YourTitle\}\{.*?\}',
            f'\\\\newcommand{{\\\\YourTitle}}{{{display_title}}}',
            cl_tex_content
        )

        future_cv_text = executor.submit(adapt_cv_with_gemini, tex_content, job_description, master_cv_content, language)
        # Use the adapted latex content
        future_cl_text = executor.submit(generate_cover_letter, job_description, master_cv_content, cl_tex_adapted, language)
        future_msg = executor.submit(generate_short_message, job_description, master_cv_content, language)

        cv_filename = "CV_AymaneMERBOUH.tex"
        cl_filename = "CoverLetter_AymaneMERBOUH.tex"

        # 3. Process CV
        JOBS[job_id]['logs'].append("Adapting CV...")
        cv_text = future_cv_text.result()
        cv_path = os.path.join(app.config['UPLOAD_FOLDER'], cv_filename)
        with open(cv_path, 'w', encoding='utf-8') as f: f.write(cv_text)
        
        JOBS[job_id]['logs'].append("Compiling CV...")
        cv_pdf_path = compile_latex(cv_path, app.config['OUTPUT_FOLDER'])
        JOBS[job_id]['logs'].append("CV Ready.")

        # 4. Process Cover Letter
        JOBS[job_id]['logs'].append("Writing Cover Letter...")
        cl_text = future_cl_text.result()
        cl_path = os.path.join(app.config['UPLOAD_FOLDER'], cl_filename)
        with open(cl_path, 'w', encoding='utf-8') as f: f.write(cl_text)
        
        JOBS[job_id]['logs'].append("Compiling Cover Letter...")
        cl_pdf_path = compile_latex(cl_path, app.config['OUTPUT_FOLDER'])
        JOBS[job_id]['logs'].append("Cover Letter Ready.")

        # 5. Process Message & Email
        JOBS[job_id]['logs'].append("Drafting Email...")
        msg_text = future_msg.result()
        
        if recipient_email:
            JOBS[job_id]['logs'].append(f"Sending email to {recipient_email}...")
            send_email(cv_pdf_path, cl_pdf_path, msg_text, recipient_email)
            JOBS[job_id]['logs'].append("Email Sent!")
        
        JOBS[job_id]['result'] = {
            'cv_pdf': os.path.basename(cv_pdf_path),
            'cl_pdf': os.path.basename(cl_pdf_path)
        }
        JOBS[job_id]['status'] = 'completed'
        JOBS[job_id]['logs'].append("All Done!")

    except Exception as e:
        JOBS[job_id]['status'] = 'failed'
        JOBS[job_id]['logs'].append(f"Error: {str(e)}")
        print(f"Job {job_id} failed: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_job', methods=['POST'])
def start_job():
    job_description = request.form.get('job_description')
    recipient_email = request.form.get('email')
    language = request.form.get('language', 'French')
    
    if not job_description:
        return jsonify({'error': 'No job description provided'}), 400

    # Read static files
    try:
        with open(os.path.abspath('CV.tex'), 'r', encoding='utf-8') as f:
            tex_content = f.read()
            
        with open(os.path.abspath('CoverLetter.tex'), 'r', encoding='utf-8') as f:
            cl_tex_content = f.read()
        
        master_cv_path = os.path.abspath('master_cv.md')
        if os.path.exists(master_cv_path):
            with open(master_cv_path, 'r', encoding='utf-8') as f:
                master_cv_content = f.read()
        else:
            master_cv_content = "No master CV found."
    except Exception as e:
        return jsonify({'error': f"File error: {e}"}), 500

    job_id = str(uuid.uuid4())
    JOBS[job_id] = {'status': 'queued', 'logs': [], 'result': None}
    
    # Start background thread
    thread = threading.Thread(target=process_application, args=(job_id, job_description, recipient_email, tex_content, cl_tex_content, master_cv_content, language))
    thread.start()
    
    return jsonify({'job_id': job_id})

@app.route('/job_status/<job_id>')
def job_status(job_id):
    job = JOBS.get(job_id)
    if not job: return jsonify({'error': 'Job not found'}), 404
    return jsonify(job)

@app.route('/download/<filename>')
def download_file(filename):
    return send_file(os.path.join(app.config['OUTPUT_FOLDER'], filename), as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
