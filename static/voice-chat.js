/**
 * Simple voice recognition - stays on until manually stopped.
 * Tap mic to start, tap again to stop and accept text.
 * No auto-off, no silence timers.
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
    this.updateUI('listening');
    
    this._startRecognition();
  }
  
  _startRecognition() {
    if (!this._shouldBeListening) return;
    
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;
    
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
      if (event.error === 'not-allowed') {
        this.showError('Please allow microphone access.');
        this._shouldBeListening = false;
        this.isListening = false;
        this.updateUI('idle');
        return;
      }
      // All other errors - let onend handle restart
    };
    
    rec.onend = () => {
      if (!this._shouldBeListening) return;
      
      // Browser killed it - restart
      this._restartCount++;
      if (this._restartCount > 100) {
        this._shouldBeListening = false;
        this.isListening = false;
        this.updateUI('idle');
        return;
      }
      
      setTimeout(() => {
        if (this._shouldBeListening) {
          this._startRecognition();
        }
      }, 50);
    };
    
    try {
      rec.start();
    } catch(e) {
      setTimeout(() => {
        if (this._shouldBeListening && this._restartCount < 10) {
          this._restartCount++;
          this._startRecognition();
        }
      }, 200);
    }
  }
  
  stopListening() {
    this._shouldBeListening = false;
    this.isListening = false;
    if (this._rec) { try { this._rec.abort(); } catch(e) {} this._rec = null; }
    this.updateUI('idle');
    
    // Return the transcript we captured
    const text = this._transcript.trim();
    this._transcript = '';
    if (text) {
      this.onSpeechResult(text);
    }
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
