# 🎤 Voice Chat Integration Guide

## Overview
Add speech-to-text and text-to-speech capabilities to your AI assistant so customers can speak naturally with the tour bot.

---

## Features

### Speech-to-Text (STT)
- ✅ Customer speaks → Converts to text automatically
- ✅ Real-time transcription display
- ✅ Auto-stops when customer finishes speaking
- ✅ Multi-language support (all 7 kiosk languages)

### Text-to-Speech (TTS)
- ✅ AI responses spoken aloud automatically
- ✅ Natural voice for each language
- ✅ Adjustable speed and volume
- ✅ Can be toggled on/off

### UI Features
- ✅ Microphone button with visual feedback
- ✅ Listening indicator (animated)
- ✅ Speaking indicator
- ✅ Interim transcription display
- ✅ Error handling with friendly messages

---

## Quick Integration

### Step 1: Add Voice Chat Script

Add this to your `templates/index.html` before the closing `</body>` tag:

```html
<!-- Voice Chat System -->
<script src="{{ url_for('static', filename='voice-chat.js') }}"></script>
```

### Step 2: Add Voice UI Controls

Add this HTML inside your chat container (after the messages container):

```html
<!-- Voice Controls -->
<div class="voice-controls">
  <button id="micButton" class="mic-button" title="Click to speak">
    <svg class="mic-icon" viewBox="0 0 24 24" width="24" height="24">
      <path fill="currentColor" d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
      <path fill="currentColor" d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
    </svg>
    <span class="mic-text">Tap to Speak</span>
  </button>
  
  <div class="voice-status" id="voiceStatus" style="display: none;">
    <div class="voice-indicator">
      <div class="pulse"></div>
    </div>
    <span class="status-text">Listening...</span>
  </div>
  
  <div class="interim-text" id="interimText" style="display: none;"></div>
  
  <label class="auto-speak-toggle">
    <input type="checkbox" id="autoSpeakToggle" checked>
    <span>Speak responses aloud</span>
  </label>
</div>
```

### Step 3: Add CSS Styling

Add this CSS to your `<style>` section:

```css
/* Voice Controls */
.voice-controls {
  padding: 15px;
  border-top: 1px solid #e0e0e0;
  background: #f8f9fa;
}

.mic-button {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 25px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  width: 100%;
  justify-content: center;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
}

.mic-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
}

.mic-button:active {
  transform: translateY(0);
}

.mic-button.listening {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  animation: pulse-button 1.5s ease-in-out infinite;
}

@keyframes pulse-button {
  0%, 100% { box-shadow: 0 4px 15px rgba(245, 87, 108, 0.3); }
  50% { box-shadow: 0 4px 25px rgba(245, 87, 108, 0.6); }
}

.mic-button.speaking {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
}

.mic-icon {
  width: 24px;
  height: 24px;
}

.voice-status {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 10px;
  padding: 10px;
  background: white;
  border-radius: 10px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.voice-indicator {
  position: relative;
  width: 20px;
  height: 20px;
}

.pulse {
  position: absolute;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: #f5576c;
  animation: pulse-ring 1.5s ease-out infinite;
}

@keyframes pulse-ring {
  0% {
    transform: scale(0.8);
    opacity: 1;
  }
  100% {
    transform: scale(2);
    opacity: 0;
  }
}

.status-text {
  font-weight: 600;
  color: #f5576c;
}

.interim-text {
  margin-top: 10px;
  padding: 10px;
  background: #fff3cd;
  border-left: 4px solid #ffc107;
  border-radius: 5px;
  color: #856404;
  font-style: italic;
}

.auto-speak-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  cursor: pointer;
  font-size: 14px;
  color: #666;
}

.auto-speak-toggle input[type="checkbox"] {
  width: 18px;
  height: 18px;
  cursor: pointer;
}
```

### Step 4: Initialize Voice Chat

Add this JavaScript at the end of your chat initialization code:

```javascript
// Initialize Voice Chat
let voiceChat = null;

function initVoiceChat() {
  voiceChat = new VoiceChat();
  
  // Set current language
  voiceChat.setLanguage(currentLanguage);
  
  // Handle speech results
  voiceChat.onSpeechResult = (transcript) => {
    console.log('Voice input:', transcript);
    
    // Hide interim text
    document.getElementById('interimText').style.display = 'none';
    
    // Send to chat
    if (transcript.trim()) {
      sendChatMessage(transcript);
    }
  };
  
  // Show interim results
  voiceChat.showInterimText = (text) => {
    const interimEl = document.getElementById('interimText');
    interimEl.textContent = text;
    interimEl.style.display = 'block';
  };
  
  // Update UI based on state
  voiceChat.updateUI = (state) => {
    const micBtn = document.getElementById('micButton');
    const voiceStatus = document.getElementById('voiceStatus');
    const statusText = voiceStatus.querySelector('.status-text');
    
    // Remove all state classes
    micBtn.classList.remove('listening', 'speaking');
    
    switch(state) {
      case 'listening':
        micBtn.classList.add('listening');
        micBtn.querySelector('.mic-text').textContent = 'Listening...';
        voiceStatus.style.display = 'flex';
        statusText.textContent = 'Listening...';
        break;
        
      case 'speaking':
        micBtn.classList.add('speaking');
        micBtn.querySelector('.mic-text').textContent = 'Speaking...';
        voiceStatus.style.display = 'flex';
        statusText.textContent = 'Speaking...';
        statusText.style.color = '#00f2fe';
        break;
        
      case 'idle':
      default:
        micBtn.querySelector('.mic-text').textContent = 'Tap to Speak';
        voiceStatus.style.display = 'none';
        document.getElementById('interimText').style.display = 'none';
        break;
    }
  };
  
  // Show errors
  voiceChat.showError = (message) => {
    addChatMessage(message, 'assistant');
  };
  
  // Wire up mic button
  document.getElementById('micButton').addEventListener('click', () => {
    voiceChat.startListening();
  });
  
  // Wire up auto-speak toggle
  document.getElementById('autoSpeakToggle').addEventListener('change', (e) => {
    voiceChat.setAutoSpeak(e.target.checked);
  });
  
  console.log('✅ Voice chat initialized');
}

// Call this after chat is ready
initVoiceChat();

// Update voice language when UI language changes
function onLanguageChange(newLang) {
  currentLanguage = newLang;
  if (voiceChat) {
    voiceChat.setLanguage(newLang);
  }
  // ... rest of your language change code
}

// Speak AI responses automatically
function addChatMessage(message, role) {
  // ... your existing code to add message to UI ...
  
  // If it's an AI message and auto-speak is enabled
  if (role === 'assistant' && voiceChat && voiceChat.autoSpeak) {
    // Wait a bit for UI to update, then speak
    setTimeout(() => {
      voiceChat.speak(message);
    }, 300);
  }
}
```

---

## Usage Instructions for Customers

### Speaking to the Bot:
1. Click the "Tap to Speak" button
2. Speak your question naturally
3. The bot will transcribe and respond
4. Response will be spoken aloud (if enabled)

### Example Interactions:
- "I want to go to Whitehaven Beach"
- "Show me full day tours under $200"
- "What diving tours do you have?"
- "I'm traveling with kids, what do you recommend?"

---

## Language Support

Voice recognition works in all 7 kiosk languages:

| Language | Recognition | Voice |
|----------|-------------|-------|
| English | ✅ en-US | ✅ Native |
| Chinese | ✅ zh-CN | ✅ Native |
| Japanese | ✅ ja-JP | ✅ Native |
| Korean | ✅ ko-KR | ✅ Native |
| German | ✅ de-DE | ✅ Native |
| French | ✅ fr-FR | ✅ Native |
| Spanish | ✅ es-ES | ✅ Native |
| Hindi | ✅ hi-IN | ✅ Native |

The voice automatically switches when customer changes language!

---

## Troubleshooting

### "Microphone not available"
- Check browser permissions
- Click the microphone icon in address bar
- Allow microphone access

### "Voice recognition not working"
- Use Chrome, Edge, or Safari (required for Web Speech API)
- Check internet connection (required for recognition)
- Try reloading the page

### "No voice output"
- Check device volume
- Verify speakers are working
- Toggle "Speak responses aloud" checkbox

### Multiple voices speaking
- This happens if customer clicks mic while AI is speaking
- Solution: Automatically stops current speech when mic is activated (already implemented)

---

## Advanced Configuration

### Adjust Speech Speed
```javascript
// In voice-chat.js, modify the speak() method:
utterance.rate = 1.0; // 0.5 = slow, 1.0 = normal, 2.0 = fast
```

### Change Voice Gender/Style
```javascript
// Select specific voice by name
const voices = this.synthesis.getVoices();
const preferredVoice = voices.find(v => v.name.includes('Female'));
if (preferredVoice) utterance.voice = preferredVoice;
```

### Disable Auto-Speak by Default
```javascript
// In VoiceChat constructor:
this.autoSpeak = false; // Changed from true
```

---

## Benefits

### For Customers:
- ✅ Hands-free interaction
- ✅ Natural conversation
- ✅ No typing needed
- ✅ Great for accessibility
- ✅ Works in their native language

### For Your Kiosk:
- ✅ More engaging experience
- ✅ Faster interactions
- ✅ Accessible to all customers
- ✅ Modern, professional feel
- ✅ No additional API costs (uses browser)

---

## Testing Checklist

- [ ] Mic button appears and works
- [ ] Voice recognition starts on click
- [ ] Interim transcription shows while speaking
- [ ] Final transcript sent to chat
- [ ] AI response appears in chat
- [ ] AI response spoken aloud (if enabled)
- [ ] Language switching updates voice
- [ ] Stop button cancels listening
- [ ] Auto-speak toggle works
- [ ] Error messages display properly

---

## Next Steps

1. **Test in your browser** - Try speaking to the bot!
2. **Adjust timing** - Tweak delays if needed
3. **Customize voices** - Select preferred voices for each language
4. **Add visual polish** - Enhance animations if desired
5. **Test on kiosk hardware** - Ensure microphone works

Your AI assistant can now have natural voice conversations with customers! 🎤✨



















