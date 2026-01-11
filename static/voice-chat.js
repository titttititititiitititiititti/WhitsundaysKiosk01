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
    
    // Configure recognition
    this.recognition.continuous = false; // Stop after one utterance
    this.recognition.interimResults = true; // Show results as user speaks
    this.recognition.maxAlternatives = 1;
    
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
      console.log('🎤 Speech recognition ENDED');
      
      // IMPORTANT: If we have a transcript but never got a "final" result,
      // send the last transcript anyway (fallback for when recognition ends abruptly)
      if (this.lastTranscript && !this.hasFinalResult) {
        console.log('🎤 No final result received - using last transcript as fallback');
        console.log(`🗣️ FALLBACK FINAL: "${this.lastTranscript}"`);
        this.onSpeechResult(this.lastTranscript);
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
          // User finished speaking - send to chat
          this.clearSilenceTimer();
          this.onSpeechResult(transcript);
        } else {
          // Show interim results - start silence timer
          this.showInterimText(transcript);
          this.startSilenceTimer();
        }
      }
    };
    
    // No match found
    this.recognition.onnomatch = () => {
      console.log('🎤 No speech was recognized');
      this.showError("Sorry, I couldn't understand that. Could you try again?");
    };
    
    // Error handling
    this.recognition.onerror = (event) => {
      console.error('🎤 Speech recognition ERROR:', event.error, event.message);
      this.isListening = false;
      this.updateUI('error');
      
      // User-friendly error messages
      let errorMsg = '';
      let showErrorToUser = true;
      
      switch(event.error) {
        case 'no-speech':
          // Don't show error - common on mobile when mic is still warming up
          console.log('🎤 No speech detected - user may not have spoken yet');
          showErrorToUser = false;
          break;
        case 'audio-capture':
          errorMsg = "Microphone not available. Please check that no other app is using it.";
          break;
        case 'not-allowed':
          errorMsg = "Please allow microphone access to use voice input.";
          break;
        case 'network':
          errorMsg = "Network error. Please check your connection and try again.";
          break;
        case 'aborted':
          console.log('🎤 Recognition was aborted');
          showErrorToUser = false;
          break;
        case 'service-not-allowed':
          errorMsg = "Voice service not available. Try typing instead.";
          break;
        default:
          console.log('🎤 Unknown error:', event.error);
          showErrorToUser = false;
      }
      
      if (showErrorToUser && errorMsg) {
        this.showError(errorMsg);
      }
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
    
    console.log(`🎤 Starting speech recognition...`);
    console.log(`   Language: ${this.recognition.lang}`);
    console.log(`   Continuous: ${this.recognition.continuous}`);
    console.log(`   Interim results: ${this.recognition.interimResults}`);
    
    // Start audio level monitoring to verify mic is working
    this.startAudioMonitoring();
    
    try {
      this.recognition.start();
      console.log('🎤 recognition.start() called - waiting for onstart event...');
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
  
  async startAudioMonitoring() {
    // Monitor actual audio levels to diagnose mic issues
    try {
      // List available microphones
      const devices = await navigator.mediaDevices.enumerateDevices();
      const mics = devices.filter(d => d.kind === 'audioinput');
      console.log('🎤 Available microphones:');
      mics.forEach((m, i) => console.log(`   ${i + 1}. ${m.label || 'Unknown mic'} (${m.deviceId.substring(0, 8)}...)`));
      
      // Try to get the default microphone with specific constraints
      const constraints = {
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      };
      
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      
      // Resume audio context if suspended (required after user interaction)
      if (audioContext.state === 'suspended') {
        console.log('🎤 AudioContext suspended, resuming...');
        await audioContext.resume();
      }
      console.log('🎤 AudioContext state:', audioContext.state);
      
      const analyser = audioContext.createAnalyser();
      const microphone = audioContext.createMediaStreamSource(stream);
      
      // Log which track we're using
      const track = stream.getAudioTracks()[0];
      console.log('🎤 Using microphone:', track.label);
      console.log('🎤 Track settings:', JSON.stringify(track.getSettings()));
      
      microphone.connect(analyser);
      analyser.fftSize = 256;
      
      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      let maxLevel = 0;
      let hasSpoken = false;
      let stopped = false;
      
      this.audioMonitorStream = stream;
      this.audioMonitorContext = audioContext;
      
      const checkLevel = () => {
        if (!this.isListening || stopped) {
          if (!stopped) {
            stopped = true;
            // Stop monitoring when not listening
            stream.getTracks().forEach(track => track.stop());
            audioContext.close().catch(() => {}); // Ignore already closed error
            console.log(`🎤 Audio monitoring stopped. Max level detected: ${maxLevel}`);
            if (maxLevel < 10) {
              console.warn('⚠️ Very low audio levels detected!');
              console.warn('   This usually means Chrome is using the wrong microphone.');
              console.warn('   Fix: Click the lock 🔒 icon in Chrome address bar → Site Settings → Microphone');
              console.warn('   Or try: chrome://settings/content/microphone');
            }
          }
          return;
        }
        
        analyser.getByteFrequencyData(dataArray);
        const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
        
        if (average > maxLevel) {
          maxLevel = average;
        }
        
        // Call audio level callback for UI updates (e.g., mic button scaling)
        if (this.audioLevelCallback && typeof this.audioLevelCallback === 'function') {
          this.audioLevelCallback(average);
        }
        
        // Log when audio is detected
        if (average > 20 && !hasSpoken) {
          console.log(`🎤 Audio level: ${average.toFixed(0)} - Sound detected!`);
          hasSpoken = true;
        } else if (average > 50) {
          console.log(`🎤 Audio level: ${average.toFixed(0)} - Loud sound!`);
        }
        
        requestAnimationFrame(checkLevel);
      };
      
      checkLevel();
      console.log('🎤 Audio level monitoring started');
      
    } catch (e) {
      console.warn('🎤 Could not start audio monitoring:', e.message);
    }
  }
  
  // Helper to list and select microphones
  async listMicrophones() {
    const devices = await navigator.mediaDevices.enumerateDevices();
    const mics = devices.filter(d => d.kind === 'audioinput');
    console.log('\n🎤 AVAILABLE MICROPHONES:');
    console.log('========================');
    mics.forEach((m, i) => {
      console.log(`${i + 1}. ${m.label || 'Unnamed microphone'}`);
      console.log(`   ID: ${m.deviceId}`);
    });
    console.log('\nTo change microphone in Chrome:');
    console.log('1. Click the 🔒 lock icon in the address bar');
    console.log('2. Click "Site settings"');
    console.log('3. Find "Microphone" and select your preferred device');
    console.log('4. Refresh the page\n');
    return mics;
  }
  
  stopListening() {
    if (this.recognition && this.isListening) {
      this.recognition.stop();
    }
    
    // Clear silence timer
    this.clearSilenceTimer();
    
    // Stop audio monitoring
    if (this.audioMonitorStream) {
      this.audioMonitorStream.getTracks().forEach(track => track.stop());
      this.audioMonitorStream = null;
    }
    if (this.audioMonitorContext) {
      this.audioMonitorContext.close().catch(() => {});
      this.audioMonitorContext = null;
    }
  }
  
  startSilenceTimer() {
    // Clear any existing timer
    this.clearSilenceTimer();
    
    // Start new timer - if 3 seconds pass with no new speech, auto-send
    this.silenceTimer = setTimeout(() => {
      if (this.isListening && this.lastTranscript && !this.hasFinalResult) {
        console.log('⏱️ 3 seconds of silence - auto-sending message');
        // Stop recognition and send the last transcript
        this.hasFinalResult = true; // Prevent duplicate sends
        this.recognition.stop();
        this.onSpeechResult(this.lastTranscript);
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
    // Override to show errors in UI
    console.error('❌ Error:', message);
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

