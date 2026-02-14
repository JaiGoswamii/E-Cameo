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

// Unlock audio on first user interaction
async function unlockAudio() {
    if (audioUnlocked) return;
    try {
        await audioPlayer.play();
        audioPlayer.pause();
        audioPlayer.currentTime = 0;
        audioUnlocked = true;
        console.log('[DEBUG] Audio unlocked');
    } catch (e) {
        console.log('[DEBUG] Audio unlock failed:', e);
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

async function playNextAudio() {
    console.log('[DEBUG] playNextAudio called, isPlaying:', isPlaying, 'queue length:', audioQueue.length);
    
    if (isPlaying || audioQueue.length === 0) return;
    
    isPlaying = true;
    const {audio, text} = audioQueue.shift();
    
    console.log('[DEBUG] Playing audio, text:', text.substring(0, 30), 'audio length:', audio.length);
    
    showTalkingAvatar();
    showSubtitles(text);
    
    // Set up event handlers BEFORE setting src
    audioPlayer.onended = () => {
        console.log('[DEBUG] Audio ended');
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
        console.error('[DEBUG] Audio playback error:', e);
        isPlaying = false;
        hideSubtitles();
        if (audioQueue.length > 0) {
            playNextAudio();
        } else {
            showStaticAvatar();
            setStatus('Error playing audio', true);
        }
    };
    
    audioPlayer.src = `data:audio/mp3;base64,${audio}`;
    
    try {
        await audioPlayer.play();
        console.log('[DEBUG] Audio started playing');
    } catch (err) {
        console.error('[DEBUG] Play error:', err);
        isPlaying = false;
        if (audioQueue.length > 0) {
            playNextAudio();
        }
    }
}

async function sendMessage(message) {
    if (!message.trim()) return;
    
    addUserMessage(message);
    setStatus('Thinking...', false);
    userInput.value = '';
    userInput.disabled = true;
    sendBtn.disabled = true;
    
    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({message})
        });
        
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = ''; // Buffer for incomplete data
        
        while (true) {
            const {done, value} = await reader.read();
            if (done) break;
            
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
                                // Queue audio for playback (subtitles + avatar animation)
                                console.log('[DEBUG] Received audio chunk, length:', data.audio.length);
                                audioQueue.push({audio: data.audio, text: data.text || ''});
                                console.log('[DEBUG] Audio queue length:', audioQueue.length);
                                playNextAudio();
                                break;
                            
                            case 'end':
                            case 'response_end':
                                typingIndicator.classList.remove('active');
                                currentAssistantMessage = null;
                                setStatus('Ready to chat', true);
                                userInput.disabled = false;
                                sendBtn.disabled = false;
                                userInput.focus();
                                break;
                            
                            case 'tool_call':
                                console.log('Tool:', data);
                                break;
                                
                            case 'error':
                                console.error('Error:', data.message);
                                typingIndicator.classList.remove('active');
                                setStatus('Error occurred', true);
                                userInput.disabled = false;
                                sendBtn.disabled = false;
                                break;
                        }
                        
                        currentData = '';
                    } catch (parseError) {
                        console.error('[DEBUG] JSON parse error:', parseError, 'Data:', currentData.slice(0, 100));
                        currentData = '';
                    }
                }
            }
        }
    } catch (error) {
        console.error('Fetch error:', error);
        setStatus('Connection error - retry', true);
        userInput.disabled = false;
        sendBtn.disabled = false;
        userInput.focus();
    }
}

sendBtn.addEventListener('click', () => {
    unlockAudio();
    sendMessage(userInput.value);
});
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        unlockAudio();
        sendMessage(userInput.value);
    }
});

// Initial status
setStatus('Ready to chat', true);