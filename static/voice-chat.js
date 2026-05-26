/**
 * Voice Chat System for Tour Kiosk
 * Uses Web Speech API with persistent microphone stream
 */

class VoiceChat {
  constructor() {
    this.recognition = null;
    this.synthesis = window.speechSynthesis;
    this.isListening = false;
    this.isSpeaking = false;
    this.currentLanguage = 'en';
    this.autoSpeak = true;
    this.currentAudio = null;
    this.speechTimeout = null;
    this.lastTranscript = '';
    this.hasFinalResult = false;
    this.silenceTimer = null;
    this.silenceTimeout = 3500; // 3.5s silence = auto-send
    this.customCallback = null;
    this.audioLevelCallback = null;
    this._userStopped = false;
    this._restarting = false;
    
    this.languageMap = {
      'en': 'en-US',
      'zh': 'zh-CN',
      'ja': 'ja-JP',
      'ko': 'ko-KR',
      'de': 'de-DE',
      'fr': 'fr-FR',
      'es': 'es-ES',
      'hi': 'hi-IN'
    };
    
    this.init();
  }
  
  init() {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      console.error('Speech recognition not supported');
      return;
    }
    
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    this.recognition = new SpeechRecognition();
    this.recognition.continuous = true;
    this.recognition.interimResults = true;
    this.recognition.maxAlternatives = 1;
    
    this.setupRecognitionHandlers();
    console.log('VoiceChat initialized');
  }
  
  setupRecognitionHandlers() {
    if (!this.recognition) return;
    
    this.recognition.onstart = () => {
      this._restarting = false;
      this.isListening = true;
      this.updateUI('listening');
      // Show hint that mic is active
      const hint = document.getElementById('ai-mic-hint');
      if (hint) { hint.textContent = 'Listening...'; hint.style.color = '#4ade80'; }
    };
    
    this.recognition.onend = () => {
      // If user stopped, clean up
      if (this._userStopped) {
        this._userStopped = false;
        if (this.lastTranscript && !this.hasFinalResult) {
          this.onSpeechResult(this.lastTranscript);
        }
        this.isListening = false;
        this.updateUI('idle');
        return;
      }
      
      // Send any unsent transcript
      if (this.lastTranscript && !this.hasFinalResult) {
        this.onSpeechResult(this.lastTranscript);
        this.lastTranscript = '';
        this.hasFinalResult = false;
      }
      
      // Restart immediately if we should still be listening
      if (this.isListening && !this._restarting) {
        this._restarting = true;
        setTimeout(() => {
          if (this._userStopped || !this.isListening) {
            this._restarting = false;
            return;
          }
          try {
            this.lastTranscript = '';
            this.hasFinalResult = false;
            this.recognition.start();
          } catch(e) {
            // If start fails, try once more after brief delay
            setTimeout(() => {
              if (this._userStopped || !this.isListening) return;
              try { this.recognition.start(); } catch(e2) {
                this.isListening = false;
                this._restarting = false;
                this.updateUI('idle');
              }
            }, 200);
          }
        }, 10); // Near-instant restart
      }
    };
    
    this.recognition.onresult = (event) => {
      const hint = document.getElementById('ai-mic-hint');
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const transcript = result[0].transcript;
        const isFinal = result.isFinal;
        
        this.lastTranscript = transcript;
        this.clearSilenceTimer();
        
        if (hint) { hint.textContent = 'Hearing you...'; hint.style.color = '#22d3ee'; }
        
        if (isFinal) {
          this.hasFinalResult = true;
          this.clearSilenceTimer();
          this.onSpeechResult(transcript);
          this.lastTranscript = '';
          this.hasFinalResult = false;
          if (hint) { hint.textContent = 'Sent! Keep talking...'; hint.style.color = '#4ade80'; }
        } else {
          this.showInterimText(transcript);
          this.startSilenceTimer();
        }
      }
    };
    
    this.recognition.onerror = (event) => {
      // Fatal - stop completely
      if (event.error === 'not-allowed') {
        this.showError("Please allow microphone access to use voice input.");
        this._userStopped = true;
        this.isListening = false;
        this.updateUI('idle');
        return;
      }
      if (event.error === 'audio-capture') {
        this.showError("Microphone not available.");
        this._userStopped = true;
        this.isListening = false;
        this.updateUI('idle');
        return;
      }
      // no-speech, network, aborted - let onend handle restart silently
    };
    
    this.recognition.onnomatch = () => {};
  }
  
  async startListening() {
    if (!this.recognition) {
      alert('Voice recognition is not available in your browser.');
      return;
    }
    
    if (this.isListening) {
      this.stopListening();
      return;
    }
    
    // Stop TTS to prevent feedback
    if (this.isSpeaking) {
      this.stopSpeaking();
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    
    this.recognition.lang = this.languageMap[this.currentLanguage] || 'en-US';
    this._userStopped = false;
    this._restarting = false;
    this.isListening = true;
    this.lastTranscript = '';
    this.hasFinalResult = false;
    
    try {
      this.recognition.start();
    } catch (error) {
      if (error.name === 'InvalidStateError') {
        try {
          this.recognition.stop();
          await new Promise(resolve => setTimeout(resolve, 50));
          this.recognition.start();
        } catch (e) {
          this.showError('Could not start microphone. Try again.');
          this.isListening = false;
        }
      } else {
        this.showError('Could not start microphone. Try again.');
        this.isListening = false;
      }
    }
  }
  
  
  stopListening() {
    this._userStopped = true;
    this.isListening = false;
    this._restarting = false;
    if (this.recognition) {
      try { this.recognition.stop(); } catch(e) {}
    }
    this.clearSilenceTimer();
    this.updateUI('idle');
  }
  
  startSilenceTimer() {
    this.clearSilenceTimer();
    this.silenceTimer = setTimeout(() => {
      if (this.isListening && this.lastTranscript && !this.hasFinalResult) {
        this.hasFinalResult = true;
        this.onSpeechResult(this.lastTranscript);
        this.lastTranscript = '';
        this.hasFinalResult = false;
      }
    }, this.silenceTimeout);
  }
  
  clearSilenceTimer() {
    if (this.silenceTimer) {
      clearTimeout(this.silenceTimer);
      this.silenceTimer = null;
    }
  }
  
  async speak(text) {
    const cleanText = text
      .replace(/\*\*/g, '')
      .replace(/[🎯🤖✨💬🏖️🏝️⭐]/g, '')
      .replace(/\[TOUR:.*?\]/g, '')
      .replace(/\[FILTER:.*?\]/g, '');
    
    const elevenLabsSuccess = await this.speakWithElevenLabs(cleanText);
    if (!elevenLabsSuccess) {
      this.speakWithBrowser(cleanText);
    }
  }
  
  async speakWithElevenLabs(text) {
    try {
      if (this.speechTimeout) clearTimeout(this.speechTimeout);
      this.isSpeaking = true;
      this.updateUI('speaking');
      
      const response = await fetch('/api/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, language: this.currentLanguage, gender: 'default' })
      });
      
      if (!response.ok) {
        this.isSpeaking = false;
        return false;
      }
      
      const audioBlob = await response.blob();
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio();
      audio.preload = 'auto';
      this.currentAudio = audio;
      
      await new Promise((resolve, reject) => {
        audio.oncanplaythrough = resolve;
        audio.onerror = reject;
        audio.src = audioUrl;
        audio.load();
        setTimeout(() => { if (audio.readyState >= 3) resolve(); }, 500);
      });
      
      audio.onplay = () => {
        const visualizer = document.getElementById('audio-visualizer');
        if (visualizer) visualizer.classList.add('active');
        this.speechTimeout = setTimeout(() => this.stopSpeaking(), 30000);
      };
      
      audio.onended = () => {
        if (this.speechTimeout) clearTimeout(this.speechTimeout);
        this.isSpeaking = false;
        this.updateUI('idle');
        const visualizer = document.getElementById('audio-visualizer');
        if (visualizer) visualizer.classList.remove('active');
        URL.revokeObjectURL(audioUrl);
        this.currentAudio = null;
      };
      
      audio.onerror = () => {
        if (this.speechTimeout) clearTimeout(this.speechTimeout);
        this.isSpeaking = false;
        this.updateUI('idle');
        const visualizer = document.getElementById('audio-visualizer');
        if (visualizer) visualizer.classList.remove('active');
        URL.revokeObjectURL(audioUrl);
        this.currentAudio = null;
      };
      
      await audio.play();
      this.currentAudio = audio;
      return true;
      
    } catch (error) {
      if (this.speechTimeout) clearTimeout(this.speechTimeout);
      this.isSpeaking = false;
      this.updateUI('idle');
      return false;
    }
  }
  
  speakWithBrowser(text) {
    if (!this.synthesis) return;
    if (this.speechTimeout) clearTimeout(this.speechTimeout);
    this.synthesis.cancel();
    
    const utterance = new SpeechSynthesisUtterance(text);
    const langCode = this.languageMap[this.currentLanguage] || 'en-US';
    utterance.lang = langCode;
    utterance.rate = 1.15;
    utterance.pitch = 1.0;
    utterance.volume = 1.0;
    
    const voices = this.synthesis.getVoices();
    const preferredVoice = voices.find(v => v.lang.startsWith(langCode.split('-')[0]));
    if (preferredVoice) utterance.voice = preferredVoice;
    
    utterance.onstart = () => {
      this.isSpeaking = true;
      this.updateUI('speaking');
      const visualizer = document.getElementById('audio-visualizer');
      if (visualizer) visualizer.classList.add('active');
      this.speechTimeout = setTimeout(() => this.stopSpeaking(), 30000);
    };
    
    utterance.onend = () => {
      if (this.speechTimeout) clearTimeout(this.speechTimeout);
      this.isSpeaking = false;
      this.updateUI('idle');
      const visualizer = document.getElementById('audio-visualizer');
      if (visualizer) visualizer.classList.remove('active');
    };
    
    utterance.onerror = () => {
      if (this.speechTimeout) clearTimeout(this.speechTimeout);
      this.isSpeaking = false;
      this.updateUI('idle');
      const visualizer = document.getElementById('audio-visualizer');
      if (visualizer) visualizer.classList.remove('active');
    };
    
    this.synthesis.speak(utterance);
  }
  
  stopSpeaking() {
    if (this.speechTimeout) { clearTimeout(this.speechTimeout); this.speechTimeout = null; }
    if (this.currentAudio) {
      try { this.currentAudio.pause(); this.currentAudio.currentTime = 0; } catch(e) {}
      this.currentAudio = null;
    }
    if (this.synthesis) {
      this.synthesis.cancel();
      setTimeout(() => { if (this.synthesis) this.synthesis.cancel(); }, 10);
    }
    const visualizer = document.getElementById('audio-visualizer');
    if (visualizer) visualizer.classList.remove('active');
    this.isSpeaking = false;
    this.updateUI('idle');
  }
  
  setLanguage(lang) { this.currentLanguage = lang; }
  setAutoSpeak(enabled) { this.autoSpeak = enabled; }
  
  setCustomCallback(callback) { this.customCallback = callback; }
  clearCustomCallback() { this.customCallback = null; }
  setAudioLevelCallback(callback) { this.audioLevelCallback = callback; }
  clearAudioLevelCallback() { this.audioLevelCallback = null; }
  
  stopAllMicStreams() { this.stopListening(); }
  
  onSpeechResult(transcript) {
    if (this.customCallback) {
      const cb = this.customCallback;
      this.customCallback = null;
      cb(transcript);
      return;
    }
  }
  
  showInterimText(text) {
    // Override in integration to show live text
  }
  
  showError(message) {
    console.error('Voice Error:', message);
    const micBtn = document.getElementById('ai-mic-btn');
    if (micBtn) {
      micBtn.classList.remove('recording');
      micBtn.classList.add('error');
      setTimeout(() => micBtn.classList.remove('error'), 3000);
    }
    const hint = document.querySelector('.ai-mic-hint');
    if (hint) {
      const original = hint.textContent;
      hint.textContent = message;
      hint.style.color = '#ff6b6b';
      setTimeout(() => { hint.textContent = original; hint.style.color = ''; }, 4000);
    }
  }
  
  updateUI(state) {
    // Override in integration
  }
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = VoiceChat;
}
