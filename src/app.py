import os
import json
from typing import List, Dict, Optional
from flask import Flask, render_template, request, Response, jsonify
from dotenv import load_dotenv
from openai import OpenAI
from PyPDF2 import PdfReader
import base64
from pathlib import Path
from elevenlabs.client import ElevenLabs
import re

# =============================
# CONFIG
# =============================
load_dotenv(override=True)
MODEL = "gpt-4o-mini"
MAX_QNA_PAIRS = 5

elevenlabs_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

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

reader = PdfReader(linkedin_path)
linkedin = ""
for page in reader.pages:
    text = page.extract_text()
    if text:
        linkedin += text + "\n"

# =============================
# LOAD TEXTUAL INFO
# =============================
with open(summary_path, "r") as f:
    summary = f.read()

name = os.getenv("PERSON_NAME", "Jai Goswami")

system_prompt = f"You are acting as {name}. You are answering questions on {name}'s website, \
particularly questions related to {name}'s career, background, skills and experience. \
Your responsibility is to represent {name} for interactions on the website as faithfully as possible. \
You are given a summary of {name}'s background and LinkedIn profile which you can use to answer questions. \
Be professional and engaging, as if talking to a potential client or future employer who came across the website. \
If you don't know the answer, say so."

system_prompt += f"\n\n## Summary:\n{summary}\n\n## LinkedIn Profile:\n{linkedin}\n\n"
system_prompt += f"With this context, please chat with the user, always staying in character as {name}."
system_prompt += f"You are strictly not to answer questions that are not related to {name}'s career, background, skills and experience, in such cases you should say that you can only answer questions related to {name}'s career, background, skills and experience."

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
# TTS PROCESSOR FOR WEB - FIXED
# =============================
class WebTTSProcessor:
    def __init__(self, model, voice_id, output_format):
        self.model = model
        self.voice_id = voice_id
        self.output_format = output_format
        self.sample_rate = 44100

    def process_text_to_speech(self, text: str) -> bytes:
        """Convert text to speech and return audio bytes"""
        try:
            # CRITICAL FIX: Use explicit output_format parameter
            audio_generator = elevenlabs_client.text_to_speech.convert(
                voice_id=self.voice_id,
                text=text,
                model_id=self.model,
                output_format="mp3_44100_128"  # Explicit format
            )
            
            # Collect audio bytes
            audio_bytes = b''.join(audio_generator)
            
            # Log for debugging
            print(f"[TTS] Generated {len(audio_bytes)} bytes for: '{text[:50]}...'")
            
            return audio_bytes
            
        except Exception as e:
            print(f"[TTS ERROR] Failed to generate audio: {e}")
            import traceback
            traceback.print_exc()
            return b''
    
    def audio_to_base64(self, audio_bytes: bytes) -> str:
        """Convert audio bytes to base64"""
        if not audio_bytes:
            return ""
        b64 = base64.b64encode(audio_bytes).decode('utf-8')
        print(f"[TTS] Base64 length: {len(b64)}")
        return b64


# =============================
# SSE CHAT ENDPOINT - FIXED
# =============================
voice_id = os.getenv("ELEVENLABS_VOICE_ID", "QtEl85LECywm4BDbmbXB")
tts_processor = WebTTSProcessor("eleven_multilingual_v2", voice_id, "mp3_44100_128")

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
            text_buffer = ""
            
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    text_buffer += content
                    
                    # Send text chunk immediately
                    yield f"data: {json.dumps({'type': 'text_chunk', 'text': content})}\n\n"
                    
                    # Generate audio at sentence breaks or every 40 chars
                    should_generate = (
                        len(text_buffer) >= 40 or 
                        any(text_buffer.rstrip().endswith(p) for p in ['.', '!', '?'])
                    )
                    
                    if should_generate and text_buffer.strip():
                        clean_text = text_buffer.strip()
                        print(f"[CHAT] Generating audio for: '{clean_text[:50]}...'")
                        
                        audio = tts_processor.process_text_to_speech(clean_text)
                        
                        if audio and len(audio) > 0:
                            audio_b64 = tts_processor.audio_to_base64(audio)
                            if audio_b64:
                                yield f"data: {json.dumps({'type': 'audio_chunk', 'audio': audio_b64, 'text': clean_text})}\n\n"
                                print(f"[CHAT] Sent audio chunk")
                        else:
                            print(f"[CHAT] WARNING: No audio generated")
                        
                        text_buffer = ""
            
            # Send any remaining text as audio
            if text_buffer.strip():
                clean_text = text_buffer.strip()
                print(f"[CHAT] Final audio for: '{clean_text[:50]}...'")
                
                audio = tts_processor.process_text_to_speech(clean_text)
                if audio and len(audio) > 0:
                    audio_b64 = tts_processor.audio_to_base64(audio)
                    if audio_b64:
                        yield f"data: {json.dumps({'type': 'audio_chunk', 'audio': audio_b64, 'text': clean_text})}\n\n"
            
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
# TEST ENDPOINT FOR DEBUGGING
# =============================
@app.route('/test-tts')
def test_tts():
    """Test TTS functionality"""
    try:
        test_text = "This is a test of the text to speech system."
        audio = tts_processor.process_text_to_speech(test_text)
        
        if not audio or len(audio) == 0:
            return jsonify({
                'success': False,
                'error': 'No audio generated',
                'text': test_text
            }), 500
        
        audio_b64 = tts_processor.audio_to_base64(audio)
        
        return jsonify({
            'success': True,
            'audio_length': len(audio),
            'base64_length': len(audio_b64),
            'text': test_text,
            'audio': audio_b64[:100] + '...'  # First 100 chars
        })
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

# =============================
# ROUTES
# =============================
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    print(f"[SERVER] Starting on port {port}")
    print(f"[CONFIG] ElevenLabs API key present: {bool(os.getenv('ELEVENLABS_API_KEY'))}")
    print(f"[CONFIG] Voice ID: {voice_id}")
    app.run(host='0.0.0.0', port=port)