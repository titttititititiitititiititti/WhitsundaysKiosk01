/**
 * Voice Chat System for Tour Kiosk
 * 
 * Features:
 * - Speech-to-Text: Customer speaks, converted to text
 * - Text-to-Speech: AI responses spoken aloud
 * - Visual feedback for listening/speaking states
 * - Auto-stop after customer finishes speaking
 * - Multilingual support (matches current language)
 */

class VoiceChat {
  constructor() {
    this.recognition = null;
    this.synthesis = window.speechSynthesis;
    this.isListening = false;
    this.isSpeaking = false;
    this.currentLanguage = 'en';
    this.autoSpeak = true; // Auto-speak AI responses
    this.currentAudio = null; // Track current audio element
    this.speechTimeout = null; // Track speech timeout
    this.audioMonitorStream = null; // For audio level monitoring
    this.audioMonitorContext = null; // AudioContext for monitoring
    this.lastTranscript = ''; // Track last transcript for fallback
    this.hasFinalResult = false; // Track if we got a final result
    this.silenceTimer = null; // Timer for auto-stop after silence
    this.silenceTimeout = 3000; // 3 seconds of silence = auto-send
    this.customCallback = null; // Custom callback for speech results (e.g., floating orb)
    this.audioLevelCallback = null; // Callback for real-time audio level updates
    
    // Language mapping for speech recognition
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
    console.log('🎤 Initializing VoiceChat...');
    
    // Check browser support
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      console.error('❌ Speech recognition not supported in this browser');
      return;
    }
    
    // Check if we're in a secure context (required for speech recognition)
    if (!window.isSecureContext) {
      console.warn('⚠️ Not in a secure context (HTTPS or localhost). Speech recognition may not work.');
    }
    
    // Initialize speech recognition
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    this.recognition = new SpeechRecognition();
    
    console.log('🎤 SpeechRecognition API:', SpeechRecognition.name || 'webkitSpeechRecognition');
    
    // Configure recognition — always continuous so mic stays alive
    this.recognition.continuous = true;
    this.recognition.interimResults = true;
    this.recognition.maxAlternatives = 1;
    console.log('🎤 Recognition configured: continuous=true for persistent listening');
    
    // Set up event handlers
    this.setupRecognitionHandlers();
    
    console.log('✅ Voice Chat initialized successfully');
    console.log('   - Continuous mode:', this.recognition.continuous);
    console.log('   - Interim results:', this.recognition.interimResults);
    console.log('   - Default language:', this.currentLanguage);
    console.log('   - Secure context:', window.isSecureContext);
  }
  
  setupRecognitionHandlers() {
    if (!this.recognition) return;
    
    // Track the last transcript in case we need to use it on end
    this.lastTranscript = '';
    this.hasFinalResult = false;
    
    // When speech recognition starts
    this.recognition.onstart = () => {
      console.log('🎤 Speech recognition STARTED');
      this.isListening = true;
      this.lastTranscript = '';
      this.hasFinalResult = false;
      this.clearSilenceTimer();
      this.updateUI('listening');
    };
    
    // When audio capture starts
    this.recognition.onaudiostart = () => {
      console.log('🎤 Audio capture started - microphone is active');
    };
    
    // When sound is detected
    this.recognition.onsoundstart = () => {
      console.log('🎤 Sound detected');
    };
    
    // When speech is detected
    this.recognition.onspeechstart = () => {
      console.log('🎤 Speech detected - user is talking');
    };
    
    // When speech ends
    this.recognition.onspeechend = () => {
      console.log('🎤 Speech ended - user stopped talking');
      // Start silence timer - if no more speech in 3 seconds, auto-send
      this.startSilenceTimer();
    };
    
    // When sound ends
    this.recognition.onsoundend = () => {
      console.log('🎤 Sound ended');
    };
    
    // When audio capture ends
    this.recognition.onaudioend = () => {
      console.log('🎤 Audio capture ended');
    };
    
    // When speech recognition ends
    this.recognition.onend = () => {
      console.log('🎤 Speech recognition ENDED, userStopped:', this._userStopped, 'hasFinal:', this.hasFinalResult);
      
      // If user intentionally stopped, just clean up - no restart
      if (this._userStopped) {
        this._userStopped = false;
        if (this.lastTranscript && !this.hasFinalResult) {
          this.onSpeechResult(this.lastTranscript);
        }
        this.isListening = false;
        this.updateUI('idle');
        return;
      }
      
      // If we have a transcript but never got a "final" result, send it
      if (this.lastTranscript && !this.hasFinalResult) {
        console.log('🎤 Using last transcript as fallback:', this.lastTranscript);
        this.onSpeechResult(this.lastTranscript);
      }
      
      // Always restart if we're supposed to be listening (continuous mode)
      if (this.isListening) {
        console.log('🎤 Recognition ended unexpectedly - restarting in 500ms...');
        setTimeout(() => {
          if (this._userStopped || !this.isListening) return;
          try {
            this.lastTranscript = '';
            this.hasFinalResult = false;
            this.recognition.start();
            console.log('🎤 Recognition restarted successfully');
          } catch(e) {
            console.log('🎤 Restart failed:', e.message);
            // Try again in 1 second
            setTimeout(() => {
              if (this._userStopped || !this.isListening) return;
              try { this.recognition.start(); } catch(e2) {
                console.log('🎤 Second restart failed, giving up');
                this.isListening = false;
                this.updateUI('idle');
              }
            }, 1000);
          }
        }, 500);
        return;
      }
      
      this.isListening = false;
      this.updateUI('idle');
    };
    
    // When we get speech results
    this.recognition.onresult = (event) => {
      console.log('🎤 Got result event:', event.results.length, 'results');
      
      // Process all results
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const transcript = result[0].transcript;
        const confidence = result[0].confidence;
        const isFinal = result.isFinal;
        
        console.log(`🗣️ ${isFinal ? 'FINAL' : 'Interim'}: "${transcript}" (confidence: ${(confidence * 100).toFixed(1)}%)`);
        
        // Always save the latest transcript
        this.lastTranscript = transcript;
        
        // Reset silence timer on new speech
        this.clearSilenceTimer();
        
        if (isFinal) {
          this.hasFinalResult = true;
          this.clearSilenceTimer();
          this.onSpeechResult(transcript);
          // Reset for next utterance (mic stays on in continuous mode)
          this.lastTranscript = '';
          this.hasFinalResult = false;
        } else {
          // Show interim results - start silence timer as fallback
          this.showInterimText(transcript);
          this.startSilenceTimer();
        }
      }
    };
    
    // No match found - don't show error, just log it (user can retry naturally)
    this.recognition.onnomatch = () => {
      console.log('🎤 No speech match - will retry silently');
    };
    
    // Error handling
    this.recognition.onerror = (event) => {
      console.error('🎤 Speech recognition ERROR:', event.error, event.message);
      
      // Fatal errors - stop completely
      if (event.error === 'not-allowed') {
        this.showError("Please allow microphone access to use voice input.");
        this._userStopped = true;
        this.isListening = false;
        this.updateUI('idle');
        return;
      }
      if (event.error === 'audio-capture') {
        this.showError("Microphone not available. Check that no other app is using it.");
        this._userStopped = true;
        this.isListening = false;
        this.updateUI('idle');
        return;
      }
      
      // Non-fatal errors (no-speech, network, aborted): onend will restart
      console.log('🎤 Non-fatal error, onend will handle restart');
    };
  }
  
  async startListening() {
    console.log('🎤 startListening() called');
    
    if (!this.recognition) {
      console.error('🎤 Recognition not available');
      alert('Voice recognition is not available in your browser.');
      return;
    }
    
    if (this.isListening) {
      console.log('🎤 Already listening - stopping...');
      this.stopListening();
      return;
    }
    
    // Stop any ongoing speech to prevent feedback
    if (this.isSpeaking) {
      console.log('🔇 Stopping TTS before starting mic');
      this.stopSpeaking();
      // Wait a moment for TTS to fully stop
      await new Promise(resolve => setTimeout(resolve, 200));
    }
    
    // Set language for recognition
    this.recognition.lang = this.languageMap[this.currentLanguage] || 'en-US';
    
    this._userStopped = false;
    this.isListening = true;
    console.log(`🎤 Starting speech recognition (continuous mode)...`);
    
    try {
      this.recognition.start();
      console.log('🎤 recognition.start() called');
    } catch (error) {
      if (error.name === 'InvalidStateError') {
        console.log('🎤 Recognition already running - stopping and restarting...');
        try {
          this.recognition.stop();
          await new Promise(resolve => setTimeout(resolve, 100));
          this.recognition.start();
          console.log('🎤 Recognition restarted');
        } catch (e) {
          console.error('🎤 Failed to restart:', e);
          this.showError('Could not start microphone. Try again.');
        }
      } else {
        console.error('🎤 Failed to start recognition:', error);
        this.showError('Could not start microphone. Try again.');
      }
    }
  }
  
  // Stop all mic-related streams
  stopAllMicStreams() {
    if (this.audioMonitorStream) {
      try { this.audioMonitorStream.getTracks().forEach(t => t.stop()); } catch(e) {}
      this.audioMonitorStream = null;
    }
    if (this.audioMonitorContext) {
      try { this.audioMonitorContext.close(); } catch(e) {}
      this.audioMonitorContext = null;
    }
  }
  
  stopListening() {
    console.log('🎤 stopListening() called - shutting down mic');
    this._userStopped = true;
    this.isListening = false;
    if (this.recognition) {
      try { this.recognition.stop(); } catch(e) {}
    }
    this.clearSilenceTimer();
    this.updateUI('idle');
  }
  
  startSilenceTimer() {
    this.clearSilenceTimer();
    
    // If 4 seconds pass with interim text but no final result, send what we have
    this.silenceTimer = setTimeout(() => {
      if (this.isListening && this.lastTranscript && !this.hasFinalResult) {
        console.log('⏱️ Silence timeout - sending interim transcript');
        this.hasFinalResult = true;
        this.onSpeechResult(this.lastTranscript);
        // Reset for next utterance (don't stop recognition)
        this.lastTranscript = '';
        this.hasFinalResult = false;
      }
    }, 4000);
  }
  
  clearSilenceTimer() {
    if (this.silenceTimer) {
      clearTimeout(this.silenceTimer);
      this.silenceTimer = null;
    }
  }
  
  async speak(text) {
    // Remove markdown-style formatting for cleaner speech
    const cleanText = text
      .replace(/\*\*/g, '') // Remove bold markers
      .replace(/[🎯🤖✨💬🏖️🏝️⭐]/g, '') // Remove emojis
      .replace(/\[TOUR:.*?\]/g, '') // Remove tour keys
      .replace(/\[FILTER:.*?\]/g, ''); // Remove filter commands
    
    // Try ElevenLabs first (premium quality)
    const elevenLabsSuccess = await this.speakWithElevenLabs(cleanText);
    
    if (!elevenLabsSuccess) {
      // Fallback to browser TTS
      this.speakWithBrowser(cleanText);
    }
  }
  
  async speakWithElevenLabs(text) {
    try {
      console.log('🎙️ Using ElevenLabs TTS...');
      
      // Clear any existing timeout
      if (this.speechTimeout) {
        clearTimeout(this.speechTimeout);
      }
      
      this.isSpeaking = true;
      this.updateUI('speaking');
      
      const response = await fetch('/api/tts', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          text: text,
          language: this.currentLanguage,
          gender: 'default'
        })
      });
      
      if (!response.ok) {
        console.warn('ElevenLabs request failed, falling back to browser TTS');
        this.isSpeaking = false;
        return false;
      }
      
      // Get audio data
      const audioBlob = await response.blob();
      const audioUrl = URL.createObjectURL(audioBlob);
      
      // Play audio - wait for it to be fully loaded before playing
      const audio = new Audio();
      audio.preload = 'auto';
      
      // Store reference immediately for stopping
      this.currentAudio = audio;
      
      // Wait for audio to be ready before playing
      await new Promise((resolve, reject) => {
        audio.oncanplaythrough = () => {
          console.log('🔊 ElevenLabs: Audio loaded, starting playback...');
          resolve();
        };
        
        audio.onerror = (error) => {
          console.error('ElevenLabs audio load error:', error);
          reject(error);
        };
        
        // Set src after attaching listeners
        audio.src = audioUrl;
        audio.load();
        
        // Fallback timeout in case canplaythrough doesn't fire
        setTimeout(() => {
          if (audio.readyState >= 3) {
            resolve();
          }
        }, 500);
      });
      
      audio.onplay = () => {
        console.log('🔊 ElevenLabs: Playing...');
        // Show audio visualizer
        const visualizer = document.getElementById('audio-visualizer');
        if (visualizer) {
          visualizer.classList.add('active');
        }
        
        // Set a safety timeout (30 seconds max)
        this.speechTimeout = setTimeout(() => {
          console.warn('⚠️ Speech timeout - forcing stop');
          this.stopSpeaking();
        }, 30000);
      };
      
      audio.onended = () => {
        console.log('🔊 ElevenLabs: Finished');
        if (this.speechTimeout) {
          clearTimeout(this.speechTimeout);
        }
        this.isSpeaking = false;
        this.updateUI('idle');
        // Hide audio visualizer
        const visualizer = document.getElementById('audio-visualizer');
        if (visualizer) {
          visualizer.classList.remove('active');
        }
        URL.revokeObjectURL(audioUrl); // Clean up
        this.currentAudio = null;
      };
      
      audio.onerror = (error) => {
        console.error('ElevenLabs audio playback error:', error);
        if (this.speechTimeout) {
          clearTimeout(this.speechTimeout);
        }
        this.isSpeaking = false;
        this.updateUI('idle');
        // Hide audio visualizer
        const visualizer = document.getElementById('audio-visualizer');
        if (visualizer) {
          visualizer.classList.remove('active');
        }
        URL.revokeObjectURL(audioUrl);
        this.currentAudio = null;
      };
      
      await audio.play();
      
      // Store audio reference for stopping
      this.currentAudio = audio;
      
      return true;
      
    } catch (error) {
      console.error('ElevenLabs error:', error);
      if (this.speechTimeout) {
        clearTimeout(this.speechTimeout);
      }
      this.isSpeaking = false;
      this.updateUI('idle');
      return false;
    }
  }
  
  speakWithBrowser(text) {
    if (!this.synthesis) {
      console.warn('Speech synthesis not supported');
      return;
    }
    
    console.log('🔊 Using browser TTS (fallback)...');
    
    // Clear any existing timeout
    if (this.speechTimeout) {
      clearTimeout(this.speechTimeout);
    }
    
    // Cancel any ongoing speech
    this.synthesis.cancel();
    
    const utterance = new SpeechSynthesisUtterance(text);
    
    // Set language
    const langCode = this.languageMap[this.currentLanguage] || 'en-US';
    utterance.lang = langCode;
    
    // Voice settings
    utterance.rate = 1.15; // Slightly faster for snappier responses
    utterance.pitch = 1.0;
    utterance.volume = 1.0;
    
    // Try to select a good voice for the language
    const voices = this.synthesis.getVoices();
    const preferredVoice = voices.find(voice => 
      voice.lang.startsWith(this.currentLanguage) || 
      voice.lang.startsWith(langCode.split('-')[0])
    );
    if (preferredVoice) {
      utterance.voice = preferredVoice;
    }
    
    // Event handlers
    utterance.onstart = () => {
      console.log('🔊 Browser TTS: Speaking...');
      this.isSpeaking = true;
      this.updateUI('speaking');
      // Show audio visualizer
      const visualizer = document.getElementById('audio-visualizer');
      if (visualizer) {
        visualizer.classList.add('active');
      }
      
      // Set a safety timeout (30 seconds max)
      this.speechTimeout = setTimeout(() => {
        console.warn('⚠️ Browser TTS timeout - forcing stop');
        this.stopSpeaking();
      }, 30000);
    };
    
    utterance.onend = () => {
      console.log('🔊 Browser TTS: Finished');
      if (this.speechTimeout) {
        clearTimeout(this.speechTimeout);
      }
      this.isSpeaking = false;
      this.updateUI('idle');
      // Hide audio visualizer
      const visualizer = document.getElementById('audio-visualizer');
      if (visualizer) {
        visualizer.classList.remove('active');
      }
    };
    
    utterance.onerror = (event) => {
      console.error('Speech synthesis error:', event.error);
      if (this.speechTimeout) {
        clearTimeout(this.speechTimeout);
      }
      this.isSpeaking = false;
      this.updateUI('idle');
      // Hide audio visualizer
      const visualizer = document.getElementById('audio-visualizer');
      if (visualizer) {
        visualizer.classList.remove('active');
      }
    };
    
    // Speak!
    this.synthesis.speak(utterance);
  }
  
  stopSpeaking() {
    console.log('🛑 Stopping all speech...');
    
    // Clear any speech timeout
    if (this.speechTimeout) {
      clearTimeout(this.speechTimeout);
      this.speechTimeout = null;
    }
    
    // Stop ElevenLabs audio if playing
    if (this.currentAudio) {
      try {
        this.currentAudio.pause();
        this.currentAudio.currentTime = 0;
      } catch (e) {
        console.warn('Error pausing audio:', e);
      }
      this.currentAudio = null;
    }
    
    // Stop browser TTS (call multiple times to ensure it stops)
    if (this.synthesis) {
      this.synthesis.cancel();
      // Some browsers need a second call
      setTimeout(() => {
        if (this.synthesis) {
          this.synthesis.cancel();
        }
      }, 10);
    }
    
    // Hide audio visualizer
    const visualizer = document.getElementById('audio-visualizer');
    if (visualizer) {
      visualizer.classList.remove('active');
    }
    
    this.isSpeaking = false;
    this.updateUI('idle');
    console.log('✅ Speech stopped');
  }
  
  setLanguage(lang) {
    this.currentLanguage = lang;
    console.log(`🌐 Voice language set to: ${lang} (${this.languageMap[lang]})`);
  }
  
  setAutoSpeak(enabled) {
    this.autoSpeak = enabled;
    console.log(`🔊 Auto-speak ${enabled ? 'enabled' : 'disabled'}`);
  }
  
  // Set a custom callback for speech results (used by floating orb)
  setCustomCallback(callback) {
    this.customCallback = callback;
    console.log('🎤 Custom callback set');
  }
  
  // Clear custom callback
  clearCustomCallback() {
    this.customCallback = null;
    console.log('🎤 Custom callback cleared');
  }
  
  // Set callback for real-time audio level updates (for mic button animation)
  setAudioLevelCallback(callback) {
    this.audioLevelCallback = callback;
    console.log('🎤 Audio level callback set');
  }
  
  // Clear audio level callback
  clearAudioLevelCallback() {
    this.audioLevelCallback = null;
  }
  
  // Callbacks (override these in your app)
  onSpeechResult(transcript) {
    console.log('📝 Final transcript:', transcript);
    
    // If there's a custom callback, use it and clear it
    if (this.customCallback) {
      console.log('🎤 Using custom callback for transcript');
      const callback = this.customCallback;
      this.customCallback = null; // Clear after use
      callback(transcript);
      return;
    }
    
    // Override this in your integration
  }
  
  showInterimText(text) {
    // Override to show interim results in UI
    console.log('💭 Interim:', text);
  }
  
  showError(message) {
    console.error('❌ Voice Error:', message);
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
    // Override to update your UI based on state
    // States: 'idle', 'listening', 'speaking', 'error'
    console.log('🎨 State:', state);
  }
}

// Diagnostic function to test speech recognition
VoiceChat.prototype.runDiagnostics = async function() {
  console.log('\n========================================');
  console.log('🔍 VOICE CHAT DIAGNOSTICS');
  console.log('========================================\n');
  
  // Check 1: Secure context
  console.log('1️⃣ Secure Context Check:');
  console.log('   isSecureContext:', window.isSecureContext);
  console.log('   Protocol:', window.location.protocol);
  console.log('   Host:', window.location.host);
  if (!window.isSecureContext && window.location.protocol !== 'https:' && !window.location.host.includes('localhost')) {
    console.error('   ❌ FAIL: Speech recognition requires HTTPS or localhost!');
  } else {
    console.log('   ✅ PASS');
  }
  
  // Check 2: API availability
  console.log('\n2️⃣ Speech Recognition API:');
  console.log('   SpeechRecognition:', 'SpeechRecognition' in window);
  console.log('   webkitSpeechRecognition:', 'webkitSpeechRecognition' in window);
  console.log('   Recognition object:', !!this.recognition);
  if (this.recognition) {
    console.log('   ✅ PASS');
  } else {
    console.error('   ❌ FAIL: No recognition object');
  }
  
  // Check 3: Microphone permission
  console.log('\n3️⃣ Microphone Permission:');
  try {
    const permissionStatus = await navigator.permissions.query({ name: 'microphone' });
    console.log('   Permission state:', permissionStatus.state);
    if (permissionStatus.state === 'granted') {
      console.log('   ✅ PASS');
    } else if (permissionStatus.state === 'prompt') {
      console.log('   ⚠️ Will prompt for permission when started');
    } else {
      console.error('   ❌ FAIL: Microphone permission denied');
    }
  } catch (e) {
    console.log('   ⚠️ Could not check permissions (may still work)');
  }
  
  // Check 4: Microphone access
  console.log('\n4️⃣ Microphone Access Test:');
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const tracks = stream.getAudioTracks();
    console.log('   Audio tracks:', tracks.length);
    if (tracks.length > 0) {
      console.log('   Device:', tracks[0].label);
      console.log('   Enabled:', tracks[0].enabled);
      console.log('   Muted:', tracks[0].muted);
      console.log('   ✅ PASS: Microphone accessible');
    }
    // Stop the stream
    tracks.forEach(track => track.stop());
  } catch (e) {
    console.error('   ❌ FAIL:', e.message);
  }
  
  // Check 5: Current state
  console.log('\n5️⃣ VoiceChat State:');
  console.log('   isListening:', this.isListening);
  console.log('   isSpeaking:', this.isSpeaking);
  console.log('   currentLanguage:', this.currentLanguage);
  console.log('   autoSpeak:', this.autoSpeak);
  
  // Check 6: Test recognition
  console.log('\n6️⃣ Quick Recognition Test:');
  console.log('   Starting 3-second test...');
  console.log('   🎤 Please say something!');
  
  return new Promise((resolve) => {
    const testRecognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
    testRecognition.continuous = false;
    testRecognition.interimResults = true;
    testRecognition.lang = this.recognition.lang || 'en-US';
    
    let gotResult = false;
    
    testRecognition.onresult = (event) => {
      gotResult = true;
      const transcript = event.results[0][0].transcript;
      console.log('   ✅ PASS: Got result:', `"${transcript}"`);
    };
    
    testRecognition.onerror = (event) => {
      console.error('   ❌ Error:', event.error);
    };
    
    testRecognition.onend = () => {
      if (!gotResult) {
        console.log('   ⚠️ No speech detected in test');
      }
      console.log('\n========================================');
      console.log('🔍 DIAGNOSTICS COMPLETE');
      console.log('========================================\n');
      resolve();
    };
    
    testRecognition.start();
    
    // Auto-stop after 3 seconds
    setTimeout(() => {
      try {
        testRecognition.stop();
      } catch (e) {}
    }, 3000);
  });
};

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
  module.exports = VoiceChat;
}

