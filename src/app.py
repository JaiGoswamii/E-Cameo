import os
import json
from typing import List, Dict, Optional
from flask import Flask, render_template, request, Response, jsonify
from dotenv import load_dotenv
from openai import OpenAI
from PyPDF2 import PdfReader
from pydantic import BaseModel, Field
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
client = ElevenLabs(
    api_key=os.getenv("ELEVENLABS_API_KEY")
)

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
# TOOL SCHEMAS
# =============================
class GetAnswerLater(BaseModel):
    user_email: str = Field(..., description="Email address provided by the user")
    question: str = Field(..., description="The unanswered user question")
    conversation_summary: str = Field(..., description="Summary of the last 5 QnAs")


class ContactMe(BaseModel):
    user_email: str = Field(..., description="User's email address")
    reason: str = Field(..., description="Why the user wants to get in touch")
    conversation_summary: str = Field(..., description="Summary of the last 5 QnAs")


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_answer_later",
            "description": "Save a question for later response when you don't know the answer",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_email": {
                        "type": "string",
                        "description": "Email address provided by the user"
                    },
                    "question": {
                        "type": "string",
                        "description": "The unanswered user question"
                    },
                    "conversation_summary": {
                        "type": "string",
                        "description": "Summary of the last 5 QnAs"
                    }
                },
                "required": ["user_email", "question", "conversation_summary"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "contact_me",
            "description": "Allow user to request direct contact",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_email": {
                        "type": "string",
                        "description": "User's email address"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Why the user wants to get in touch"
                    },
                    "conversation_summary": {
                        "type": "string",
                        "description": "Summary of the last 5 QnAs"
                    }
                },
                "required": ["user_email", "reason", "conversation_summary"]
            }
        }
    }
]

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
    def __init__(self, model, voice_id, output_format):
        self.model = model
        self.voice_id = voice_id
        self.output_format = output_format
        self.sample_rate = 44100

    def process_text_to_speech(self, text: str) -> bytes:
        """Convert text to speech and return audio bytes"""
        try:
            audio_stream = client.text_to_speech.convert(
                text=text,
                voice_id=self.voice_id,
                model_id=self.model,
                output_format=self.output_format,
            )
            
            audio_bytes = b''.join(audio_stream)
            return audio_bytes
            
        except Exception as e:
            print(f"[TTS ERROR] Failed to generate audio: {e}")
            return b''
    
    def audio_to_base64(self, audio_bytes: bytes) -> str:
        """Convert audio bytes to base64"""
        return base64.b64encode(audio_bytes).decode('utf-8')


class SentenceBuffer:
    """Buffers streaming text and detects complete sentences"""
    
    def __init__(self):
        self.buffer = ""
        self.sentence_pattern = re.compile(r'([.!?]+)(?:\s+|$)')
    
    def add_text(self, text: str) -> List[str]:
        """Add text to buffer and return any complete sentences"""
        self.buffer += text
        sentences = []
        
        matches = list(self.sentence_pattern.finditer(self.buffer))
        
        if matches:
            last_match = matches[-1]
            end_pos = last_match.end()
            
            completed = self.buffer[:end_pos]
            self.buffer = self.buffer[end_pos:]
            
            sentence_parts = self.sentence_pattern.split(completed)
            
            for i in range(0, len(sentence_parts) - 1, 2):
                if sentence_parts[i].strip():
                    sentence = sentence_parts[i].strip() + sentence_parts[i + 1]
                    sentences.append(sentence)
        
        return sentences
    
    def flush(self) -> Optional[str]:
        """Get any remaining text in buffer"""
        if self.buffer.strip():
            remaining = self.buffer.strip()
            self.buffer = ""
            return remaining
        return None


# =============================
# SSE CHAT ENDPOINT
# =============================
voice_id = os.getenv("ELEVENLABS_VOICE_ID", "QtEl85LECywm4BDbmbXB")
tts_processor = WebTTSProcessor("eleven_multilingual_v2", voice_id, "mp3_44100_128")

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
                tools=TOOLS,
                stream=True,
            )
            
            full_response = ""
            tool_calls = []
            sentence_buffer = SentenceBuffer()
            
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    
                    # Send text chunk
                    yield f"data: {json.dumps({'type': 'text_chunk', 'text': content})}\n\n"
                    
                    # Generate audio for complete sentences
                    complete_sentences = sentence_buffer.add_text(content)
                    for sentence in complete_sentences:
                        audio = tts_processor.process_text_to_speech(sentence)
                        if len(audio) > 0:
                            audio_b64 = tts_processor.audio_to_base64(audio)
                            yield f"data: {json.dumps({'type': 'audio_chunk', 'audio': audio_b64, 'text': sentence})}\n\n"
                
                # Handle tool calls
                if chunk.choices[0].delta.tool_calls:
                    for tool_call_delta in chunk.choices[0].delta.tool_calls:
                        if tool_call_delta.index is not None:
                            if len(tool_calls) <= tool_call_delta.index:
                                tool_calls.append({
                                    "id": tool_call_delta.id,
                                    "name": tool_call_delta.function.name or "",
                                    "arguments": tool_call_delta.function.arguments or ""
                                })
                            else:
                                if tool_call_delta.function.arguments:
                                    tool_calls[tool_call_delta.index]["arguments"] += tool_call_delta.function.arguments
            
            # Flush remaining text
            if not tool_calls:
                remaining = sentence_buffer.flush()
                if remaining:
                    audio = tts_processor.process_text_to_speech(remaining)
                    if len(audio) > 0:
                        audio_b64 = tts_processor.audio_to_base64(audio)
                        yield f"data: {json.dumps({'type': 'audio_chunk', 'audio': audio_b64, 'text': remaining})}\n\n"
            
            # Signal completion
            yield f"data: {json.dumps({'type': 'response_end'})}\n\n"
            
            # Update session
            if not tool_calls:
                session.add("user", user_input)
                session.add("assistant", full_response.strip())
            else:
                for tool_call in tool_calls:
                    try:
                        args = json.loads(tool_call["arguments"])
                        payload = {"tool": tool_call["name"], "data": args}
                        yield f"data: {json.dumps({'type': 'tool_call', **payload})}\n\n"
                    except json.JSONDecodeError as e:
                        print(f"Error parsing tool call: {e}")
                        
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
    app.run(debug=True, host='0.0.0.0', port=port)