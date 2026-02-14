const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const avatarStatic = document.getElementById('avatar-static');
const avatarTalking = document.getElementById('avatar-talking');
const subtitleText = document.getElementById('subtitle-text');
const subtitles = document.getElementById('subtitles');
const audioPlayer = document.getElementById('audio-player');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const chatMessages = document.getElementById('chat-messages');
const typingIndicator = document.getElementById('typing-indicator');

let audioQueue = [];
let isPlaying = false;
let currentAssistantMessage = null;
let audioUnlocked = false;

// CRITICAL FIX: Unlock audio immediately on ANY user interaction
document.addEventListener('DOMContentLoaded', () => {
    // Multiple triggers to ensure audio works
    const unlockEvents = ['click', 'touchstart', 'keydown'];
    
    unlockEvents.forEach(event => {
        document.addEventListener(event, unlockAudio, { once: true });
    });
    
    // Also unlock on input focus
    userInput.addEventListener('focus', unlockAudio, { once: true });
});

// Unlock audio on first user interaction
async function unlockAudio() {
    if (audioUnlocked) return;
    
    console.log('[AUDIO] Attempting to unlock audio context');
    
    try {
        // CRITICAL FIX: Use Web Audio API instead of HTML5 audio for unlock
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (AudioContext) {
            const ctx = new AudioContext();
            const buffer = ctx.createBuffer(1, 1, 22050);
            const source = ctx.createBufferSource();
            source.buffer = buffer;
            source.connect(ctx.destination);
            source.start(0);
            
            // Resume context (required on some browsers)
            if (ctx.state === 'suspended') {
                await ctx.resume();
            }
            
            console.log('[AUDIO] Web Audio API unlocked');
        }
        
        // Also unlock HTML5 audio element
        audioPlayer.volume = 0.01;
        // Use a data URI that's guaranteed to work
        audioPlayer.src = 'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=';
        
        const playPromise = audioPlayer.play();
        
        if (playPromise !== undefined) {
            await playPromise;
            audioPlayer.pause();
            audioPlayer.currentTime = 0;
            audioPlayer.volume = 1.0;
            audioUnlocked = true;
            console.log('[AUDIO] HTML5 audio unlocked successfully');
        }
    } catch (e) {
        console.warn('[AUDIO] Unlock attempt failed:', e.name, e.message);
        // Mark as unlocked anyway - will fail gracefully on first real play
        audioUnlocked = true;
    }
}

function setStatus(message, isReady = true) {
    statusText.textContent = message;
    statusDot.className = `status-dot ${isReady ? 'ready' : 'busy'}`;
}

function showTalkingAvatar() {
    avatarStatic.classList.remove('active');
    avatarTalking.classList.add('active');
}

function showStaticAvatar() {
    avatarTalking.classList.remove('active');
    avatarStatic.classList.add('active');
}

function showSubtitles(text) {
    subtitleText.textContent = text;
    subtitles.classList.add('visible');
}

function hideSubtitles() {
    subtitles.classList.remove('visible');
}

function addUserMessage(text) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message user';
    messageDiv.innerHTML = `<div class="message-bubble">${escapeHtml(text)}</div>`;
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

function createAssistantMessage() {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    messageDiv.innerHTML = `<div class="message-bubble"></div>`;
    chatMessages.appendChild(messageDiv);
    currentAssistantMessage = messageDiv.querySelector('.message-bubble');
    scrollToBottom();
    return currentAssistantMessage;
}

function appendToAssistantMessage(text) {
    if (currentAssistantMessage) {
        currentAssistantMessage.textContent += text;
        scrollToBottom();
    }
}

function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// FIXED: Better audio playback with error handling
async function playNextAudio() {
    if (isPlaying || audioQueue.length === 0) return;
    
    isPlaying = true;
    const {audio, text} = audioQueue.shift();
    
    console.log('[AUDIO] Playing:', {
        textLength: text.length,
        audioLength: audio.length,
        queueRemaining: audioQueue.length
    });
    
    // CRITICAL: Validate audio data first
    if (!audio || audio.length < 100) {
        console.error('[AUDIO] Invalid audio data - skipping');
        isPlaying = false;
        if (audioQueue.length > 0) {
            playNextAudio();
        }
        return;
    }
    
    showTalkingAvatar();
    showSubtitles(text);
    
    // CRITICAL: Clean up previous audio
    audioPlayer.pause();
    audioPlayer.currentTime = 0;
    audioPlayer.src = '';
    
    // Small delay to ensure cleanup
    await new Promise(resolve => setTimeout(resolve, 50));
    
    // CRITICAL: Set up event handlers BEFORE changing src
    audioPlayer.onended = () => {
        console.log('[AUDIO] Playback ended');
        isPlaying = false;
        hideSubtitles();
        if (audioQueue.length > 0) {
            playNextAudio();
        } else {
            showStaticAvatar();
            setStatus('Ready to chat', true);
        }
    };
    
    audioPlayer.onerror = (e) => {
        console.error('[AUDIO] Playback error:', {
            error: e,
            networkState: audioPlayer.networkState,
            readyState: audioPlayer.readyState,
            errorCode: audioPlayer.error ? audioPlayer.error.code : 'unknown',
            errorMessage: audioPlayer.error ? audioPlayer.error.message : 'unknown'
        });
        isPlaying = false;
        hideSubtitles();
        if (audioQueue.length > 0) {
            playNextAudio();
        } else {
            showStaticAvatar();
            setStatus('Audio error - chat continues', true);
        }
    };
    
    // Set the audio source with proper MIME type
    audioPlayer.src = `data:audio/mpeg;base64,${audio}`;
    
    // Force load
    audioPlayer.load();
    
    // Small delay before play
    await new Promise(resolve => setTimeout(resolve, 50));
    
    // Attempt to play
    try {
        await audioPlayer.play();
        console.log('[AUDIO] Started playing successfully');
    } catch (err) {
        console.error('[AUDIO] Play failed:', {
            name: err.name,
            message: err.message
        });
        
        // If autoplay blocked, show user prompt
        if (err.name === 'NotAllowedError') {
            console.log('[AUDIO] Autoplay blocked - user interaction required');
            setStatus('Click to enable audio', true);
            
            // Wait for next user interaction
            const enableAudio = async () => {
                audioUnlocked = false;
                await unlockAudio();
                
                // Retry this audio
                try {
                    await audioPlayer.play();
                    console.log('[AUDIO] Retry successful after user interaction');
                    document.removeEventListener('click', enableAudio);
                } catch (retryErr) {
                    console.error('[AUDIO] Retry still failed:', retryErr);
                    isPlaying = false;
                    if (audioQueue.length > 0) {
                        playNextAudio();
                    }
                }
            };
            
            document.addEventListener('click', enableAudio, { once: true });
        } else {
            isPlaying = false;
            if (audioQueue.length > 0) {
                playNextAudio();
            }
        }
    }
}

async function sendMessage(message) {
    if (!message.trim()) return;
    
    // CRITICAL: Force audio unlock on first message
    if (!audioUnlocked) {
        console.log('[CHAT] First message - unlocking audio');
        await unlockAudio();
        
        // Give browser time to process unlock
        await new Promise(resolve => setTimeout(resolve, 100));
    }
    
    addUserMessage(message);
    setStatus('Thinking...', false);
    userInput.value = '';
    userInput.disabled = true;
    sendBtn.disabled = true;
    
    console.log('[CHAT] Sending message:', message);
    
    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({message})
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        
        while (true) {
            const {done, value} = await reader.read();
            if (done) {
                console.log('[CHAT] Stream complete');
                break;
            }
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            
            // Keep the last incomplete line in buffer
            buffer = lines.pop() || '';
            
            let currentData = '';
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    currentData += line.slice(6);
                } else if (line === '' && currentData) {
                    // Empty line marks end of SSE message
                    try {
                        const data = JSON.parse(currentData);
                        
                        console.log('[CHAT] Event:', data.type);
                        
                        switch(data.type) {
                            case 'start':
                            case 'response_start':
                                setStatus('Responding...', false);
                                typingIndicator.classList.add('active');
                                createAssistantMessage();
                                break;
                            
                            case 'text':
                            case 'text_chunk':
                                // Display ALL text immediately as it streams
                                appendToAssistantMessage(data.text);
                                typingIndicator.classList.remove('active');
                                break;
                            
                            case 'audio':
                            case 'audio_chunk':
                                // Queue audio for playback
                                console.log('[CHAT] Received audio chunk:', {
                                    textLength: data.text?.length || 0,
                                    audioLength: data.audio?.length || 0
                                });
                                
                                if (data.audio && data.audio.length > 0) {
                                    audioQueue.push({
                                        audio: data.audio, 
                                        text: data.text || ''
                                    });
                                    playNextAudio();
                                } else {
                                    console.warn('[CHAT] Empty audio chunk received');
                                }
                                break;
                            
                            case 'end':
                            case 'response_end':
                                typingIndicator.classList.remove('active');
                                currentAssistantMessage = null;
                                if (audioQueue.length === 0 && !isPlaying) {
                                    setStatus('Ready to chat', true);
                                }
                                userInput.disabled = false;
                                sendBtn.disabled = false;
                                userInput.focus();
                                break;
                            
                            case 'tool_call':
                                console.log('[CHAT] Tool:', data);
                                break;
                                
                            case 'error':
                                console.error('[CHAT] Error:', data.message);
                                typingIndicator.classList.remove('active');
                                setStatus('Error occurred', true);
                                userInput.disabled = false;
                                sendBtn.disabled = false;
                                break;
                        }
                        
                        currentData = '';
                    } catch (parseError) {
                        console.warn('[CHAT] Parse error:', parseError, 'Data:', currentData);
                        currentData = '';
                    }
                }
            }
        }
    } catch (error) {
        console.error('[CHAT] Fetch error:', error);
        setStatus('Connection error - retry', true);
        userInput.disabled = false;
        sendBtn.disabled = false;
        userInput.focus();
    }
}

sendBtn.addEventListener('click', () => {
    sendMessage(userInput.value);
});

userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendMessage(userInput.value);
    }
});

// Focus input on page load
userInput.focus();

// Initial status
setStatus('Ready to chat', true);
console.log('[INIT] Chat interface ready');