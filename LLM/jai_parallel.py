import os
import json
import queue
import threading
from typing import List, Dict, Optional
from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader
from pydantic import BaseModel, Field
from openai import pydantic_function_tool
import torch
import numpy as np
import soundfile as sf
import sounddevice as sd
from pathlib import Path
from TTS.api import TTS
import re

# =============================
# CONFIG
# =============================
MODEL = "gpt-4o-mini"
MAX_QNA_PAIRS = 5
LATENTS_FILE = "/Users/jg/projects/ecameo/Voice_Cloning/src/jai_voice_latents.pt"
OUTPUT_DIR = "/Users/jg/projects/ecameo/Voice_Cloning/Outputs"

# Create output directory
Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

# Force .env to override everything
load_dotenv(override=True)

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY not found in .env")

client = OpenAI(api_key=api_key)

# =============================
# LOAD TTS MODEL & LATENTS
# =============================
print("Loading TTS model...")
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
xtts_model = tts.synthesizer.tts_model

print("Loading voice latents...")
latents = torch.load(LATENTS_FILE, map_location="cpu")

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
    pydantic_function_tool(GetAnswerLater),
    pydantic_function_tool(ContactMe),
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


# =============================
# PARALLEL TTS PROCESSOR WITH PLAYBACK
# =============================
class ParallelTTSProcessor:
    """Processes TTS in parallel as text streams in and plays audio in real-time"""
    
    def __init__(self, model, latents, output_dir):
        self.model = model
        self.latents = latents
        self.output_dir = output_dir
        self.sample_rate = 24000
        
        # Queues for parallel processing
        self.sentence_queue = queue.Queue()
        self.playback_queue = queue.Queue()
        self.audio_chunks = []
        
        self.processing_thread = None
        self.playback_thread = None
        self.stop_signal = threading.Event()
        
    def process_text_to_speech(self, text: str) -> np.ndarray:
        """Convert text to speech and return audio array"""
        try:
            out = self.model.inference(
                text=text,
                language="en",
                gpt_cond_latent=self.latents["gpt_cond_latent"],
                speaker_embedding=self.latents["speaker_embedding"],
            )
            
            # Handle dict output
            if isinstance(out, dict):
                wav = out.get("wav", None)
            else:
                wav = out
            
            # Handle list output
            if isinstance(wav, list):
                wav = wav[0]
            
            # Handle torch tensor
            if isinstance(wav, torch.Tensor):
                wav = wav.detach().cpu().numpy()
            
            # Force numpy array
            wav = np.asarray(wav)
            
            # Handle scalar / empty edge cases
            if wav.ndim == 0:
                wav = wav.reshape(1)
            
            # Final safety: ensure 1-D float32
            wav = wav.astype(np.float32).flatten()
            
            return wav
        except Exception as e:
            print(f"\n[TTS ERROR] Failed to generate audio: {e}")
            return np.array([])
    
    def tts_worker(self):
        """Background worker that processes sentences from the queue"""
        while not self.stop_signal.is_set():
            try:
                sentence = self.sentence_queue.get(timeout=0.1)
                if sentence is None:  # Poison pill
                    self.sentence_queue.task_done()
                    break
                    
                if sentence.strip():
                    print(f"\n[TTS] 🎵 Generating: {sentence[:60]}...")
                    audio = self.process_text_to_speech(sentence)
                    if len(audio) > 0:
                        self.audio_chunks.append(audio)
                        # Send to playback queue immediately
                        self.playback_queue.put(audio)
                        # Add small pause between sentences
                        pause = np.zeros(int(self.sample_rate * 0.3))
                        self.audio_chunks.append(pause)
                        self.playback_queue.put(pause)
                        
                self.sentence_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"\n[TTS ERROR] Worker error: {e}")
    
    def playback_worker(self):
        """Background worker that plays audio chunks as they become available"""
        while not self.stop_signal.is_set():
            try:
                audio_chunk = self.playback_queue.get(timeout=0.1)
                if audio_chunk is None:  # Poison pill
                    self.playback_queue.task_done()
                    break
                
                # Play the audio chunk
                if len(audio_chunk) > 0:
                    print(f"[AUDIO] 🔊 Playing {len(audio_chunk)/self.sample_rate:.2f}s")
                    sd.play(audio_chunk, self.sample_rate)
                    sd.wait()  # Wait until playback is finished
                
                self.playback_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"\n[PLAYBACK ERROR] {e}")
    
    def start_processing(self):
        """Start the background TTS processing and playback threads"""
        self.audio_chunks = []
        self.stop_signal.clear()
        
        # Start TTS generation thread
        self.processing_thread = threading.Thread(target=self.tts_worker, daemon=True)
        self.processing_thread.start()
        
        # Start audio playback thread
        self.playback_thread = threading.Thread(target=self.playback_worker, daemon=True)
        self.playback_thread.start()
    
    def add_sentence(self, sentence: str):
        """Add a sentence to the processing queue"""
        self.sentence_queue.put(sentence)
    
    def finish_and_save(self, output_file: str) -> Optional[str]:
        """Signal completion and save the final audio file"""
        # Send poison pills to stop workers
        self.sentence_queue.put(None)
        
        # Wait for all TTS processing to complete
        self.sentence_queue.join()
        
        # Send poison pill to playback worker
        self.playback_queue.put(None)
        
        # Wait for all playback to complete
        self.playback_queue.join()
        
        if self.processing_thread:
            self.processing_thread.join(timeout=5)
        
        if self.playback_thread:
            self.playback_thread.join(timeout=5)
        
        # Concatenate and save
        if self.audio_chunks:
            final_audio = np.concatenate(self.audio_chunks)
            sf.write(output_file, final_audio, self.sample_rate)
            print(f"\n[TTS] ✓ Complete audio saved: {output_file}")
            return output_file
        return None


class SentenceBuffer:
    """Buffers streaming text and detects complete sentences"""
    
    def __init__(self):
        self.buffer = ""
        self.sentence_pattern = re.compile(r'([.!?]+)(?:\s+|$)')
    
    def add_text(self, text: str) -> List[str]:
        """Add text to buffer and return any complete sentences"""
        self.buffer += text
        sentences = []
        
        # Find all sentence endings
        matches = list(self.sentence_pattern.finditer(self.buffer))
        
        if matches:
            last_match = matches[-1]
            end_pos = last_match.end()
            
            # Split buffer at last sentence boundary
            completed = self.buffer[:end_pos]
            self.buffer = self.buffer[end_pos:]
            
            # Split completed text into individual sentences
            sentence_parts = self.sentence_pattern.split(completed)
            
            # Reconstruct sentences (text + punctuation)
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
# STREAMING CHAT WITH PARALLEL VOICE
# =============================
def stream_chat_with_parallel_voice(session: SessionMemory, user_input: str, 
                                   tts_processor: ParallelTTSProcessor, response_id: int):
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(session.get())
    messages.append({"role": "user", "content": user_input})

    stream = client.responses.stream(
        model=MODEL,
        input=messages,
        tools=TOOLS,
    )

    full_response = ""
    tool_call = None
    sentence_buffer = SentenceBuffer()
    
    # Start TTS processing in background
    tts_processor.start_processing()

    print("\n[LLM] ", end="", flush=True)
    
    with stream as s:
        for event in s:
            if event.type == "response.output_text.delta":
                print(event.delta, end="", flush=True)
                full_response += event.delta
                
                # Check for complete sentences and send to TTS
                complete_sentences = sentence_buffer.add_text(event.delta)
                for sentence in complete_sentences:
                    tts_processor.add_sentence(sentence)

            elif event.type == "response.tool_call":
                tool_call = event
                break

    print()  # New line after streaming completes
    
    # Handle any remaining text in buffer
    if not tool_call:
        remaining = sentence_buffer.flush()
        if remaining:
            tts_processor.add_sentence(remaining)
        
        # Finalize TTS and save audio
        if full_response.strip():
            output_file = os.path.join(tts_processor.output_dir, f"response_{response_id}.wav")
            print("\n[TTS] Finalizing audio...")
            tts_processor.finish_and_save(output_file)
    
    return full_response.strip(), tool_call


# =============================
# TOOL HANDLER
# =============================
def handle_tool(tool_call, session: SessionMemory):
    args = json.loads(tool_call.arguments)
    payload = {
        "tool": tool_call.name,
        "data": args,
    }

    print("\n--- TOOL PAYLOAD ---")
    print(json.dumps(payload, indent=2))
    print("--------------------\n")


# =============================
# MAIN LOOP
# =============================
def main():
    session = SessionMemory()
    tts_processor = ParallelTTSProcessor(xtts_model, latents, OUTPUT_DIR)
    response_counter = 0
    
    print("\n" + "="*70)
    print(" 🎙️  Voice-Enabled Chatbot - Jai Goswami's eCameo")
    print("="*70)
    print(" Features:")
    print("  • Real-time LLM streaming")
    print("  • Parallel TTS generation (sentence-by-sentence)")
    print("  • LIVE audio playback as segments are generated")
    print("  • Voice output in Jai's cloned voice")
    print("="*70)
    print(" Commands: 'exit' or 'quit' to end")
    print("="*70 + "\n")

    while True:
        user_input = input("\n💬 You: ").strip()
        if user_input.lower() in {"exit", "quit"}:
            print("\n👋 Goodbye!")
            break

        if not user_input:
            continue

        response_counter += 1
        response, tool_call = stream_chat_with_parallel_voice(session, user_input, tts_processor, response_counter)

        if tool_call:
            handle_tool(tool_call, session)
        else:
            session.add("user", user_input)
            session.add("assistant", response)


if __name__ == "__main__":
    main()