/**
 * Voice input with auto-stop on silence.
 * Uses continuous mode, auto-stops after 2 seconds of no speech detected.
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
    this._lastResultTime = 0;
    
    this.languageMap = {
      'en': 'en-US', 'zh': 'zh-CN', 'ja': 'ja-JP', 'ko': 'ko-KR',
      'de': 'de-DE', 'fr': 'fr-FR', 'es': 'es-ES', 'hi': 'hi-IN'
    };
  }
  
  startListening() {
    if (this.isListening) { this.stopListening(); return; }
    if (this.isSpeaking) this.stopSpeaking();
    
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { this.showError('Voice not supported in this browser.'); return; }
    
    const rec = new SR();
    rec.continuous = true;
    rec.interimResults = true;
    rec.maxAlternatives = 1;
    rec.lang = this.languageMap[this.currentLanguage] || 'en-US';
    
    this._rec = rec;
    this.isListening = true;
    this._lastResultTime = Date.now();
    this.updateUI('listening');
    
    let finalTranscript = '';
    
    rec.onresult = (event) => {
      this._lastResultTime = Date.now();
      this._resetSilenceTimer();
      
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcript;
        } else {
          interim += transcript;
        }
      }
      
      if (finalTranscript) {
        this.showInterimText(finalTranscript + interim);
      } else if (interim) {
        this.showInterimText(interim);
      }
    };
    
    rec.onerror = (event) => {
      if (event.error === 'not-allowed') {
        this.showError('Please allow microphone access.');
      } else if (event.error === 'no-speech') {
        // Silence detected by browser - stop and return what we have
        this._finishListening(finalTranscript);
        return;
      }
      this._clearSilenceTimer();
      this.isListening = false;
      this.updateUI('idle');
    };
    
    rec.onend = () => {
      this._clearSilenceTimer();
      if (this.isListening) {
        // If we're still supposed to be listening, finish with what we have
        this._finishListening(finalTranscript);
      }
    };
    
    // Start the silence timer - auto-stop after 2s of no new results
    this._startSilenceTimer(finalTranscript);
    
    try {
      rec.start();
    } catch(e) {
      this.showError('Could not start mic. Try again.');
      this.isListening = false;
      this.updateUI('idle');
    }
  }
  
  _startSilenceTimer() {
    this._clearSilenceTimer();
    this._silenceTimer = setInterval(() => {
      if (!this.isListening) { this._clearSilenceTimer(); return; }
      const elapsed = Date.now() - this._lastResultTime;
      if (elapsed >= 2000) {
        this._clearSilenceTimer();
        this.stopListening();
      }
    }, 300);
  }
  
  _resetSilenceTimer() {
    this._lastResultTime = Date.now();
  }
  
  _clearSilenceTimer() {
    if (this._silenceTimer) { clearInterval(this._silenceTimer); this._silenceTimer = null; }
  }
  
  _finishListening(transcript) {
    this._clearSilenceTimer();
    this.isListening = false;
    this.updateUI('idle');
    if (this._rec) { try { this._rec.stop(); } catch(e) {} this._rec = null; }
    if (transcript && transcript.trim()) {
      this.onSpeechResult(transcript.trim());
    }
  }
  
  stopListening() {
    this._clearSilenceTimer();
    this.isListening = false;
    if (this._rec) { try { this._rec.stop(); } catch(e) {} this._rec = null; }
    this.updateUI('idle');
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
  
  // Utility
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
