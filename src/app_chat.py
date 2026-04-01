import os
import json
from typing import List, Dict, Optional
from flask import Flask, render_template, request, Response, jsonify
from dotenv import load_dotenv
from openai import OpenAI
from PyPDF2 import PdfReader
import base64
from pathlib import Path
import re

# =============================
# CONFIG
# =============================
load_dotenv(override=True)
MODEL = "gpt-4o-mini"
MAX_QNA_PAIRS = 5

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY not found in .env")

openai_client = OpenAI(api_key=api_key)

# =============================
# FLASK APP SETUP
# =============================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# =============================
# LOAD LINKEDIN PDF
# =============================
Base_dir = Path(__file__).parent.parent
linkedin_path = os.getenv("LINKEDIN_PDF_PATH", Base_dir / "src" / "Me" / "linkedin.pdf")
summary_path = os.getenv("SUMMARY_TXT_PATH", Base_dir / "src" / "Me" / "summary.txt")
resume_path = os.getenv("RESUME_PDF_PATH", Base_dir / "src" / "Me" / "Jai_Goswami_Resume.pdf")

reader = PdfReader(linkedin_path)
linkedin = ""
for page in reader.pages:
    text = page.extract_text()
    if text:
        linkedin += text + "\n"

# =============================
# LOAD RESUME PDF
# =============================
resume_reader = PdfReader(resume_path)
resume = ""
for page in resume_reader.pages:
    text = page.extract_text()
    if text:
        resume += text + "\n"

# =============================
# LOAD TEXTUAL INFO
# =============================
with open(summary_path, "r") as f:
    summary = f.read()

name = os.getenv("PERSON_NAME", "Jai Goswami")

system_prompt = f"You are acting as {name}'e-cameo. You are answering questions on {name}'s website, \
particularly questions related to {name}'s career, background, skills and experience. \
Your responsibility is to represent {name} for interactions on the website as faithfully as possible. \
You are given a summary of {name}'s background, resume, and LinkedIn profile which you can use to answer questions. \
Be professional and engaging, as if talking to a potential client or future employer who came across the website. \
If you don't know the answer, say so."

system_prompt += f"\n\n## Summary:\n{summary}\n\n## Resume:\n{resume}\n\n## LinkedIn Profile:\n{linkedin}\n\n"
system_prompt += f"With this context, please chat with the user, always staying in character as {name}. "
system_prompt += f"IMPORTANT: Keep your responses concise and summarized. Do not exceed 50-100 words in any answer only say a 100 words where actually required. "
system_prompt += f"If someone asks who you are, introduce yourself as Jai's ecameo. "
system_prompt += f"\n\n## Special Guidance:\n"
system_prompt += f"When asked about whether interactive AI resumes like this eCameo could replace traditional resumes, emphasize that you strongly believe they will evolve into the future of hiring. \
Explain that traditional resumes are static documents, while AI-powered resumes like this can answer questions, explain projects, and adapt to what a recruiter wants to know. \
Highlight how recruiters can have a real conversation instead of scanning bullet points, giving them instant insight into your skills, experience, and thinking process. \
Note that as hiring becomes more digital and AI-driven, interactive formats are faster, more engaging, and far more informative than PDF resumes."
system_prompt += f"You are strictly not to answer questions that are not related to {name}'s career, background, skills and experience, in such cases you should say that you can only answer questions related to {name}'s career, background, skills and experience."
system_prompt += f"Always keep your answers concise and to the point, do not exceed 50-100 words in any answer, and we are at the moment in 2026 and do not mention that Jai is still a student at university, instead say that Jai recently graduated from university and is now working as a Data Scientist."

# =============================
# SESSION MEMORY
# =============================
class SessionMemory:
    def __init__(self):
        self.messages: List[Dict] = []

    def add(self, role, content):
        self.messages.append({"role": role, "content": content})
        self.messages = self.messages[-MAX_QNA_PAIRS * 2:]

    def get(self):
        return self.messages

    def summary(self):
        out = []
        for i in range(0, len(self.messages), 2):
            q = self.messages[i]["content"]
            a = self.messages[i + 1]["content"]
            out.append(f"Q: {q}\nA: {a}")
        return "\n".join(out)


# Global session (in production, use session management)
session = SessionMemory()

# =============================
# SSE CHAT ENDPOINT
# =============================
@app.route('/chat', methods=['POST'])
def chat():
    """SSE endpoint for streaming chat responses"""
    user_input = request.json.get('message', '').strip()
    
    if not user_input:
        return jsonify({'error': 'Empty message'}), 400
    
    print(f"[CHAT] Received message: {user_input}")
    
    def generate():
        # Signal start
        yield f"data: {json.dumps({'type': 'response_start'})}\n\n"
        
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(session.get())
        messages.append({"role": "user", "content": user_input})
        
        try:
            stream = openai_client.chat.completions.create(
                model=MODEL,
                messages=messages,
                stream=True,
            )
            
            full_response = ""
            
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    
                    # Send text chunk immediately
                    yield f"data: {json.dumps({'type': 'text_chunk', 'text': content})}\n\n"
            
            # Signal completion
            yield f"data: {json.dumps({'type': 'response_end'})}\n\n"
            
            # Update session
            session.add("user", user_input)
            session.add("assistant", full_response.strip())
            
            print(f"[CHAT] Response complete")
                        
        except Exception as e:
            print(f"[CHAT ERROR] {e}")
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

# =============================
# ROUTES
# =============================
@app.route('/favicon.ico')
def favicon():
    """Return a simple favicon to prevent 404 errors"""
    return '', 204  # No content response

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    print(f"[SERVER] Starting on port {port}")
    app.run(host='0.0.0.0', port=port)
