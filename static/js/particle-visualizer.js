/**
 * Premium AI Particle Visualizer
 * 
 * A beautiful, audio-reactive particle system for AI assistant visuals.
 * Inspired by modern voice assistants like Siri.
 * 
 * Features:
 * - Smooth particle flow in a spherical formation
 * - Audio-reactive with WebAudio API
 * - Two states: Idle (gentle) and Speaking (dynamic)
 * - Optimized for kiosk hardware
 */

class ParticleVisualizer {
  constructor(containerId = 'ai-visualizer-container') {
    this.container = document.getElementById(containerId);
    if (!this.container) {
      console.warn('Particle visualizer container not found:', containerId);
      return;
    }

    // Canvas setup
    this.canvas = null;
    this.ctx = null;
    
    // Particle system
    this.particles = [];
    this.particleCount = 120; // Balanced for performance
    
    // Audio analysis
    this.audioContext = null;
    this.analyser = null;
    this.audioSource = null;
    this.dataArray = null;
    this.isAudioConnected = false;
    
    // State
    this.isSpeaking = false;
    this.currentAmplitude = 0;
    this.targetAmplitude = 0;
    this.animationId = null;
    this.time = 0;
    
    // Visual settings - premium purple/blue palette - BRIGHT and VISIBLE
    this.settings = {
      // Colors (HSL for easy manipulation)
      baseHue: 260,           // Purple
      accentHue: 220,         // Blue
      saturation: 90,         // High saturation for vivid colors
      lightness: 70,          // Bright
      
      // Particle properties - LARGER for visibility
      particleMinSize: 4,
      particleMaxSize: 12,
      
      // Sphere properties
      sphereRadius: 120,
      sphereRadiusVariation: 25,
      
      // Motion
      idleSpeed: 0.4,
      speakingSpeed: 1.5,
      turbulence: 0.6,
      
      // Glow - STRONGER
      glowIntensity: 0.8,
      glowRadius: 180,
      
      // Audio reactivity
      amplitudeSmoothing: 0.15,
      amplitudeMultiplier: 2.5,
    };
    
    this.init();
  }
  
  init() {
    this.setupCanvas();
    this.createParticles();
    this.animate();
    
    // Handle resize
    window.addEventListener('resize', () => this.onResize());
    
    console.log('✨ Particle Visualizer initialized');
    console.log('✨ Container:', this.container);
    console.log('✨ Container size:', this.width, 'x', this.height);
    console.log('✨ Canvas:', this.canvas);
    console.log('✨ Particles count:', this.particles.length);
    console.log('✨ Sphere radius:', this.settings.sphereRadius);
  }
  
  setupCanvas() {
    // Create canvas
    this.canvas = document.createElement('canvas');
    this.canvas.id = 'particle-canvas';
    this.canvas.style.cssText = 'width: 100%; height: 100%; display: block; background: transparent;';
    
    // Remove any existing canvas
    const existingCanvas = this.container.querySelector('canvas');
    if (existingCanvas) {
      existingCanvas.remove();
    }
    
    this.container.appendChild(this.canvas);
    this.ctx = this.canvas.getContext('2d');
    
    // Set size
    this.onResize();
  }
  
  onResize() {
    const rect = this.container.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio, 2); // Cap for performance
    
    // Use rect dimensions or fallback to 350px
    const containerWidth = rect.width > 0 ? rect.width : 350;
    const containerHeight = rect.height > 0 ? rect.height : 350;
    
    this.canvas.width = containerWidth * dpr;
    this.canvas.height = containerHeight * dpr;
    
    this.ctx.scale(dpr, dpr);
    
    this.width = containerWidth;
    this.height = containerHeight;
    this.centerX = this.width / 2;
    this.centerY = this.height / 2;
    
    // Adjust sphere radius based on container size
    this.settings.sphereRadius = Math.min(this.width, this.height) * 0.35;
    this.settings.glowRadius = this.settings.sphereRadius * 1.6;
    
    console.log('✨ Canvas resized:', this.width, 'x', this.height, 'sphere radius:', this.settings.sphereRadius);
  }
  
  createParticles() {
    this.particles = [];
    
    for (let i = 0; i < this.particleCount; i++) {
      this.particles.push(this.createParticle(i));
    }
  }
  
  createParticle(index) {
    // Distribute particles on a sphere using fibonacci sphere algorithm
    const goldenRatio = (1 + Math.sqrt(5)) / 2;
    const theta = 2 * Math.PI * index / goldenRatio;
    const phi = Math.acos(1 - 2 * (index + 0.5) / this.particleCount);
    
    // Convert to cartesian (normalized)
    const x = Math.sin(phi) * Math.cos(theta);
    const y = Math.sin(phi) * Math.sin(theta);
    const z = Math.cos(phi);
    
    return {
      // Base position on sphere
      baseX: x,
      baseY: y,
      baseZ: z,
      
      // Current position (will be animated)
      x: 0,
      y: 0,
      z: 0,
      
      // Animation offsets
      phaseOffset: Math.random() * Math.PI * 2,
      speedMultiplier: 0.8 + Math.random() * 0.4,
      radiusOffset: (Math.random() - 0.5) * this.settings.sphereRadiusVariation,
      
      // Visual properties
      size: this.settings.particleMinSize + Math.random() * (this.settings.particleMaxSize - this.settings.particleMinSize),
      hueOffset: (Math.random() - 0.5) * 40,
      alpha: 0.6 + Math.random() * 0.4,
    };
  }
  
  /**
   * Connect to an audio element for reactivity
   * @param {HTMLAudioElement} audioElement - The audio element playing ElevenLabs speech
   */
  connectAudio(audioElement) {
    if (!audioElement) {
      console.warn('No audio element provided');
      return;
    }
    
    this.audioElement = audioElement;
    
    try {
      // Create audio context if needed
      if (!this.audioContext) {
        this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
      }
      
      // Resume context if suspended
      if (this.audioContext.state === 'suspended') {
        this.audioContext.resume();
      }
      
      // Create analyser if needed
      if (!this.analyser) {
        this.analyser = this.audioContext.createAnalyser();
        this.analyser.fftSize = 256;
        this.analyser.smoothingTimeConstant = 0.7;
        this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);
      }
      
      // Check if already connected
      if (audioElement._particleSourceNode) {
        this.audioSource = audioElement._particleSourceNode;
        this.isAudioConnected = true;
        return;
      }
      
      // Create and connect source
      this.audioSource = this.audioContext.createMediaElementSource(audioElement);
      audioElement._particleSourceNode = this.audioSource;
      
      this.audioSource.connect(this.analyser);
      this.analyser.connect(this.audioContext.destination);
      
      this.isAudioConnected = true;
      console.log('🔊 Audio connected to particle visualizer');
      
    } catch (error) {
      console.error('Error connecting audio:', error);
      if (error.message && error.message.includes('already connected')) {
        this.isAudioConnected = true;
      }
    }
  }
  
  /**
   * Start speaking animation
   */
  startSpeaking() {
    console.log('✨ Particle visualizer: START SPEAKING');
    this.isSpeaking = true;
    this.targetAmplitude = 0.5;
    this.currentAmplitude = 0.3; // Immediate feedback
    
    if (this.audioContext && this.audioContext.state === 'suspended') {
      this.audioContext.resume();
    }
  }
  
  /**
   * Stop speaking animation
   */
  stopSpeaking() {
    console.log('✨ Particle visualizer: STOP SPEAKING');
    this.isSpeaking = false;
    this.targetAmplitude = 0;
  }
  
  /**
   * Get current audio amplitude (real or simulated)
   * AUDIO DRIVES VISUAL: This is where audio analysis happens
   */
  getAmplitude() {
    if (!this.isSpeaking) {
      return 0;
    }
    
    // Try real audio data first
    if (this.isAudioConnected && this.analyser && this.audioContext) {
      try {
        if (this.audioContext.state === 'suspended') {
          this.audioContext.resume();
        }
        
        this.analyser.getByteFrequencyData(this.dataArray);
        
        // Calculate RMS with emphasis on voice frequencies (85-255 Hz range)
        let sum = 0;
        let count = 0;
        for (let i = 2; i < Math.min(40, this.dataArray.length); i++) {
          sum += this.dataArray[i] * this.dataArray[i];
          count++;
        }
        const rms = Math.sqrt(sum / count) / 255;
        
        // If we got real data, use it
        if (rms > 0.02) {
          return Math.min(1, rms * this.settings.amplitudeMultiplier);
        }
      } catch (e) {
        // Fall through to simulated
      }
    }
    
    // SIMULATED SPEECH PATTERN - natural rhythm when speaking
    // Creates organic, speech-like variations
    const t = this.time;
    const wave1 = Math.sin(t * 6) * 0.2;           // Fast pulse (syllables)
    const wave2 = Math.sin(t * 2.5) * 0.15;        // Medium rhythm (words)
    const wave3 = Math.sin(t * 0.8) * 0.1;         // Slow variation (phrases)
    const noise = (Math.random() - 0.5) * 0.15;    // Natural variation
    
    const simulated = 0.45 + wave1 + wave2 + wave3 + noise;
    return Math.max(0.15, Math.min(0.9, simulated));
  }
  
  /**
   * Main animation loop
   * AUDIO DRIVES VISUAL: amplitude affects particle positions, sizes, colors
   */
  animate() {
    this.animationId = requestAnimationFrame(() => this.animate());
    
    const deltaTime = 0.016; // ~60fps
    this.time += deltaTime;
    
    // Get audio amplitude
    const rawAmplitude = this.getAmplitude();
    
    // Smooth amplitude changes
    const smoothing = this.isSpeaking ? 0.25 : 0.1;
    this.targetAmplitude = rawAmplitude;
    this.currentAmplitude += (this.targetAmplitude - this.currentAmplitude) * smoothing;
    
    // Clear canvas
    this.ctx.clearRect(0, 0, this.width, this.height);
    
    // Draw background glow
    this.drawGlow();
    
    // Update and draw particles
    this.updateParticles();
    this.drawParticles();
  }
  
  /**
   * Draw ambient glow behind particles
   * AUDIO DRIVES VISUAL: glow intensity based on amplitude
   */
  drawGlow() {
    const glowIntensity = this.settings.glowIntensity + this.currentAmplitude * 0.5;
    const glowRadius = this.settings.glowRadius * (1 + this.currentAmplitude * 0.4);
    
    // Create radial gradient for glow - BRIGHTER
    const gradient = this.ctx.createRadialGradient(
      this.centerX, this.centerY, 0,
      this.centerX, this.centerY, glowRadius
    );
    
    // Color shifts with amplitude
    const hue = this.settings.baseHue + this.currentAmplitude * 20;
    
    // More intense glow for visibility
    gradient.addColorStop(0, `hsla(${hue}, ${this.settings.saturation}%, 85%, ${glowIntensity * 0.7})`);
    gradient.addColorStop(0.2, `hsla(${hue}, ${this.settings.saturation}%, ${this.settings.lightness}%, ${glowIntensity * 0.5})`);
    gradient.addColorStop(0.4, `hsla(${hue}, ${this.settings.saturation}%, ${this.settings.lightness}%, ${glowIntensity * 0.3})`);
    gradient.addColorStop(0.7, `hsla(${hue + 20}, ${this.settings.saturation}%, ${this.settings.lightness}%, ${glowIntensity * 0.15})`);
    gradient.addColorStop(1, 'transparent');
    
    this.ctx.fillStyle = gradient;
    this.ctx.fillRect(0, 0, this.width, this.height);
  }
  
  /**
   * Update particle positions
   * AUDIO DRIVES VISUAL: amplitude affects radius, turbulence, speed
   */
  updateParticles() {
    const speed = this.isSpeaking ? this.settings.speakingSpeed : this.settings.idleSpeed;
    const turbulence = this.settings.turbulence * (1 + this.currentAmplitude * 2);
    
    // AUDIO DRIVES VISUAL: Sphere expands/contracts with amplitude
    const radiusMultiplier = 1 + this.currentAmplitude * 0.4;
    
    for (const p of this.particles) {
      // Base rotation around Y axis (orbit)
      const rotationSpeed = speed * p.speedMultiplier * 0.5;
      const angle = this.time * rotationSpeed + p.phaseOffset;
      
      // Calculate 3D position with audio-reactive radius
      const radius = (this.settings.sphereRadius + p.radiusOffset) * radiusMultiplier;
      
      // Rotate base position
      const cosA = Math.cos(angle);
      const sinA = Math.sin(angle);
      
      // Apply rotation around Y axis
      const rotatedX = p.baseX * cosA - p.baseZ * sinA;
      const rotatedZ = p.baseX * sinA + p.baseZ * cosA;
      
      // AUDIO DRIVES VISUAL: Add turbulence based on amplitude
      const turbX = Math.sin(this.time * 3 + p.phaseOffset) * turbulence;
      const turbY = Math.cos(this.time * 2.5 + p.phaseOffset * 1.3) * turbulence;
      const turbZ = Math.sin(this.time * 2 + p.phaseOffset * 0.7) * turbulence;
      
      // Final position
      p.x = this.centerX + (rotatedX * radius) + turbX * this.currentAmplitude * 30;
      p.y = this.centerY + (p.baseY * radius) + turbY * this.currentAmplitude * 30;
      p.z = rotatedZ; // Used for depth sorting and size
      
      // AUDIO DRIVES VISUAL: Size pulses with amplitude
      p.currentSize = p.size * (1 + this.currentAmplitude * 0.8);
      
      // AUDIO DRIVES VISUAL: Alpha increases when speaking
      p.currentAlpha = p.alpha * (0.7 + this.currentAmplitude * 0.5);
    }
    
    // Sort by Z for proper depth rendering (back to front)
    this.particles.sort((a, b) => a.z - b.z);
  }
  
  /**
   * Draw all particles
   * AUDIO DRIVES VISUAL: colors and brightness react to amplitude
   */
  drawParticles() {
    for (const p of this.particles) {
      // Depth-based size and alpha (closer = larger, more opaque)
      const depthFactor = (p.z + 1) / 2; // 0 to 1
      const size = p.currentSize * (0.5 + depthFactor * 0.5);
      const alpha = p.currentAlpha * (0.4 + depthFactor * 0.6);
      
      // AUDIO DRIVES VISUAL: Color shifts with amplitude
      const hue = this.settings.baseHue + p.hueOffset + this.currentAmplitude * 30;
      const saturation = this.settings.saturation + this.currentAmplitude * 10;
      const lightness = this.settings.lightness + this.currentAmplitude * 15;
      
      // Draw particle with glow
      this.ctx.beginPath();
      this.ctx.arc(p.x, p.y, size, 0, Math.PI * 2);
      
      // Create gradient for soft particle
      const particleGradient = this.ctx.createRadialGradient(
        p.x, p.y, 0,
        p.x, p.y, size
      );
      
      particleGradient.addColorStop(0, `hsla(${hue}, ${saturation}%, ${lightness + 20}%, ${alpha})`);
      particleGradient.addColorStop(0.4, `hsla(${hue}, ${saturation}%, ${lightness}%, ${alpha * 0.8})`);
      particleGradient.addColorStop(1, `hsla(${hue}, ${saturation}%, ${lightness - 10}%, 0)`);
      
      this.ctx.fillStyle = particleGradient;
      this.ctx.fill();
      
      // Add bright center point for closest particles
      if (depthFactor > 0.7) {
        this.ctx.beginPath();
        this.ctx.arc(p.x, p.y, size * 0.3, 0, Math.PI * 2);
        this.ctx.fillStyle = `hsla(${hue}, ${saturation}%, 90%, ${alpha * 0.6})`;
        this.ctx.fill();
      }
    }
  }
  
  show() {
    if (this.container) {
      this.container.classList.remove('hidden');
      this.container.style.opacity = '1';
    }
  }
  
  hide() {
    if (this.container) {
      this.container.classList.add('hidden');
      this.container.style.opacity = '0';
    }
  }
  
  destroy() {
    if (this.animationId) {
      cancelAnimationFrame(this.animationId);
    }
    
    if (this.audioSource) {
      try {
        this.audioSource.disconnect();
      } catch (e) {}
    }
    
    if (this.audioContext) {
      try {
        this.audioContext.close();
      } catch (e) {}
    }
    
    if (this.canvas && this.canvas.parentNode) {
      this.canvas.parentNode.removeChild(this.canvas);
    }
  }
}

// Global instance
let particleVisualizer = null;

/**
 * Initialize the particle visualizer
 */
function initParticleVisualizer() {
  const container = document.getElementById('ai-visualizer-container');
  if (!container) {
    console.log('✨ Visualizer container not found, will init when available');
    return null;
  }
  
  // If already initialized, return existing instance
  if (particleVisualizer && particleVisualizer.canvas) {
    container.classList.remove('hidden');
    return particleVisualizer;
  }
  
  console.log('✨ Creating new Particle Visualizer...');
  
  try {
    particleVisualizer = new ParticleVisualizer('ai-visualizer-container');
    window.particleVisualizer = particleVisualizer;
    
    container.classList.remove('hidden');
    
    console.log('✨ Particle Visualizer ready');
    return particleVisualizer;
  } catch (error) {
    console.error('✨ Error initializing visualizer:', error);
    return null;
  }
}

/**
 * Connect audio to the visualizer
 */
function connectVisualizerToAudio(audioElement) {
  if (!particleVisualizer) {
    particleVisualizer = initParticleVisualizer();
  }
  
  if (particleVisualizer && audioElement) {
    particleVisualizer.connectAudio(audioElement);
  }
}

/**
 * Start speaking animation
 */
function visualizerStartSpeaking() {
  if (particleVisualizer) {
    particleVisualizer.startSpeaking();
  }
}

/**
 * Stop speaking animation
 */
function visualizerStopSpeaking() {
  if (particleVisualizer) {
    particleVisualizer.stopSpeaking();
  }
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initParticleVisualizer);
} else {
  setTimeout(initParticleVisualizer, 100);
}

// Export for global access
window.ParticleVisualizer = ParticleVisualizer;
window.initParticleVisualizer = initParticleVisualizer;
window.connectVisualizerToAudio = connectVisualizerToAudio;
window.visualizerStartSpeaking = visualizerStartSpeaking;
window.visualizerStopSpeaking = visualizerStopSpeaking;

// Debug function
window.testVisualizer = function() {
  console.log('🧪 Testing visualizer...');
  if (window.particleVisualizer) {
    console.log('🧪 Starting speaking mode for 5 seconds...');
    window.particleVisualizer.startSpeaking();
    setTimeout(() => {
      console.log('🧪 Stopping speaking mode');
      window.particleVisualizer.stopSpeaking();
    }, 5000);
  } else {
    console.log('🧪 No visualizer found, initializing...');
    initParticleVisualizer();
  }
};

