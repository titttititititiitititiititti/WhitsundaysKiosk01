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
    // Check browser support
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      console.warn('Speech recognition not supported in this browser');
      return;
    }
    
    // Initialize speech recognition
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    this.recognition = new SpeechRecognition();
    
    // Configure recognition
    this.recognition.continuous = false; // Stop after one utterance
    this.recognition.interimResults = true; // Show results as user speaks
    this.recognition.maxAlternatives = 1;
    
    // Set up event handlers
    this.setupRecognitionHandlers();
    
    console.log('✅ Voice Chat initialized');
  }
  
  setupRecognitionHandlers() {
    if (!this.recognition) return;
    
    // When speech recognition starts
    this.recognition.onstart = () => {
      console.log('🎤 Listening...');
      this.isListening = true;
      this.updateUI('listening');
    };
    
    // When speech recognition ends
    this.recognition.onend = () => {
      console.log('🎤 Stopped listening');
      this.isListening = false;
      this.updateUI('idle');
    };
    
    // When we get speech results
    this.recognition.onresult = (event) => {
      const result = event.results[event.results.length - 1];
      const transcript = result[0].transcript;
      const isFinal = result.isFinal;
      
      console.log(`🗣️ ${isFinal ? 'Final' : 'Interim'}: "${transcript}"`);
      
      if (isFinal) {
        // User finished speaking - send to chat
        this.onSpeechResult(transcript);
      } else {
        // Show interim results
        this.showInterimText(transcript);
      }
    };
    
    // Error handling
    this.recognition.onerror = (event) => {
      console.error('Speech recognition error:', event.error);
      this.isListening = false;
      this.updateUI('error');
      
      // User-friendly error messages
      let errorMsg = '';
      switch(event.error) {
        case 'no-speech':
          errorMsg = "I didn't hear anything. Try again?";
          break;
        case 'audio-capture':
          errorMsg = "Microphone not available. Please check permissions.";
          break;
        case 'not-allowed':
          errorMsg = "Microphone access denied. Please allow microphone access.";
          break;
        default:
          errorMsg = `Voice error: ${event.error}`;
      }
      
      this.showError(errorMsg);
    };
  }
  
  startListening() {
    if (!this.recognition) {
      alert('Voice recognition is not available in your browser.');
      return;
    }
    
    if (this.isListening) {
      this.stopListening();
      return;
    }
    
    // Stop any ongoing speech
    if (this.isSpeaking) {
      this.stopSpeaking();
    }
    
    // Set language for recognition
    this.recognition.lang = this.languageMap[this.currentLanguage] || 'en-US';
    
    console.log(`🎤 Starting recognition in ${this.recognition.lang}...`);
    
    try {
      this.recognition.start();
    } catch (error) {
      console.error('Failed to start recognition:', error);
      this.showError('Could not start microphone. Try again.');
    }
  }
  
  stopListening() {
    if (this.recognition && this.isListening) {
      this.recognition.stop();
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
      
      // Play audio
      const audio = new Audio(audioUrl);
      
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
  
  // Callbacks (override these in your app)
  onSpeechResult(transcript) {
    console.log('📝 Final transcript:', transcript);
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

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
  module.exports = VoiceChat;
}

