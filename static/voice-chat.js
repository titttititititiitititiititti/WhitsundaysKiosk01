/**
 * Voice Chat - Proven pattern from production voice assistants.
 * Creates a FRESH SpeechRecognition instance on each restart to avoid
 * Chrome's stale WebSocket freeze issue.
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
    this.silenceTimeout = 3500;
    this.customCallback = null;
    this.audioLevelCallback = null;
    this._shouldRun = false;
    this._restartTimer = null;
    
    this.languageMap = {
      'en': 'en-US', 'zh': 'zh-CN', 'ja': 'ja-JP', 'ko': 'ko-KR',
      'de': 'de-DE', 'fr': 'fr-FR', 'es': 'es-ES', 'hi': 'hi-IN'
    };
    
    // Check support
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      console.error('Speech recognition not supported');
      return;
    }
    console.log('VoiceChat ready');
  }
  
  /**
   * Create a fresh recognition instance and start it.
   * This is the core pattern - never reuse a stale instance.
   */
  _spawn() {
    // Clean up old instance
    if (this.recognition) {
      try { this.recognition.onend = null; this.recognition.onresult = null; this.recognition.onerror = null; }
      catch(e) {}
      this.recognition = null;
    }
    
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const rec = new SpeechRecognition();
    rec.continuous = true;
    rec.interimResults = true;
    rec.maxAlternatives = 1;
    rec.lang = this.languageMap[this.currentLanguage] || 'en-US';
    
    rec.onstart = () => {
      this.isListening = true;
      this.updateUI('listening');
      const hint = document.getElementById('ai-mic-hint');
      if (hint) { hint.textContent = 'Listening...'; hint.style.color = '#4ade80'; }
    };
    
    rec.onresult = (event) => {
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
    
    rec.onerror = (event) => {
      if (event.error === 'not-allowed') {
        this.showError("Please allow microphone access.");
        this._shouldRun = false;
        this.isListening = false;
        this.updateUI('idle');
        return;
      }
      if (event.error === 'audio-capture') {
        this.showError("Microphone not available.");
        this._shouldRun = false;
        this.isListening = false;
        this.updateUI('idle');
        return;
      }
      // no-speech, aborted, network - let onend handle restart
    };
    
    rec.onend = () => {
      if (!this._shouldRun) {
        // User stopped - send any unsent transcript
        if (this.lastTranscript && !this.hasFinalResult) {
          this.onSpeechResult(this.lastTranscript);
          this.lastTranscript = '';
        }
        this.isListening = false;
        this.updateUI('idle');
        return;
      }
      
      // Send unsent transcript before restart
      if (this.lastTranscript && !this.hasFinalResult) {
        this.onSpeechResult(this.lastTranscript);
        this.lastTranscript = '';
        this.hasFinalResult = false;
      }
      
      // Chrome killed the session - spawn a fresh instance after 250ms
      // (250ms is the empirically proven minimum for slower devices)
      this._restartTimer = setTimeout(() => {
        if (this._shouldRun) this._spawn();
      }, 250);
    };
    
    try {
      rec.start();
      this.recognition = rec;
    } catch (err) {
      // start() can throw if called too soon - retry with more delay
      this._restartTimer = setTimeout(() => {
        if (this._shouldRun) this._spawn();
      }, 500);
    }
  }
  
  startListening() {
    if (this._shouldRun) {
      this.stopListening();
      return;
    }
    
    // Stop TTS to prevent feedback
    if (this.isSpeaking) {
      this.stopSpeaking();
    }
    
    this._shouldRun = true;
    this.lastTranscript = '';
    this.hasFinalResult = false;
    this._spawn();
  }
  
  stopListening() {
    this._shouldRun = false;
    if (this._restartTimer) { clearTimeout(this._restartTimer); this._restartTimer = null; }
    if (this.recognition) {
      try { this.recognition.stop(); } catch(e) {}
    }
    this.clearSilenceTimer();
    this.isListening = false;
    this.updateUI('idle');
    const hint = document.getElementById('ai-mic-hint');
    if (hint) { hint.textContent = 'Tap to speak'; hint.style.color = ''; }
  }
  
  startSilenceTimer() {
    this.clearSilenceTimer();
    this.silenceTimer = setTimeout(() => {
      if (this._shouldRun && this.lastTranscript && !this.hasFinalResult) {
        this.hasFinalResult = true;
        this.onSpeechResult(this.lastTranscript);
        this.lastTranscript = '';
        this.hasFinalResult = false;
      }
    }, this.silenceTimeout);
  }
  
  clearSilenceTimer() {
    if (this.silenceTimer) { clearTimeout(this.silenceTimer); this.silenceTimer = null; }
  }
  
  async speak(text) {
    const cleanText = text.replace(/\*\*/g, '').replace(/[🎯🤖✨💬🏖️🏝️⭐]/g, '')
      .replace(/\[TOUR:.*?\]/g, '').replace(/\[FILTER:.*?\]/g, '');
    if (!(await this.speakWithElevenLabs(cleanText))) {
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
      if (!response.ok) { this.isSpeaking = false; return false; }
      
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
        const v = document.getElementById('audio-visualizer');
        if (v) v.classList.add('active');
        this.speechTimeout = setTimeout(() => this.stopSpeaking(), 30000);
      };
      audio.onended = () => {
        if (this.speechTimeout) clearTimeout(this.speechTimeout);
        this.isSpeaking = false; this.updateUI('idle');
        const v = document.getElementById('audio-visualizer');
        if (v) v.classList.remove('active');
        URL.revokeObjectURL(audioUrl); this.currentAudio = null;
      };
      audio.onerror = () => {
        if (this.speechTimeout) clearTimeout(this.speechTimeout);
        this.isSpeaking = false; this.updateUI('idle');
        const v = document.getElementById('audio-visualizer');
        if (v) v.classList.remove('active');
        URL.revokeObjectURL(audioUrl); this.currentAudio = null;
      };
      
      await audio.play();
      return true;
    } catch (e) {
      if (this.speechTimeout) clearTimeout(this.speechTimeout);
      this.isSpeaking = false; this.updateUI('idle');
      return false;
    }
  }
  
  speakWithBrowser(text) {
    if (!this.synthesis) return;
    if (this.speechTimeout) clearTimeout(this.speechTimeout);
    this.synthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = this.languageMap[this.currentLanguage] || 'en-US';
    utterance.rate = 1.15; utterance.pitch = 1.0; utterance.volume = 1.0;
    const voices = this.synthesis.getVoices();
    const v = voices.find(v => v.lang.startsWith(this.currentLanguage));
    if (v) utterance.voice = v;
    utterance.onstart = () => {
      this.isSpeaking = true; this.updateUI('speaking');
      const vis = document.getElementById('audio-visualizer');
      if (vis) vis.classList.add('active');
      this.speechTimeout = setTimeout(() => this.stopSpeaking(), 30000);
    };
    utterance.onend = () => {
      if (this.speechTimeout) clearTimeout(this.speechTimeout);
      this.isSpeaking = false; this.updateUI('idle');
      const vis = document.getElementById('audio-visualizer');
      if (vis) vis.classList.remove('active');
    };
    utterance.onerror = () => {
      if (this.speechTimeout) clearTimeout(this.speechTimeout);
      this.isSpeaking = false; this.updateUI('idle');
    };
    this.synthesis.speak(utterance);
  }
  
  stopSpeaking() {
    if (this.speechTimeout) { clearTimeout(this.speechTimeout); this.speechTimeout = null; }
    if (this.currentAudio) {
      try { this.currentAudio.pause(); this.currentAudio.currentTime = 0; } catch(e) {}
      this.currentAudio = null;
    }
    if (this.synthesis) { this.synthesis.cancel(); }
    const vis = document.getElementById('audio-visualizer');
    if (vis) vis.classList.remove('active');
    this.isSpeaking = false; this.updateUI('idle');
  }
  
  setLanguage(lang) { this.currentLanguage = lang; }
  setAutoSpeak(enabled) { this.autoSpeak = enabled; }
  setCustomCallback(cb) { this.customCallback = cb; }
  clearCustomCallback() { this.customCallback = null; }
  setAudioLevelCallback(cb) { this.audioLevelCallback = cb; }
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
  
  showInterimText(text) {}
  
  showError(message) {
    const micBtn = document.getElementById('ai-mic-btn');
    if (micBtn) { micBtn.classList.remove('recording'); micBtn.classList.add('error');
      setTimeout(() => micBtn.classList.remove('error'), 3000); }
    const hint = document.getElementById('ai-mic-hint');
    if (hint) { const orig = hint.textContent; hint.textContent = message; hint.style.color = '#ff6b6b';
      setTimeout(() => { hint.textContent = orig; hint.style.color = ''; }, 4000); }
  }
  
  updateUI(state) {}
}

if (typeof module !== 'undefined' && module.exports) { module.exports = VoiceChat; }
