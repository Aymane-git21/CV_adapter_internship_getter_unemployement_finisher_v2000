import os
os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "true"
os.environ["GRPC_POLL_STRATEGY"] = "poll"
os.environ["NO_GCE_CHECK"] = "true"
os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
import subprocess
import concurrent.futures
import uuid
import threading
import time
import json
import re
from flask_cors import CORS
from datetime import datetime, timedelta
from flask import Flask, render_template, request, send_file, flash, redirect, url_for, jsonify, session, send_from_directory
import google.generativeai as genai
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from pypdf import PdfReader

load_dotenv()

app = Flask(__name__, static_folder='static/dist/assets', template_folder='static/dist')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.secret_key = os.getenv('SECRET_KEY', 'super_secret_key_default') # Load from env
# CORS Configuration
allowed_origins_env = os.environ.get('ALLOWED_ORIGINS')
if allowed_origins_env:
    origins_list = [origin.strip() for origin in allowed_origins_env.split(',')]
else:
    # Default trusted origins
    origins_list = [
        "http://localhost:3000",      # React Local
        "http://localhost:5173",      # Vite Local
        "http://localhost:8080",      # Flask Local
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8080",
        "https://cvglowup.com",       # Production
        "https://www.cvglowup.com"
    ]

CORS(app, resources={r"/api/*": {"origins": origins_list}}, supports_credentials=True)

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
app.config['OUTPUT_FOLDER'] = '/tmp/outputs'

# Database Configuration
db_user = os.environ.get("DB_USER")
db_pass = os.environ.get("DB_PASS")
db_name = os.environ.get("DB_NAME")
cloud_sql_connection_name = os.environ.get("CLOUD_SQL_CONNECTION_NAME")
database_url = os.environ.get("DATABASE_URL")

if database_url:
    # External DB (Neon)
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url

elif cloud_sql_connection_name:
    # Production: Google Cloud SQL (via Unix Socket)
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        f"postgresql+psycopg2://{db_user}:{db_pass}@/{db_name}"
        f"?host=/cloudsql/{cloud_sql_connection_name}"
    )
else:
    # Local: SQLite
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/cv_tailor_v2.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# Database Setup
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# User Model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.Text) # Changed from String(128) to Text for longer hashes
    cv_text = db.Column(db.Text, nullable=True) 
    
    # SaaS Fields
    plan_type = db.Column(db.String(20), default='free') # 'free', 'pro'
    credits_used = db.Column(db.Integer, default=0)
    last_reset = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Application History Model
class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    job_title = db.Column(db.String(150))
    company = db.Column(db.String(150))
    ats_score = db.Column(db.Integer, default=0)
    missing_keywords = db.Column(db.Text) # JSON string
    cv_path = db.Column(db.String(200))
    cl_path = db.Column(db.String(200))
    message_content = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Feedback Model
class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120))
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Create DB
with app.app_context():
    if os.environ.get('FORCE_DB_RESET') == 'true':
        print("!!! FORCE_DB_RESET is set. Dropping all tables... !!!")
        db.drop_all()
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ROUTES ---

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def home(path):
    if path.startswith('api/') or path.startswith('static/'):
        return jsonify({'error': 'Not found'}), 404
    return render_template('index.html')




@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already exists'}), 400
        
    new_user = User(email=email)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    login_user(new_user)
    return jsonify({'message': 'Registered successfully', 'has_cv': False})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(email=data.get('email')).first()
    if user and user.check_password(data.get('password')):
        login_user(user)
        return jsonify({'message': 'Login successful', 'has_cv': bool(user.cv_text)})
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    logout_user()
    return jsonify({'message': 'Logged out'})

@app.route('/api/user_status')
def user_status():
    if current_user.is_authenticated:
        # Check credit reset
        if current_user.plan_type == 'free' and (datetime.utcnow() - current_user.last_reset).days >= 1:
            current_user.credits_used = 0
            current_user.last_reset = datetime.utcnow()
            db.session.commit()
            
        return jsonify({
            'logged_in': True, 
            'email': current_user.email,
            'has_cv': bool(current_user.cv_text),
            'credits': 99 - current_user.credits_used,
            'plan': current_user.plan_type
        })
    return jsonify({'logged_in': False})

@app.route('/api/history')
@login_required
def get_history():
    apps = Application.query.filter_by(user_id=current_user.id).order_by(Application.timestamp.desc()).all()
    history_data = []
    for app in apps:
        history_data.append({
            'id': app.id,
            'job': app.job_title or "Job Application",
            'company': app.company or "Unknown",
            'score': app.ats_score,
            'date': app.timestamp.strftime('%Y-%m-%d')
        })
    return jsonify(history_data)

@app.route('/api/contact', methods=['POST'])
def contact():
    data = request.json
    feedback = Feedback(
        name=data.get('name'), 
        email=data.get('email'), 
        message=data.get('message')
    )
    db.session.add(feedback)
    db.session.commit()
    return jsonify({'message': 'Message received!'})

# Gemini Configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY, transport="rest")

# Global Job Store and Executor
JOBS = {}
executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)

def clean_markdown(text):
    if text.startswith("```latex"): text = text[8:]
    elif text.startswith("```json"): text = text[7:]
    elif text.startswith("```"): text = text[3:]
    if text.endswith("```"): text = text[:-3]
    text = text.replace("**", "")
    return text.strip()

def extract_json(text):
    """Extracts JSON object from a string that might contain other text."""
    try:
        # Try parsing directly
        return json.loads(text)
    except json.JSONDecodeError:
        # Look for { ... } structure
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except:
                pass
    return None

def process_job(job_id, job_description, cv_text, user_id=None, language='en'):
    try:
        JOBS[job_id]['status'] = 'processing'
        JOBS[job_id]['current_step'] = 0
        JOBS[job_id]['logs'].append("Reading master templates...")

        # 1. READ TEMPLATES
        try:
            with open('CV.tex', 'r', encoding='utf-8', errors='replace') as f:
                cv_template = f.read()
            with open('CoverLetter.tex', 'r', encoding='utf-8', errors='replace') as f:
                cl_template = f.read()
        except FileNotFoundError:
            cv_template = "Error: CV.tex not found."
            cl_template = "Error: CoverLetter.tex not found."
            JOBS[job_id]['logs'].append("Warning: Templates not found.")

        # Configure Generative Model (Upgrade to gemini-2.5-flash)
        model = genai.GenerativeModel('gemini-2.5-flash')

        # 2. CONSTRUCT PROMPTS
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
    4. **Language**: Write strictly in {language.upper()}.
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
    3. **Language**: Write strictly in {language.upper()}.
    4. **Safety**: 
       - You MUST escape special characters (& -> \\&, # -> \\#, etc.).
       - Do NOT invent new commands. Use ONLY commands defined in the provided template.
       - Ensure `\\makeextraheader` is preserved.
    
    Return ONLY the raw LaTeX code (no markdown backticks if possible, or inside a latex block).
    """

        lang_name = "French" if language == 'fr' else "English"
        msg_prompt = f"""
        Act as the candidate described in the CV.
        Write a short, engaging LinkedIn outreach message (<1000 chars) to a recruiter for this Job.
        
        CONTEXT:
        - My CV: {cv_text}
        - Job Description: {job_description}

        INSTRUCTIONS:
        1. **Language**: Write strictly in {lang_name}.
        2. **No Placeholders**: You MUST fill in the names/skills/company.
           - Candidate Name: Extract from CV (if not found, use "The Candidate").
           - Recruiter Name: "Hiring Team" (unless specific name found in JD).
           - Company: Extract from JD.
           - Skills: select real skills from CV relevant to JD.
        3. **Tone**: Professional, brief, and not robotic.
        
        Return ONLY the message text (Subject + Body).
        """

        output_dir = app.config['OUTPUT_FOLDER']
        cv_filename = f"CV_{job_id}.tex"
        cl_filename = f"CL_{job_id}.tex"

        # Compilation helper function to be run inside the thread pool
        def compile_latex_file(latex_content, filename):
            file_path = os.path.join(output_dir, filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(latex_content)
            
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
                print(f"Compilation of {filename} failed:\nSTDOUT: {stdout_str}\nSTDERR: {stderr_str}")
                raise Exception(f"Compilation failed. Details: {error_details}")
            
            pdf_filename = filename.replace('.tex', '.pdf')
            pdf_path = os.path.join(output_dir, pdf_filename)
            if not os.path.exists(pdf_path):
                raise Exception(f"PDF file missing after compilation: {pdf_filename}")
            
            return pdf_filename

        JOBS[job_id]['logs'].append("Launching parallel AI adaptation pipeline...")
        JOBS[job_id]['current_step'] = 1

        # 3. RUN CONCURRENT GENERATION TASKS
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as local_executor:
            # Submit initial tasks
            future_analysis = local_executor.submit(model.generate_content, analysis_prompt)
            future_cv = local_executor.submit(model.generate_content, cv_prompt)
            future_cl = local_executor.submit(model.generate_content, cl_prompt)
            future_msg = local_executor.submit(model.generate_content, msg_prompt)

            # A. Get initial ATS scan analysis
            analysis_response = future_analysis.result()
            initial_analysis = extract_json(analysis_response.text)
            if not initial_analysis:
                initial_analysis = {
                    "job_title": "Job Application", "company": "Unknown", 
                    "ats_score": 70, "missing_keywords": [], "cv_improvements": ""
                }
            JOBS[job_id]['logs'].append(f"Initial ATS Match Score: {initial_analysis.get('ats_score', 0)}%")
            
            # B. Get CV text and submit final scoring and compilation immediately
            cv_response = future_cv.result()
            cv_body = clean_markdown(cv_response.text)
            JOBS[job_id]['logs'].append("CV adaptation content generated.")

            # Reconstruct full LaTeX CV
            if "\\begin{document}" in cv_template:
                preamble = cv_template.split("\\begin{document}")[0]
                cv_latex = f"{preamble}\\begin{{document}}\n{cv_body}\n\\end{{document}}"
            else:
                cv_latex = cv_body

            # Log the generated CV LaTeX for debugging
            print(f"--- GENERATED CV LATEX ({job_id}) ---\n{cv_latex}\n-----------------------------------")

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
            future_final_analysis = local_executor.submit(model.generate_content, final_analysis_prompt)
            future_cv_compile = local_executor.submit(compile_latex_file, cv_latex, cv_filename)

            # C. Get Cover Letter text and submit compilation immediately
            cl_response = future_cl.result()
            cl_latex = clean_markdown(cl_response.text)
            JOBS[job_id]['logs'].append("Cover Letter content generated.")
            
            # Log the generated CL LaTeX for debugging
            print(f"--- GENERATED CL LATEX ({job_id}) ---\n{cl_latex}\n-----------------------------------")
            
            future_cl_compile = local_executor.submit(compile_latex_file, cl_latex, cl_filename)

            # D. Wait for remaining concurrent tasks
            JOBS[job_id]['logs'].append("Compiling PDF documents in parallel...")
            JOBS[job_id]['current_step'] = 2

            final_analysis_res = future_final_analysis.result()
            final_analysis = extract_json(final_analysis_res.text)
            if not final_analysis:
                final_analysis = initial_analysis
                final_analysis['ats_score'] += 10
            JOBS[job_id]['logs'].append(f"Optimized ATS Match Score: {final_analysis.get('ats_score', 0)}%")
            JOBS[job_id]['current_step'] = 3

            cv_pdf = future_cv_compile.result()
            cl_pdf = future_cl_compile.result()
            JOBS[job_id]['logs'].append("PDF documents compiled successfully.")

            msg_content = clean_markdown(future_msg.result().text)
            JOBS[job_id]['logs'].append("LinkedIn outreach message generated.")

        # 4. SAVE TO DB (If Registered)
        if user_id:
            with app.app_context():
                user = User.query.get(user_id)
                if user and user.plan_type == 'free':
                    user.credits_used += 1
                
                new_app = Application(
                    user_id=user_id,
                    job_title=final_analysis.get('job_title', 'Job Application'),
                    company=final_analysis.get('company', 'Unknown'),
                    ats_score=final_analysis.get('ats_score', 0),
                    missing_keywords=json.dumps(final_analysis.get('missing_keywords', [])),
                    cv_path=cv_pdf,
                    cl_path=cl_pdf,
                    message_content=msg_content
                )
                db.session.add(new_app)
                db.session.commit()

        JOBS[job_id]['current_step'] = 4
        JOBS[job_id]['status'] = 'completed'
        JOBS[job_id]['result'] = {
            'cv_pdf': cv_pdf,
            'cl_pdf': cl_pdf,
            'analysis': final_analysis,
            'initial_analysis': initial_analysis,
            'message_text': msg_content
        }
        JOBS[job_id]['logs'].append("Done!")

    except Exception as e:
        JOBS[job_id]['status'] = 'failed'
        error_msg = str(e)
        JOBS[job_id]['logs'].append(f"Error: {error_msg}")
        JOBS[job_id]['error_details'] = error_msg
        print(f"Job failed: {e}")

@app.route('/start_job', methods=['POST'])
def start_job():
    # Guest Limit Check
    if not current_user.is_authenticated:
        if session.get('guest_usage', 0) >= 1:
            return jsonify({'error': 'Guest verification limit reached. Please register for free.'}), 403
        session['guest_usage'] = session.get('guest_usage', 0) + 1
    else:
        # User Limit Check
        if current_user.plan_type == 'free' and current_user.credits_used >= 99:
             return jsonify({'error': 'Daily limit reached (99/99). Upgrade to Pro for unlimited.'}), 403

    job_description = request.form.get('job_description')
    cv_text = ""
    
    # Handle CV Input (File or Database or Text)
    should_save = request.form.get('save_cv') == 'true'

    if 'cv_file' in request.files:
        file = request.files['cv_file']
        if file.filename != '':
            filename = secure_filename(file.filename)
            path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(path)
            reader = PdfReader(path)
            for page in reader.pages:
                cv_text += page.extract_text()
            
            # Save to profile if requested OR if empty
            if current_user.is_authenticated:
                if should_save or not current_user.cv_text:
                    current_user.cv_text = cv_text
                    db.session.commit()

    elif 'cv_text' in request.form and request.form['cv_text']:
        cv_text = request.form['cv_text']
        if current_user.is_authenticated:
            if should_save or not current_user.cv_text:
                current_user.cv_text = cv_text
                db.session.commit()

    elif current_user.is_authenticated and current_user.cv_text:
        cv_text = current_user.cv_text
    
    else:
        return jsonify({'error': 'No CV provided'}), 400

    job_id = str(uuid.uuid4())
    JOBS[job_id] = {'status': 'queued', 'logs': [], 'result': None, 'current_step': 0}
    
    user_id = current_user.id if current_user.is_authenticated else None
    
    language = request.form.get('language', 'en')
    
    executor.submit(process_job, job_id, job_description, cv_text, user_id, language)
    
    return jsonify({'job_id': job_id})

@app.route('/job_status/<job_id>')
def job_status(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({'status': 'unknown'}), 404
    return jsonify(job)

@app.route('/view/<filename>')
def view_file(filename):
    try:
        directory = os.path.abspath(app.config['OUTPUT_FOLDER'])
        safe_filename = secure_filename(filename)
        file_path = os.path.join(directory, safe_filename)
        if not os.path.exists(file_path):
             print(f"View Error: File not found at {file_path}")
             return jsonify({'error': 'File not found'}), 404
        return send_file(file_path, as_attachment=False)
    except Exception as e:
        print(f"View Exception: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    try:
        directory = os.path.abspath(app.config['OUTPUT_FOLDER'])
        safe_filename = secure_filename(filename)
        file_path = os.path.join(directory, safe_filename)
        
        if not os.path.exists(file_path):
            print(f"Download Error: File not found at {file_path}")
            return jsonify({'error': 'File not found'}), 404
            
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        print(f"Download Exception: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Use PORT env var for Cloud Run, default to 8080 or 5000 locally
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=False, host='0.0.0.0', port=port)
