const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const avatarStatic = document.getElementById('avatar-static');
const avatarTalking = document.getElementById('avatar-talking');
const subtitleText = document.getElementById('subtitle-text');
const audioPlayer = document.getElementById('audio-player');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');

let audioQueue = [];
let isPlaying = false;

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

async function playNextAudio() {
    if (isPlaying || audioQueue.length === 0) return;
    
    isPlaying = true;
    const {audio, text} = audioQueue.shift();
    
    showTalkingAvatar();
    subtitleText.textContent = text;
    
    audioPlayer.src = `data:audio/mp3;base64,${audio}`;
    audioPlayer.play();
    
    audioPlayer.onended = () => {
        isPlaying = false;
        if (audioQueue.length > 0) {
            playNextAudio();
        } else {
            showStaticAvatar();
            subtitleText.textContent = '';
            setStatus('Ready to chat', true);
        }
    };
}

async function sendMessage(message) {
    if (!message.trim()) return;
    
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
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        while (true) {
            const {done, value} = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = JSON.parse(line.slice(6));
                    
                    switch(data.type) {
                        case 'response_start':
                            setStatus('Responding...', false);
                            break;
                        
                        case 'text_chunk':
                            // Optional: display text in real-time
                            break;
                        
                        case 'audio_chunk':
                            audioQueue.push({audio: data.audio, text: data.text});
                            playNextAudio();
                            break;
                        
                        case 'response_end':
                            userInput.disabled = false;
                            sendBtn.disabled = false;
                            userInput.focus();
                            break;
                        
                        case 'tool_call':
                            console.log('Tool called:', data.tool, data.data);
                            break;
                        
                        case 'error':
                            console.error('Error:', data.message);
                            setStatus('Error occurred', true);
                            userInput.disabled = false;
                            sendBtn.disabled = false;
                            break;
                    }
                }
            }
        }
    } catch (error) {
        console.error('Fetch error:', error);
        setStatus('Connection error', true);
        userInput.disabled = false;
        sendBtn.disabled = false;
    }
}

sendBtn.addEventListener('click', () => sendMessage(userInput.value));
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage(userInput.value);
});

// Initial status
setStatus('Ready to chat', true);