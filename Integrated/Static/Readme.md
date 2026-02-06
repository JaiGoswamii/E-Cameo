# Jai Goswami's eCameo - Voice-Enabled Web Interface

A minimalist, attractive web interface for the voice-enabled chatbot with real-time TTS and animated avatar.

## Features

- 🎙️ **Real-time voice synthesis** using cloned voice
- 💬 **Streaming LLM responses** with OpenAI GPT-4
- 🎬 **Animated talking avatar** - GIF plays when speaking
- 🎨 **Minimalist design** with smooth animations
- 🔊 **Live audio playback** as sentences are generated
- ⚡ **WebSocket-based** for real-time communication

## Setup Instructions

### 1. Install Dependencies

```bash
pip install flask flask-socketio python-socketio openai pypdf pydantic python-dotenv torch numpy soundfile TTS
```

### 2. Prepare Your Assets

You need two images in the `static/` folder:

- `avatar.jpg` - Your static profile photo (shown when not speaking)
- `talking.gif` - Animated GIF of you talking (shown when TTS is playing)

**To create the talking GIF:**
- Record a short video of yourself talking (5-10 seconds)
- Use a tool like EZGIF (https://ezgif.com/video-to-gif) to convert it
- Crop it to a square aspect ratio
- Optimize to keep file size under 2MB

Place both files in `/static/`:
```
/static/
  ├── avatar.jpg
  ├── talking.gif
  ├── css/
  │   └── style.css
  └── js/
      └── chat.js
```

### 3. Configure Environment

Make sure your `.env` file contains:
```
OPENAI_API_KEY=your_openai_api_key_here
```

### 4. Update File Paths

In `app.py`, update these paths to match your system:
- `LATENTS_FILE` - Path to your voice latents file
- LinkedIn PDF path
- Summary text file path

### 5. Run the Application

```bash
python app.py
```

The server will start on `http://localhost:5000`

## How It Works

### Frontend Flow
1. User types a message and clicks send
2. Message is sent via WebSocket to Flask backend
3. Typing indicator appears
4. LLM streams response text back in real-time
5. Complete sentences trigger TTS generation
6. Audio chunks stream back and play sequentially
7. **Talking GIF plays while audio is playing**
8. Static avatar shows when not speaking

### Backend Flow
1. Flask receives message via WebSocket
2. Sends to OpenAI with streaming enabled
3. For each text chunk:
   - Emits text to frontend
   - Buffers until complete sentence
   - Generates TTS audio
   - Converts to base64 WAV
   - Emits audio chunk to frontend
4. Frontend queues and plays audio sequentially

### Avatar Animation
- `avatar-static` (jpg) - Default state, opacity: 1
- `avatar-talking` (gif) - Speaking state, opacity: 0 by default
- When audio plays: talking GIF becomes visible, static hidden
- When audio ends: static becomes visible, talking GIF hidden
- Sound waves animate below avatar during playback

## Customization

### Colors
Edit CSS variables in `static/css/style.css`:
```css
:root {
    --bg-dark: #0a0a0a;
    --accent: #00ff88;  /* Change to your brand color */
    --text-primary: #ffffff;
}
```

### Fonts
Currently uses:
- **Syne** - Display/headers (distinctive, modern)
- **JetBrains Mono** - Body text (monospace, tech feel)

To change fonts, update the Google Fonts import in `templates/index.html`

### Animation Speed
Adjust animation durations in the CSS:
- `@keyframes wave` - Sound wave animation
- `@keyframes pulse` - Status indicator pulse
- `.avatar-img` transition - Avatar swap speed

## Project Structure

```
.
├── app.py                  # Flask backend with WebSocket
├── templates/
│   └── index.html         # Main HTML template
├── static/
│   ├── css/
│   │   └── style.css      # Styling and animations
│   ├── js/
│   │   └── chat.js        # Frontend WebSocket logic
│   ├── avatar.jpg         # Static profile photo
│   └── talking.gif        # Animated talking GIF
└── README.md
```

## Troubleshooting

**Audio not playing:**
- Check browser console for errors
- Ensure WAV encoding is correct
- Try a different browser (Chrome recommended)

**GIF not animating:**
- Verify GIF file is properly formatted
- Check file path in HTML
- Ensure GIF is under 5MB for smooth performance

**WebSocket connection fails:**
- Check Flask-SocketIO is installed
- Verify port 5000 is not in use
- Check browser console for connection errors

**TTS generation slow:**
- First inference is slower (model loading)
- Subsequent sentences generate faster
- Consider using GPU for faster inference

## Browser Support

- ✅ Chrome/Edge (Recommended)
- ✅ Firefox
- ✅ Safari
- ⚠️ Older browsers may not support WebSocket audio streaming

## Performance Tips

1. **Optimize GIF**: Keep under 2MB for smooth transitions
2. **Use GPU**: TTS is faster with CUDA-enabled GPU
3. **Adjust sentence detection**: Modify regex in `SentenceBuffer` for faster/slower chunking
4. **Limit message history**: `MAX_QNA_PAIRS` controls context window

## Future Enhancements

- [ ] Add voice input (speech-to-text)
- [ ] Mobile-responsive improvements
- [ ] Multi-session support with session IDs
- [ ] Database integration for conversation history
- [ ] Admin panel for content management
- [ ] Analytics dashboard

## License

Private project for Jai Goswami's portfolio.