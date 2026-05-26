/**
 * Simple voice recognition with auto-stop after 2s silence.
 * Restarts recognition if browser kills it prematurely.
 */

class VoiceChat {
  constructor() {
    this.isListening = false;
    this.isSpeaking = false;
    this.currentLanguage = 'en';
    this.autoSpeak = true;
    this.currentAudio = null;
    this.speechTimeout = null;
    this.synthesis = window.speechSynthesis;
    this.customCallback = null;
    this.audioLevelCallback = null;
    this._rec = null;
    this._silenceTimer = null;
    this._lastSpeechTime = 0;
    this._transcript = '';
    this._shouldBeListening = false;
    this._restartCount = 0;
    
    this.languageMap = {
      'en': 'en-US', 'zh': 'zh-CN', 'ja': 'ja-JP', 'ko': 'ko-KR',
      'de': 'de-DE', 'fr': 'fr-FR', 'es': 'es-ES', 'hi': 'hi-IN'
    };
  }
  
  startListening() {
    if (this._shouldBeListening) { this.stopListening(); return; }
    if (this.isSpeaking) this.stopSpeaking();
    
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { this.showError('Voice not supported in this browser.'); return; }
    
    this._shouldBeListening = true;
    this.isListening = true;
    this._transcript = '';
    this._restartCount = 0;
    this._lastSpeechTime = Date.now();
    this.updateUI('listening');
    
    this._startRecognition();
    this._startSilenceTimer();
  }
  
  _startRecognition() {
    if (!this._shouldBeListening) return;
    
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;
    
    // Clean up old instance
    if (this._rec) {
      try { this._rec.abort(); } catch(e) {}
      this._rec = null;
    }
    
    const rec = new SR();
    rec.continuous = true;
    rec.interimResults = true;
    rec.maxAlternatives = 1;
    rec.lang = this.languageMap[this.currentLanguage] || 'en-US';
    this._rec = rec;
    
    rec.onresult = (event) => {
      this._lastSpeechTime = Date.now();
      this._restartCount = 0;
      
      let interim = '';
      let finalText = '';
      for (let i = 0; i < event.results.length; i++) {
        const t = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalText += t;
        } else {
          interim += t;
        }
      }
      
      if (finalText) this._transcript = finalText;
      this.showInterimText(this._transcript + interim);
    };
    
    rec.onerror = (event) => {
      console.log('[MIC] error:', event.error);
      if (event.error === 'not-allowed') {
        this.showError('Please allow microphone access.');
        this._shouldBeListening = false;
        this.isListening = false;
        this._clearSilenceTimer();
        this.updateUI('idle');
        return;
      }
      // For all other errors (no-speech, network, aborted), let onend handle restart
    };
    
    rec.onend = () => {
      console.log('[MIC] onend fired, shouldBeListening:', this._shouldBeListening);
      if (!this._shouldBeListening) return;
      
      // Browser killed recognition - restart it (up to 50 times)
      this._restartCount++;
      if (this._restartCount > 50) {
        console.log('[MIC] Too many restarts, giving up');
        this._finish();
        return;
      }
      
      // Small delay before restart to avoid hammering
      setTimeout(() => {
        if (this._shouldBeListening) {
          console.log('[MIC] Restarting recognition, attempt', this._restartCount);
          this._startRecognition();
        }
      }, 100);
    };
    
    try {
      rec.start();
      console.log('[MIC] Recognition started');
    } catch(e) {
      console.log('[MIC] start() threw:', e.message);
      // If start fails, retry once after a delay
      setTimeout(() => {
        if (this._shouldBeListening && this._restartCount < 5) {
          this._restartCount++;
          this._startRecognition();
        } else {
          this._finish();
        }
      }, 300);
    }
  }
  
  _startSilenceTimer() {
    this._clearSilenceTimer();
    this._silenceTimer = setInterval(() => {
      if (!this._shouldBeListening) { this._clearSilenceTimer(); return; }
      
      const elapsed = Date.now() - this._lastSpeechTime;
      // Only auto-stop after 2s of silence IF we have some transcript
      // If no transcript yet, wait longer (5s) before giving up
      const timeout = this._transcript.trim() ? 2000 : 5000;
      
      if (elapsed >= timeout) {
        console.log('[MIC] Silence timeout reached (' + timeout + 'ms)');
        this._finish();
      }
    }, 300);
  }
  
  _clearSilenceTimer() {
    if (this._silenceTimer) { clearInterval(this._silenceTimer); this._silenceTimer = null; }
  }
  
  _finish() {
    this._clearSilenceTimer();
    this._shouldBeListening = false;
    this.isListening = false;
    if (this._rec) { try { this._rec.abort(); } catch(e) {} this._rec = null; }
    this.updateUI('idle');
    
    if (this._transcript.trim()) {
      this.onSpeechResult(this._transcript.trim());
    }
    this._transcript = '';
  }
  
  stopListening() {
    console.log('[MIC] stopListening called');
    this._clearSilenceTimer();
    this._shouldBeListening = false;
    this.isListening = false;
    if (this._rec) { try { this._rec.abort(); } catch(e) {} this._rec = null; }
    this.updateUI('idle');
    this._transcript = '';
  }
  
  // TTS methods
  async speak(text) {
    const clean = text.replace(/\*\*/g, '').replace(/[🎯🤖✨💬🏖️🏝️⭐]/g, '')
      .replace(/\[TOUR:.*?\]/g, '').replace(/\[FILTER:.*?\]/g, '');
    if (!(await this.speakWithElevenLabs(clean))) this.speakWithBrowser(clean);
  }
  
  async speakWithElevenLabs(text) {
    try {
      if (this.speechTimeout) clearTimeout(this.speechTimeout);
      this.isSpeaking = true; this.updateUI('speaking');
      const resp = await fetch('/api/tts', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({text, language: this.currentLanguage, gender:'default'})
      });
      if (!resp.ok) { this.isSpeaking = false; return false; }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio();
      this.currentAudio = audio;
      await new Promise((res,rej) => {
        audio.oncanplaythrough = res; audio.onerror = rej;
        audio.src = url; audio.load();
        setTimeout(() => { if (audio.readyState >= 3) res(); }, 500);
      });
      audio.onplay = () => { this.speechTimeout = setTimeout(() => this.stopSpeaking(), 30000); };
      audio.onended = () => { this._cleanupAudio(url); };
      audio.onerror = () => { this._cleanupAudio(url); };
      await audio.play();
      return true;
    } catch(e) {
      if (this.speechTimeout) clearTimeout(this.speechTimeout);
      this.isSpeaking = false; this.updateUI('idle'); return false;
    }
  }
  
  _cleanupAudio(url) {
    if (this.speechTimeout) clearTimeout(this.speechTimeout);
    this.isSpeaking = false; this.updateUI('idle');
    if (url) URL.revokeObjectURL(url);
    this.currentAudio = null;
  }
  
  speakWithBrowser(text) {
    if (!this.synthesis) return;
    this.synthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = this.languageMap[this.currentLanguage] || 'en-US';
    u.rate = 1.15;
    u.onstart = () => { this.isSpeaking = true; this.updateUI('speaking'); };
    u.onend = () => { this.isSpeaking = false; this.updateUI('idle'); };
    u.onerror = () => { this.isSpeaking = false; this.updateUI('idle'); };
    this.synthesis.speak(u);
  }
  
  stopSpeaking() {
    if (this.speechTimeout) { clearTimeout(this.speechTimeout); this.speechTimeout = null; }
    if (this.currentAudio) { try { this.currentAudio.pause(); } catch(e) {} this.currentAudio = null; }
    if (this.synthesis) this.synthesis.cancel();
    this.isSpeaking = false; this.updateUI('idle');
  }
  
  setLanguage(lang) { this.currentLanguage = lang; }
  setAutoSpeak(v) { this.autoSpeak = v; }
  setCustomCallback(cb) { this.customCallback = cb; }
  clearCustomCallback() { this.customCallback = null; }
  setAudioLevelCallback(cb) { this.audioLevelCallback = cb; }
  clearAudioLevelCallback() { this.audioLevelCallback = null; }
  stopAllMicStreams() { this.stopListening(); }
  
  onSpeechResult(transcript) {
    if (this.customCallback) { const cb = this.customCallback; this.customCallback = null; cb(transcript); }
  }
  showInterimText(text) {}
  showError(msg) {
    const hint = document.getElementById('ai-mic-hint');
    if (hint) { const orig = hint.textContent; hint.textContent = msg; hint.style.color = '#ff6b6b';
      setTimeout(() => { hint.textContent = orig; hint.style.color = ''; }, 3000); }
  }
  updateUI(state) {}
}

if (typeof module !== 'undefined' && module.exports) module.exports = VoiceChat;
