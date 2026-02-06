# Voice-Enabled eCameo Chatbot 🎙️

An intelligent chatbot that responds in **Jai Goswami's cloned voice** by combining OpenAI's LLM streaming with XTTS v2 text-to-speech synthesis.

## 🎯 Overview

This project integrates:
- **OpenAI GPT-4o-mini** for intelligent conversation
- **XTTS v2** for voice cloning and TTS generation
- **Streaming architecture** for minimal latency
- **Parallel processing** for real-time audio generation

## 📦 Project Structure

```
.
├── voice_chatbot.py              # Basic version: Sequential processing
├── voice_chatbot_parallel.py     # Advanced: Parallel streaming TTS
└── README.md                     # This file
```

## 🔧 Architecture

### Version 1: Sequential Processing (`voice_chatbot.py`)

**Flow:**
```
User Input → LLM Streams Response → Complete Response → Generate TTS → Save Audio
```

**Pros:**
- Simpler implementation
- Easier to debug
- Complete text available before TTS

**Cons:**
- User waits for complete LLM response before TTS starts
- Longer total response time

### Version 2: Parallel Processing (`voice_chatbot_parallel.py`) ⭐ **RECOMMENDED**

**Flow:**
```
User Input → LLM Streams Response ──┬→ Display text chunk
                                     └→ Detect complete sentence
                                        └→ Queue for TTS (parallel thread)
                                           └→ Generate audio chunk
                                              └→ Accumulate chunks
                                                 └→ Save complete audio
```

**Features:**
- **Real-time sentence detection** using regex pattern matching
- **Background TTS thread** processes sentences as they arrive
- **Queue-based architecture** for thread-safe communication
- **Smart buffering** accumulates partial text until sentence boundary

**Pros:**
- ✅ Minimal perceived latency
- ✅ TTS generation happens during LLM streaming
- ✅ First audio chunks ready while LLM still generating
- ✅ Better user experience

**Cons:**
- More complex architecture
- Requires thread management

## 🚀 Setup

### Prerequisites

```bash
pip install openai python-dotenv pypdf pydantic torch numpy soundfile TTS
```

### Environment Variables

Create `.env` file:
```
OPENAI_API_KEY=your_openai_api_key_here
```

### File Structure

Ensure these files exist:
```
/Users/jg/projects/ecameo/
├── Voice_Cloning/
│   ├── src/jai_voice_latents.pt          # Pre-computed voice latents
│   └── Outputs/                           # Generated audio files
├── LLM/Me/linkedin.pdf                    # LinkedIn profile PDF
└── Me/summary.txt                         # Personal summary text
```

## 💻 Usage

### Basic Version

```bash
python voice_chatbot.py
```

### Parallel Version (Recommended)

```bash
python voice_chatbot_parallel.py
```

### Example Interaction

```
💬 You: What's your background in AI?

[LLM] I'm a GenAI engineer currently exploring the field of 
generative AI. I have experience with...

[TTS] 🎵 Generating: I'm a GenAI engineer currently exploring...
[TTS] 🎵 Generating: I have experience with large language models...
[TTS] ✓ Complete audio saved: response_1.wav
```

## 🔍 Key Components

### 1. **SentenceBuffer** (Parallel version only)
```python
class SentenceBuffer:
    """Detects complete sentences from streaming text"""
```
- Uses regex to identify sentence boundaries (`.!?`)
- Buffers partial text until complete sentence detected
- Returns list of complete sentences for TTS processing

### 2. **ParallelTTSProcessor**
```python
class ParallelTTSProcessor:
    """Processes TTS in parallel as text streams"""
```
- **Background thread** continuously polls sentence queue
- Generates audio for each sentence independently
- Accumulates audio chunks with natural pauses
- Thread-safe queue operations

### 3. **Stream Processing**
```python
def stream_chat_with_parallel_voice():
    # Start background TTS thread
    tts_processor.start_processing()
    
    # Stream from LLM
    for event in stream:
        # Display to user
        print(event.delta)
        
        # Check for complete sentences
        sentences = sentence_buffer.add_text(event.delta)
        for sentence in sentences:
            tts_processor.add_sentence(sentence)  # Non-blocking
```

## 🎨 Customization

### Adjust Sentence Pause Duration

In `ParallelTTSProcessor.tts_worker()`:
```python
# Change 0.3 to desired pause in seconds
pause = np.zeros(int(self.sample_rate * 0.3))
```

### Modify Sentence Detection

In `SentenceBuffer.__init__()`:
```python
# Current: Detects . ! ?
self.sentence_pattern = re.compile(r'([.!?]+)(?:\s+|$)')

# Example: Also detect colons and semicolons
self.sentence_pattern = re.compile(r'([.!?;:]+)(?:\s+|$)')
```

### Change TTS Model

```python
# Current model
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")

# Alternative models
tts = TTS("tts_models/en/ljspeech/tacotron2-DDC")
```

## 🔧 Troubleshooting

### Audio sounds choppy
- Increase pause duration between sentences
- Check CPU/GPU usage during generation
- Consider reducing LLM streaming speed

### TTS generation too slow
- Use GPU for XTTS inference
- Reduce sentence length threshold
- Consider faster TTS model

### Thread synchronization issues
```python
# Increase timeout in tts_worker
sentence = self.sentence_queue.get(timeout=1.0)  # Increase from 0.1

# Increase join timeout in finish_and_save
self.processing_thread.join(timeout=10)  # Increase from 5
```

### Memory issues with long conversations
```python
# Reduce MAX_QNA_PAIRS to limit memory
MAX_QNA_PAIRS = 3  # Keep only last 3 exchanges
```

## 📊 Performance Comparison

| Metric | Sequential | Parallel |
|--------|-----------|----------|
| Time to first audio | ~15-20s | ~3-5s |
| Total response time | ~20-25s | ~15-18s |
| User perception | Slower | Much faster |
| Complexity | Low | Medium |

*Times approximate for 200-word response*

## 🚀 Future Enhancements

### 1. **Real-time Audio Streaming**
Instead of saving complete audio file, stream audio chunks to user:
```python
# Play audio as it's generated
import pyaudio
p = pyaudio.PyAudio()
stream = p.open(format=pyaudio.paFloat32, channels=1, rate=24000, output=True)
stream.write(audio_chunk.tobytes())
```

### 2. **Web Interface**
- FastAPI backend with WebSocket
- React frontend with audio player
- Real-time transcription display

### 3. **Voice Activity Detection**
- Detect when user stops speaking
- Auto-trigger response generation

### 4. **Multi-turn Audio Conversation**
- Maintain conversation history in audio format
- "Replay conversation" feature

### 5. **Emotion Detection & Synthesis**
- Analyze user sentiment
- Adjust TTS emotion/tone accordingly

## 🛡️ Production Considerations

### For Web Deployment:

1. **API Rate Limiting**
```python
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

@app.post("/chat", dependencies=[Depends(RateLimiter(times=10, seconds=60))])
```

2. **Async Processing**
```python
import asyncio

async def async_tts_generation():
    loop = asyncio.get_event_loop()
    audio = await loop.run_in_executor(None, tts_processor.process_text_to_speech, text)
```

3. **Caching**
```python
from functools import lru_cache

@lru_cache(maxsize=100)
def get_cached_audio(text: str):
    return tts_processor.process_text_to_speech(text)
```

4. **Resource Management**
```python
# Limit concurrent TTS generations
semaphore = asyncio.Semaphore(5)

async with semaphore:
    audio = await generate_audio(text)
```

## 📝 License

This is a personal project for Jai Goswami's eCameo portfolio.

## 🤝 Contributing

This is a personal project, but suggestions are welcome!

## 📧 Contact

For questions about this project, use the chatbot's `ContactMe` tool or reach out through the eCameo website.

---

**Built with ❤️ using OpenAI GPT-4o-mini and XTTS v2**