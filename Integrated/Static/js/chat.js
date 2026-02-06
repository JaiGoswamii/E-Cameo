const socket = io();

// DOM elements
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const statusText = document.getElementById('status-text');
const statusDot = document.getElementById('status-dot');
const avatarStatic = document.getElementById('avatar-static');
const avatarTalking = document.getElementById('avatar-talking');
const subtitles = document.getElementById('subtitles');
const subtitleText = document.getElementById('subtitle-text');
const audioPlayer = document.getElementById('audio-player');

// State
let audioQueue = [];
let textQueue = [];
let isPlaying = false;

// Initialize
socket.on('connect', () => {
    updateStatus('Ready', false);
});

socket.on('disconnect', () => {
    updateStatus('Offline', false);
});

sendBtn.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

function updateStatus(text, isSpeaking) {
    statusText.textContent = text;
    statusDot.classList.toggle('speaking', isSpeaking);
}

function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;
    
    userInput.value = '';
    setInputState(false);
    
    audioQueue = [];
    textQueue = [];
    hideSubtitles();
    updateStatus('Processing...', false);
    
    socket.emit('send_message', { message });
}

function setInputState(enabled) {
    userInput.disabled = !enabled;
    sendBtn.disabled = !enabled;
    if (enabled) userInput.focus();
}

function startTalking() {
    avatarStatic.classList.remove('active');
    avatarTalking.classList.add('active');
    // Use video instead of GIF
    if (avatarTalking.tagName === 'VIDEO') {
        avatarTalking.play();
    }
    updateStatus('Speaking', true);
}

function stopTalking() {
    avatarTalking.classList.remove('active');
    if (avatarTalking.tagName === 'VIDEO') {
        avatarTalking.pause();
        avatarTalking.currentTime = 0;
    }
    avatarStatic.classList.add('active');
    updateStatus('Ready', false);
}

function showSubtitles(text) {
    subtitleText.textContent = text;
    subtitles.classList.add('visible');
}

function hideSubtitles() {
    subtitles.classList.remove('visible');
    setTimeout(() => subtitleText.textContent = '', 300);
}

function playNextAudio() {
    if (audioQueue.length === 0) {
        isPlaying = false;
        stopTalking();
        hideSubtitles();
        setInputState(true);
        return;
    }
    
    isPlaying = true;
    const audioData = audioQueue.shift();
    const text = textQueue.shift();
    
    const audioBlob = base64ToBlob(audioData, 'audio/mpeg');
    const audioUrl = URL.createObjectURL(audioBlob);
    
    audioPlayer.src = audioUrl;
    startTalking();
    
    audioPlayer.oncanplaythrough = () => {
        audioPlayer.play().then(() => {
            showSubtitles(text);
        }).catch(e => {
            console.error('Playback error:', e);
            URL.revokeObjectURL(audioUrl);
            playNextAudio();
        });
    };
    
    audioPlayer.onended = () => {
        URL.revokeObjectURL(audioUrl);
        setTimeout(playNextAudio, 200);
    };
}

function base64ToBlob(base64, mimeType) {
    const byteCharacters = atob(base64);
    const byteArray = new Uint8Array(byteCharacters.length);
    for (let i = 0; i < byteCharacters.length; i++) {
        byteArray[i] = byteCharacters.charCodeAt(i);
    }
    return new Blob([byteArray], { type: mimeType });
}

// Socket events
socket.on('response_start', () => {
    audioQueue = [];
    textQueue = [];
});

socket.on('audio_chunk', (data) => {
    audioQueue.push(data.audio);
    textQueue.push(data.text);
    if (!isPlaying) playNextAudio();
});

socket.on('response_end', () => {
    if (audioQueue.length === 0 && !isPlaying) {
        setInputState(true);
        stopTalking();
    }
});

socket.on('error', (data) => {
    showSubtitles(`⚠️ ${data.message}`);
    setTimeout(() => {
        hideSubtitles();
        setInputState(true);
        stopTalking();
    }, 3000);
});

window.addEventListener('load', () => userInput.focus());