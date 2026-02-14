import os
import json
from typing import List, Dict, Optional
from flask import Flask, render_template, request, Response, jsonify
from dotenv import load_dotenv
from openai import OpenAI
from PyPDF2 import PdfReader
import base64
from pathlib import Path
# from elevenlabs import generate, set_api_key
from elevenlabs.client import ElevenLabs
import re

# =============================
# CONFIG
# =============================
load_dotenv(override=True)
MODEL = "gpt-4o-mini"
MAX_QNA_PAIRS = 5

# set_api_key(os.getenv("ELEVENLABS_API_KEY"))


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
# TTS PROCESSOR FOR WEB
# =============================
class WebTTSProcessor:
    def __init__(self, model, voice_id, output_format, use_mock=False):
        self.model = model
        self.voice_id = voice_id
        self.output_format = output_format
        self.sample_rate = 44100
        self.use_mock = use_mock

    def process_text_to_speech(self, text: str) -> bytes:
        """Convert text to speech and return audio bytes"""
        # MOCK MODE: Return fake MP3 header for testing without API calls
        if self.use_mock:
            print(f"[MOCK TTS] Simulating audio for: {text[:30]}...")
            # Minimal valid MP3 frame (silence, ~0.026 seconds)
            # This allows testing audio playback without spending credits
            duration = len(text) * 0.05  # ~50ms per character
            frames = int(duration / 0.026)
            mock_audio = b'\xff\xfb\x90\x00' * frames  # Valid MP3 frame
            return mock_audio
        
        try:
            audio_generator = elevenlabs_client.generate(
                text=text,
                voice=self.voice_id,
                model=self.model
            )
            
            # v1.9.0 returns generator - collect into bytes
            audio_bytes = b''.join(audio_generator)
            return audio_bytes
            
        except Exception as e:
            print(f"[TTS ERROR] Failed to generate audio: {e}")
            import traceback
            traceback.print_exc()
            return b''
    
    def audio_to_base64(self, audio_bytes: bytes) -> str:
        """Convert audio bytes to base64"""
        return base64.b64encode(audio_bytes).decode('utf-8')


# =============================
# SSE CHAT ENDPOINT
# =============================
voice_id = os.getenv("ELEVENLABS_VOICE_ID", "QtEl85LECywm4BDbmbXB")
use_mock_tts = os.getenv("USE_MOCK_TTS", "false").lower() == "true"
tts_processor = WebTTSProcessor("eleven_multilingual_v2", voice_id, "mp3_44100_128", use_mock=use_mock_tts)

if use_mock_tts:
    print("[INFO] Running in MOCK TTS mode - no ElevenLabs API calls will be made")

@app.route('/chat', methods=['POST'])
def chat():
    """SSE endpoint for streaming chat responses"""
    user_input = request.json.get('message', '').strip()
    
    if not user_input:
        return jsonify({'error': 'Empty message'}), 400
    
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
            text_buffer = ""  # Simple accumulator instead of sentence buffer
            
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    text_buffer += content
                    
                    # Send text chunk
                    yield f"data: {json.dumps({'type': 'text_chunk', 'text': content})}\n\n"
                    
                    # Generate audio every ~50 characters or at sentence breaks
                    if len(text_buffer) >= 50 or any(text_buffer.endswith(p) for p in ['. ', '! ', '? ', '.\n', '!\n', '?\n']):
                        if text_buffer.strip():
                            print(f"[DEBUG] Generating audio for: {text_buffer.strip()[:50]}...")
                            audio = tts_processor.process_text_to_speech(text_buffer.strip())
                            print(f"[DEBUG] Audio bytes generated: {len(audio)}")
                            if len(audio) > 0:
                                audio_b64 = tts_processor.audio_to_base64(audio)
                                print(f"[DEBUG] Base64 length: {len(audio_b64)}")
                                yield f"data: {json.dumps({'type': 'audio_chunk', 'audio': audio_b64, 'text': text_buffer.strip()})}\n\n"
                            else:
                                print(f"[DEBUG] WARNING: No audio generated!")
                            text_buffer = ""
            
            # Send any remaining text as audio
            if text_buffer.strip():
                print(f"[DEBUG] Flushing remaining: {text_buffer.strip()[:50]}...")
                audio = tts_processor.process_text_to_speech(text_buffer.strip())
                print(f"[DEBUG] Flush audio bytes: {len(audio)}")
                if len(audio) > 0:
                    audio_b64 = tts_processor.audio_to_base64(audio)
                    yield f"data: {json.dumps({'type': 'audio_chunk', 'audio': audio_b64, 'text': text_buffer.strip()})}\n\n"
                else:
                    print(f"[DEBUG] WARNING: No audio in flush!")
            
            # Signal completion
            yield f"data: {json.dumps({'type': 'response_end'})}\n\n"
            
            # Update session
            session.add("user", user_input)
            session.add("assistant", full_response.strip())
                        
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

# =============================
# ROUTES
# =============================
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port)