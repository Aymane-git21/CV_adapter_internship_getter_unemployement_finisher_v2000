import os
import subprocess
import concurrent.futures
import uuid
import threading
import time
import json
import re
from datetime import datetime, timedelta
from flask import Flask, render_template, request, send_file, flash, redirect, url_for, jsonify, session
import google.generativeai as genai
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from pypdf import PdfReader

load_dotenv()

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Change this in production
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'outputs'
# Force new DB file to resolve schema issues
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cv_tailor_v2.db' 
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
    password_hash = db.Column(db.String(128))
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
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ROUTES ---

@app.route('/')
def home():
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
    genai.configure(api_key=GEMINI_API_KEY)

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
        JOBS[job_id]['logs'].append("Analyzing Job Description & CV...")

        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # 1. ANALYZE & SCORE (JSON Output)
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
        
        analysis_response = model.generate_content(analysis_prompt)
        analysis_data = extract_json(analysis_response.text)
        
        if not analysis_data:
            # Fallback if AI fails to give JSON
            analysis_data = {
                "job_title": "Job Application", "company": "Unknown", 
                "ats_score": 70, "missing_keywords": [], "cv_improvements": ""
            }

        JOBS[job_id]['logs'].append(f"ATS Score: {analysis_data['ats_score']}%")
        JOBS[job_id]['current_step'] = 1
        
        # 2. GENERATE LATEX CV
        # Read the Master Template
        try:
            with open('CV.tex', 'r', encoding='utf-8') as f:
                cv_template = f.read()
            with open('CoverLetter.tex', 'r', encoding='utf-8') as f:
                cl_template = f.read()
        except FileNotFoundError:
            cv_template = "Error: CV.tex not found."
            cl_template = "Error: CoverLetter.tex not found."
            JOBS[job_id]['logs'].append("Error: Templates not found.")

        cv_prompt = f"""
    You are an expert CV tailor.
    I have a Master CV (Markdown) containing all my experiences, and a Job Description.
    I also have a LaTeX CV template.

    Your task is to rewrite the BODY of the LaTeX CV to target the Job Description, using the data from the Master CV.
    
    GUIDELINES:
    1. **Strict Structure**: You MUST use the exact LaTeX commands and structure defined in the template (e.g., use the defined \\entry and \\project commands).
    2. **Content**: Select the most relevant projects/experiences. Rewrite the 'Profile' and 'Title'.
    3. **No Markdown**: Do NOT use markdown formatting (no **, no # headers). Use LaTeX commands (\\textbf{{...}}).
    4. **Language**: Write strictly in {language.upper()}.
    5. **Reference**: Do strictly follow the template's custom commands.
    6. **ONE PAGE ONLY**: Keep it concise.
    7. **Output Format**: generate ONLY the LaTeX content for the body. Do NOT include \\documentclass, preamble, \\begin{{document}} or \\end{{document}}.

    Master CV (Source of Truth):
    {cv_text}

    Job Description:
    {job_description}

    LaTeX CV Template (Structure to follow):
    {cv_template}
    
    Return ONLY the content that goes INSIDE \\begin{{document}} ... \\end{{document}}.
    """
        cv_response = model.generate_content(cv_prompt)
        cv_body = clean_markdown(cv_response.text)
        
        # Reconstruct the full CV
        if "\\begin{document}" in cv_template:
            preamble = cv_template.split("\\begin{document}")[0]
            cv_latex = f"{preamble}\\begin{{document}}\n{cv_body}\n\\end{{document}}"
        else:
            cv_latex = cv_body # Fallback

        JOBS[job_id]['current_step'] = 2

        # 3. GENERATE COVER LETTER
        cl_prompt = f"""
    You are an expert career coach.
    Write a professional Cover Letter body for the attached Job Description.
    
    JOB DESCRIPTION:
    {job_description}
    
    CANDIDATE CV:
    {cv_text}
    
    TEMPLATE CONTEXT:
    {cl_template}
    
    INSTRUCTIONS:
    1. **Format**: Use the exact commands from the template (e.g., \\opening, \\closing).
    2. **Content**: Write 3 paragraphs explaining why the candidate is a fit.
    3. **Style**: Professional and enthusiastic. Write strictly in {language.upper()}.
    4. **Output**: Return ONLY the body content (from \\opening to \\closing). Do NOT include \\documentclass or \\begin{{document}}.
    """
        cl_response = model.generate_content(cl_prompt)
        cl_body = clean_markdown(cl_response.text)
        
        # Inject into CL Template
        if "% <BODY_CONTENT>" in cl_template:
            cl_latex = cl_template.replace("% <BODY_CONTENT>", cl_body)
        elif "\\begin{document}" in cl_template:
             # Heuristic injection
             part1 = cl_template.split("\\begin{document}")[0] + "\\begin{document}\n"
             if "\\makeextraheader" in cl_template:
                 part1 += "\\makeextraheader\n"
             cl_latex = f"{part1}\n{cl_body}\n\\end{{document}}"
        else:
            cl_latex = cl_body
        
        # 4. GENERATE OUTREACH MESSAGE
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
        msg_response = model.generate_content(msg_prompt)
        msg_content = clean_markdown(msg_response.text)

        # 5. COMPILE LATEX
        JOBS[job_id]['current_step'] = 3
        JOBS[job_id]['logs'].append("Compiling PDF Documents...")
        
        output_dir = app.config['OUTPUT_FOLDER']
        cv_filename = f"CV_{job_id}.tex"
        cl_filename = f"CL_{job_id}.tex"
        
        with open(os.path.join(output_dir, cv_filename), 'w', encoding='utf-8') as f: f.write(cv_latex)
        with open(os.path.join(output_dir, cl_filename), 'w', encoding='utf-8') as f: f.write(cl_latex)

        # Compilation Command (with fallback)
        pdflatex_path = r'C:\Users\ayman\AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe'
        cmd = pdflatex_path if os.path.exists(pdflatex_path) else 'pdflatex'

        try:
            # Capture output for debugging
            result_cv = subprocess.run([cmd, '-interaction=nonstopmode', '-output-directory', output_dir, os.path.join(output_dir, cv_filename)], 
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            
            if result_cv.returncode != 0:
                print(f"CV Compilation Failed:\nSTDOUT: {result_cv.stdout}\nSTDERR: {result_cv.stderr}")
                JOBS[job_id]['logs'].append(f"CV Compilation Error (Code {result_cv.returncode})")

            result_cl = subprocess.run([cmd, '-interaction=nonstopmode', '-output-directory', output_dir, os.path.join(output_dir, cl_filename)], 
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                                     
            if result_cl.returncode != 0:
                 print(f"CL Compilation Failed:\nSTDOUT: {result_cl.stdout}\nSTDERR: {result_cl.stderr}")
                 JOBS[job_id]['logs'].append(f"CL Compilation Error (Code {result_cl.returncode})")

        except Exception as e:
            JOBS[job_id]['logs'].append(f"PDF Execution Error: {e}")
            print(f"Compilation Exec Failed: {e}")

        cv_pdf = f"CV_{job_id}.pdf"
        cl_pdf = f"CL_{job_id}.pdf"
        
        # Check if files actually exist
        if not os.path.exists(os.path.join(output_dir, cv_pdf)):
             JOBS[job_id]['logs'].append("CRITICAL: CV PDF was not created.")
        
        if not os.path.exists(os.path.join(output_dir, cl_pdf)):
             JOBS[job_id]['logs'].append("CRITICAL: CL PDF was not created.")

        # 6. SAVE TO DB (If Registered)
        if user_id:
            with app.app_context():
                user = User.query.get(user_id)
                if user and user.plan_type == 'free':
                    user.credits_used += 1
                
                new_app = Application(
                    user_id=user_id,
                    job_title=analysis_data.get('job_title', 'Job Application'),
                    company=analysis_data.get('company', 'Unknown'),
                    ats_score=analysis_data.get('ats_score', 0),
                    missing_keywords=json.dumps(analysis_data.get('missing_keywords', [])),
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
            'analysis': analysis_data
        }
        JOBS[job_id]['message_text'] = msg_content # Keys match frontend
        JOBS[job_id]['logs'].append("Done!")

    except Exception as e:
        JOBS[job_id]['status'] = 'failed'
        JOBS[job_id]['logs'].append(f"Error: {str(e)}")
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
    if 'cv_file' in request.files:
        file = request.files['cv_file']
        if file.filename != '':
            filename = secure_filename(file.filename)
            path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(path)
            reader = PdfReader(path)
            for page in reader.pages:
                cv_text += page.extract_text()
            
            # Save to profile if logged in
            if current_user.is_authenticated:
                current_user.cv_text = cv_text
                db.session.commit()

    elif 'cv_text' in request.form and request.form['cv_text']:
        cv_text = request.form['cv_text']
        if current_user.is_authenticated:
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
    return send_file(os.path.join(app.config['OUTPUT_FOLDER'], filename), as_attachment=False)

@app.route('/download/<filename>')
def download_file(filename):
    return send_file(os.path.join(app.config['OUTPUT_FOLDER'], filename), as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
