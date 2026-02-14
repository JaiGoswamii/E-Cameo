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
        // Create a silent audio buffer and play it
        audioPlayer.volume = 0.01; // Very quiet
        audioPlayer.src = 'data:audio/mp3;base64,SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4Ljc2LjEwMAAAAAAAAAAAAAAA//tQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWGluZwAAAA8AAAACAAADhAC7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7//////////////////////////////////////////////////////////////////8AAAAATGF2YzU4LjEzAAAAAAAAAAAAAAAAJAAAAAAAAAAAA4S+T3idAAAAAAAAAAAAAAAAAAAA//sQZAAP8AAAaQAAAAgAAA0gAAABAAABpAAAACAAADSAAAAETEFNRTMuMTAwVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//sQZDwP8AAAaQAAAAgAAA0gAAABAAABpAAAACAAADSAAAAEVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV';
        
        const playPromise = audioPlayer.play();
        
        if (playPromise !== undefined) {
            await playPromise;
            audioPlayer.pause();
            audioPlayer.currentTime = 0;
            audioPlayer.volume = 1.0; // Restore volume
            audioUnlocked = true;
            console.log('[AUDIO] Audio unlocked successfully');
        }
    } catch (e) {
        console.warn('[AUDIO] Failed to unlock:', e);
        // Try again on next interaction
        setTimeout(() => {
            audioUnlocked = false;
        }, 100);
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
    
    showTalkingAvatar();
    showSubtitles(text);
    
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
            errorCode: audioPlayer.error ? audioPlayer.error.code : 'unknown'
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
    
    // CRITICAL: Validate base64 data
    if (!audio || audio.length < 100) {
        console.error('[AUDIO] Invalid audio data');
        isPlaying = false;
        hideSubtitles();
        if (audioQueue.length > 0) {
            playNextAudio();
        }
        return;
    }
    
    // Set the audio source
    audioPlayer.src = `data:audio/mp3;base64,${audio}`;
    
    // Load the audio
    try {
        audioPlayer.load(); // Ensure audio is loaded
        await audioPlayer.play();
        console.log('[AUDIO] Started playing successfully');
    } catch (err) {
        console.error('[AUDIO] Play failed:', {
            name: err.name,
            message: err.message
        });
        
        // If autoplay blocked, try to unlock again
        if (err.name === 'NotAllowedError') {
            console.log('[AUDIO] Autoplay blocked - attempting unlock');
            audioUnlocked = false;
            await unlockAudio();
            
            // Retry play
            try {
                await audioPlayer.play();
                console.log('[AUDIO] Retry successful');
            } catch (retryErr) {
                console.error('[AUDIO] Retry failed:', retryErr);
                isPlaying = false;
            }
        } else {
            isPlaying = false;
        }
        
        if (!isPlaying && audioQueue.length > 0) {
            playNextAudio();
        }
    }
}

async function sendMessage(message) {
    if (!message.trim()) return;
    
    // Ensure audio is unlocked before sending
    if (!audioUnlocked) {
        await unlockAudio();
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