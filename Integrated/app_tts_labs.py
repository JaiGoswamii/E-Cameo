import os
import json
import queue
import threading
import base64
from typing import List, Dict, Optional
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader
from pydantic import BaseModel, Field
import torch
import numpy as np
from pathlib import Path
from elevenlabs.client import ElevenLabs
from elevenlabs.play import play
import re
import io
import wave

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
socketio = SocketIO(app, cors_allowed_origins="*")


# =============================
# LOAD LINKEDIN PDF
# =============================
reader = PdfReader("/Users/jg/projects/ecameo/LLM/Me/linkedin.pdf")
linkedin = ""
for page in reader.pages:
    text = page.extract_text()
    if text:
        linkedin += text + "\n"

# =============================
# LOAD TEXTUAL INFO
# =============================
with open("/Users/jg/projects/ecameo/LLM/Me/summary.txt", "r") as f:
    summary = f.read()

name = "Jai Goswami"

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
        self.sample_rate = 44100  # Add this line

    def process_text_to_speech(self, text: str) -> bytes:
        """Convert text to speech and return audio bytes"""
        try:
            # ElevenLabs returns an iterator of audio chunks
            audio_stream = client.text_to_speech.convert(
                text=text,
                voice_id=self.voice_id,
                model_id=self.model,
                output_format=self.output_format,
            )
            
            # Collect all audio chunks
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
# WEBSOCKET HANDLERS
# =============================
tts_processor = WebTTSProcessor("eleven_multilingual_v2", "QtEl85LECywm4BDbmbXB", "mp3_44100_128")

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('status', {'message': 'Connected to Jai\'s eCameo'})

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('send_message')
def handle_message(data):
    user_input = data.get('message', '').strip()
    
    if not user_input:
        return
    
    # Signal that we're starting to respond
    emit('response_start', {})
    
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
        current_tool_call = None
        
        for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response += content
                
                # Send text to client
                emit('text_chunk', {'text': content})
                
                # Check for complete sentences and generate audio
                complete_sentences = sentence_buffer.add_text(content)
                for sentence in complete_sentences:
                    audio = tts_processor.process_text_to_speech(sentence)
                    if len(audio) > 0:
                        audio_b64 = tts_processor.audio_to_base64(audio)
                        # Send both audio AND the text it represents for subtitle sync
                        emit('audio_chunk', {'audio': audio_b64, 'text': sentence})
            
            # Check for tool calls
            if chunk.choices[0].delta.tool_calls:
                for tool_call_delta in chunk.choices[0].delta.tool_calls:
                    if tool_call_delta.index is not None:
                        # New tool call
                        if len(tool_calls) <= tool_call_delta.index:
                            tool_calls.append({
                                "id": tool_call_delta.id,
                                "name": tool_call_delta.function.name if tool_call_delta.function.name else "",
                                "arguments": tool_call_delta.function.arguments if tool_call_delta.function.arguments else ""
                            })
                        else:
                            # Append to existing tool call
                            if tool_call_delta.function.arguments:
                                tool_calls[tool_call_delta.index]["arguments"] += tool_call_delta.function.arguments
        
        # Handle remaining text
        if not tool_calls:
            remaining = sentence_buffer.flush()
            if remaining:
                audio = tts_processor.process_text_to_speech(remaining)
                if len(audio) > 0:
                    audio_b64 = tts_processor.audio_to_base64(audio)
                    # Send both audio AND text for subtitle sync
                    emit('audio_chunk', {'audio': audio_b64, 'text': remaining})
        
        # Signal completion
        emit('response_end', {})
        
        # Update session
        if not tool_calls:
            session.add("user", user_input)
            session.add("assistant", full_response.strip())
        else:
            # Handle tool calls
            for tool_call in tool_calls:
                try:
                    args = json.loads(tool_call["arguments"])
                    payload = {
                        "tool": tool_call["name"],
                        "data": args,
                    }
                    emit('tool_call', payload)
                except json.JSONDecodeError as e:
                    print(f"Error parsing tool call arguments: {e}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        emit('error', {'message': str(e)})

# =============================
# ROUTES
# =============================
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5001)