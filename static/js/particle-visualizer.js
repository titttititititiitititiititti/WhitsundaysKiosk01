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
    
    // Visual settings - premium purple/blue palette
    this.settings = {
      // Colors (HSL for easy manipulation)
      baseHue: 260,           // Purple
      accentHue: 220,         // Blue
      saturation: 85,
      lightness: 70,
      
      // Particle properties
      particleMinSize: 3,
      particleMaxSize: 9,
      
      // Sphere properties
      sphereRadius: 55,
      sphereRadiusVariation: 25,
      
      // Motion - smooth and controlled
      idleSpeed: 0.28,
      speakingSpeed: 0.55,   // Slower when speaking for cleaner orbits
      turbulence: 0.3,       // Less chaotic
      
      // Glow
      glowIntensity: 0.52,
      glowRadius: 95,
      
      // Audio reactivity - balanced for good sync
      amplitudeSmoothing: 0.08,   // Smooth but responsive
      amplitudeMultiplier: 2.2,   // Good amplification
      amplitudeThreshold: 0.03,   // Sensitive but not too twitchy
    };
    
    this.init();
  }
  
  init() {
    this.setupCanvas();
    this.createParticles();
    this.animate();
    
    // Handle resize
    window.addEventListener('resize', () => this.onResize());
    
    console.log('✨ Particle Visualizer initialized -', this.particles.length, 'particles');
  }
  
  setupCanvas() {
    // Create canvas - no visible boundary
    this.canvas = document.createElement('canvas');
    this.canvas.id = 'particle-canvas';
    this.canvas.style.cssText = 'width: 100%; height: 100%; display: block; background: transparent; position: absolute; top: 0; left: 0;';
    
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
    
    // Keep sphere radius FIXED - don't scale with container
    // This keeps the orb reasonably sized while container is large (no cutoff)
    this.settings.sphereRadius = 70;  // Good visible size
    this.settings.glowRadius = 110;   // Matching glow size
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
        if (rms > 0.015) {
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
    let rawAmplitude = this.getAmplitude();
    
    // Apply threshold - ignore tiny fluctuations
    if (rawAmplitude < this.settings.amplitudeThreshold) {
      rawAmplitude = 0;
    }
    
    // Very smooth amplitude changes - prevents twitchy start/stop
    const smoothing = this.settings.amplitudeSmoothing;
    this.targetAmplitude = rawAmplitude;
    this.currentAmplitude += (this.targetAmplitude - this.currentAmplitude) * smoothing;
    
    // Floor very small values to zero for cleaner idle state
    if (this.currentAmplitude < 0.015) {
      this.currentAmplitude = 0;
    }
    
    // Clear canvas completely
    this.ctx.clearRect(0, 0, this.width, this.height);
    
    // Draw background glow
    this.drawGlow();
    
    // Update particle positions first
    this.updateParticles();
    
    // DEPTH SORTING: Draw in correct order for 3D effect
    // 1. Draw particles BEHIND the orb (negative Z)
    this.drawParticlesBehind();
    
    // 2. Draw central orb
    this.drawCentralOrb();
    
    // 3. Draw particles IN FRONT of the orb (positive Z)
    this.drawParticlesInFront();
  }
  
  /**
   * Draw the central glowing orb - 3D sphere effect
   * AUDIO DRIVES VISUAL: orb size and brightness react to amplitude
   */
  drawCentralOrb() {
    const baseRadius = this.settings.sphereRadius * 0.5;
    // AUDIO DRIVES VISUAL: orb pulses with amplitude
    const radius = baseRadius * (1 + this.currentAmplitude * 0.2);
    const hue = this.settings.baseHue + this.currentAmplitude * 20;
    
    // === OUTER GLOW (soft ambient light) ===
    for (let i = 4; i >= 0; i--) {
      const glowRadius = radius * (1.8 - i * 0.15);
      const alpha = 0.08 - i * 0.015;
      
      this.ctx.beginPath();
      this.ctx.arc(this.centerX, this.centerY, glowRadius, 0, Math.PI * 2);
      this.ctx.fillStyle = `hsla(${hue}, ${this.settings.saturation}%, 70%, ${Math.max(0, alpha * (1 + this.currentAmplitude))})`;
      this.ctx.fill();
    }
    
    // === SHADOW (bottom edge for 3D depth) ===
    const shadowGradient = this.ctx.createRadialGradient(
      this.centerX, this.centerY + radius * 0.15, radius * 0.5,
      this.centerX, this.centerY + radius * 0.1, radius * 1.1
    );
    shadowGradient.addColorStop(0, 'rgba(0, 0, 0, 0)');
    shadowGradient.addColorStop(0.7, 'rgba(30, 0, 60, 0.15)');
    shadowGradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
    
    this.ctx.beginPath();
    this.ctx.arc(this.centerX, this.centerY, radius * 1.1, 0, Math.PI * 2);
    this.ctx.fillStyle = shadowGradient;
    this.ctx.fill();
    
    // === MAIN SPHERE BODY (3D gradient - light from top-left) ===
    const sphereGradient = this.ctx.createRadialGradient(
      this.centerX - radius * 0.4, this.centerY - radius * 0.4, 0,
      this.centerX + radius * 0.1, this.centerY + radius * 0.1, radius * 1.2
    );
    
    const brightness = 70 + this.currentAmplitude * 15;
    
    sphereGradient.addColorStop(0, `hsla(${hue - 10}, 70%, 95%, 1)`);      // Bright highlight
    sphereGradient.addColorStop(0.15, `hsla(${hue}, 80%, ${brightness + 15}%, 0.98)`);  // Light area
    sphereGradient.addColorStop(0.4, `hsla(${hue}, ${this.settings.saturation}%, ${brightness}%, 0.95)`);  // Mid tone
    sphereGradient.addColorStop(0.7, `hsla(${hue + 15}, ${this.settings.saturation}%, ${brightness - 15}%, 0.9)`); // Shadow
    sphereGradient.addColorStop(1, `hsla(${hue + 20}, ${this.settings.saturation - 10}%, ${brightness - 30}%, 0.85)`); // Dark edge
    
    this.ctx.beginPath();
    this.ctx.arc(this.centerX, this.centerY, radius, 0, Math.PI * 2);
    this.ctx.fillStyle = sphereGradient;
    this.ctx.fill();
    
    // === RIM LIGHT (subtle edge highlight from behind) ===
    const rimGradient = this.ctx.createRadialGradient(
      this.centerX + radius * 0.5, this.centerY + radius * 0.3, 0,
      this.centerX, this.centerY, radius
    );
    rimGradient.addColorStop(0, `hsla(${hue + 30}, 90%, 85%, ${0.3 + this.currentAmplitude * 0.2})`);
    rimGradient.addColorStop(0.3, `hsla(${hue + 20}, 80%, 75%, 0.1)`);
    rimGradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
    
    this.ctx.beginPath();
    this.ctx.arc(this.centerX, this.centerY, radius, 0, Math.PI * 2);
    this.ctx.fillStyle = rimGradient;
    this.ctx.fill();
    
    // === INNER GLOW (energy core) ===
    const coreRadius = radius * 0.5;
    const coreGradient = this.ctx.createRadialGradient(
      this.centerX, this.centerY, 0,
      this.centerX, this.centerY, coreRadius
    );
    
    const coreIntensity = 0.4 + this.currentAmplitude * 0.4;
    coreGradient.addColorStop(0, `rgba(255, 255, 255, ${coreIntensity})`);
    coreGradient.addColorStop(0.3, `hsla(${hue - 10}, 70%, 90%, ${coreIntensity * 0.7})`);
    coreGradient.addColorStop(0.7, `hsla(${hue}, 60%, 80%, ${coreIntensity * 0.3})`);
    coreGradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
    
    this.ctx.beginPath();
    this.ctx.arc(this.centerX, this.centerY, coreRadius, 0, Math.PI * 2);
    this.ctx.fillStyle = coreGradient;
    this.ctx.fill();
    
    // === PRIMARY HIGHLIGHT (top-left shine) ===
    const highlightX = this.centerX - radius * 0.35;
    const highlightY = this.centerY - radius * 0.35;
    const highlightRadius = radius * 0.35;
    
    const highlightGradient = this.ctx.createRadialGradient(
      highlightX, highlightY, 0,
      highlightX, highlightY, highlightRadius
    );
    
    highlightGradient.addColorStop(0, 'rgba(255, 255, 255, 0.9)');
    highlightGradient.addColorStop(0.3, 'rgba(255, 255, 255, 0.4)');
    highlightGradient.addColorStop(0.6, 'rgba(255, 255, 255, 0.1)');
    highlightGradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
    
    this.ctx.beginPath();
    this.ctx.arc(highlightX, highlightY, highlightRadius, 0, Math.PI * 2);
    this.ctx.fillStyle = highlightGradient;
    this.ctx.fill();
    
    // === SECONDARY HIGHLIGHT (smaller, sharper) ===
    const shine2X = this.centerX - radius * 0.45;
    const shine2Y = this.centerY - radius * 0.45;
    const shine2Radius = radius * 0.12;
    
    const shine2Gradient = this.ctx.createRadialGradient(
      shine2X, shine2Y, 0,
      shine2X, shine2Y, shine2Radius
    );
    
    shine2Gradient.addColorStop(0, 'rgba(255, 255, 255, 0.95)');
    shine2Gradient.addColorStop(0.5, 'rgba(255, 255, 255, 0.3)');
    shine2Gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
    
    this.ctx.beginPath();
    this.ctx.arc(shine2X, shine2Y, shine2Radius, 0, Math.PI * 2);
    this.ctx.fillStyle = shine2Gradient;
    this.ctx.fill();
    
    // === FRESNEL EDGE (bright rim on dark side for glass effect) ===
    this.ctx.save();
    this.ctx.beginPath();
    this.ctx.arc(this.centerX, this.centerY, radius, 0, Math.PI * 2);
    this.ctx.clip();
    
    const fresnelGradient = this.ctx.createRadialGradient(
      this.centerX, this.centerY, radius * 0.7,
      this.centerX, this.centerY, radius
    );
    fresnelGradient.addColorStop(0, 'rgba(0, 0, 0, 0)');
    fresnelGradient.addColorStop(0.8, `hsla(${hue}, 80%, 80%, 0.1)`);
    fresnelGradient.addColorStop(1, `hsla(${hue - 20}, 90%, 90%, ${0.2 + this.currentAmplitude * 0.15})`);
    
    this.ctx.fillStyle = fresnelGradient;
    this.ctx.fillRect(this.centerX - radius, this.centerY - radius, radius * 2, radius * 2);
    this.ctx.restore();
  }
  
  /**
   * Draw ambient glow behind particles
   * AUDIO DRIVES VISUAL: glow intensity based on amplitude
   * Uses circular fill to avoid square edges
   */
  drawGlow() {
    const glowIntensity = this.settings.glowIntensity + this.currentAmplitude * 0.4;
    const glowRadius = this.settings.glowRadius * (1 + this.currentAmplitude * 0.3);
    
    // Create radial gradient for glow - fades to fully transparent
    const gradient = this.ctx.createRadialGradient(
      this.centerX, this.centerY, 0,
      this.centerX, this.centerY, glowRadius
    );
    
    // Color shifts with amplitude
    const hue = this.settings.baseHue + this.currentAmplitude * 20;
    
    // Glow fades completely to transparent - NO SQUARE EDGES
    gradient.addColorStop(0, `hsla(${hue}, ${this.settings.saturation}%, 80%, ${glowIntensity * 0.5})`);
    gradient.addColorStop(0.3, `hsla(${hue}, ${this.settings.saturation}%, ${this.settings.lightness}%, ${glowIntensity * 0.3})`);
    gradient.addColorStop(0.6, `hsla(${hue + 10}, ${this.settings.saturation}%, ${this.settings.lightness}%, ${glowIntensity * 0.1})`);
    gradient.addColorStop(0.85, `hsla(${hue + 20}, ${this.settings.saturation}%, ${this.settings.lightness}%, 0.02)`);
    gradient.addColorStop(1, 'rgba(0, 0, 0, 0)'); // Fully transparent at edge
    
    // Draw as circle, not rectangle - prevents square edges
    this.ctx.beginPath();
    this.ctx.arc(this.centerX, this.centerY, glowRadius, 0, Math.PI * 2);
    this.ctx.fillStyle = gradient;
    this.ctx.fill();
  }
  
  /**
   * Update particle positions
   * AUDIO DRIVES VISUAL: amplitude affects radius, turbulence, speed
   */
  updateParticles() {
    const speed = this.isSpeaking ? this.settings.speakingSpeed : this.settings.idleSpeed;
    const turbulence = this.settings.turbulence * (1 + this.currentAmplitude * 2);
    
    // AUDIO DRIVES VISUAL: Sphere expands/contracts with speech
    const radiusMultiplier = 1 + this.currentAmplitude * 0.22;
    
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
      
      // AUDIO DRIVES VISUAL: Smooth, gentle turbulence
      const turbX = Math.sin(this.time * 1.5 + p.phaseOffset) * turbulence;
      const turbY = Math.cos(this.time * 1.3 + p.phaseOffset * 1.3) * turbulence;
      const turbZ = Math.sin(this.time * 1.2 + p.phaseOffset * 0.7) * turbulence;
      
      // Final position - gentler movement for cleaner look
      p.x = this.centerX + (rotatedX * radius) + turbX * this.currentAmplitude * 12;
      p.y = this.centerY + (p.baseY * radius) + turbY * this.currentAmplitude * 12;
      p.z = rotatedZ; // Used for depth sorting and size
      
      // AUDIO DRIVES VISUAL: Size pulses with speech
      p.currentSize = p.size * (1 + this.currentAmplitude * 0.45);
      
      // AUDIO DRIVES VISUAL: Alpha increases when speaking
      p.currentAlpha = p.alpha * (0.7 + this.currentAmplitude * 0.5);
    }
    
    // Sort by Z for proper depth rendering (back to front)
    this.particles.sort((a, b) => a.z - b.z);
  }
  
  /**
   * Draw a single particle
   */
  drawParticle(p, isBehind = false) {
    // Depth-based size and alpha (closer = larger, more opaque)
    const depthFactor = (p.z + 1) / 2; // 0 to 1
    let size = p.currentSize * (0.5 + depthFactor * 0.5);
    let alpha = p.currentAlpha * (0.4 + depthFactor * 0.6);
    
    // Particles behind the orb are dimmer and slightly smaller
    if (isBehind) {
      alpha *= 0.5;  // Much dimmer behind
      size *= 0.85;  // Slightly smaller
    }
    
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
    
    // Add bright center point for closest particles (only in front)
    if (!isBehind && depthFactor > 0.7) {
      this.ctx.beginPath();
      this.ctx.arc(p.x, p.y, size * 0.3, 0, Math.PI * 2);
      this.ctx.fillStyle = `hsla(${hue}, ${saturation}%, 90%, ${alpha * 0.6})`;
      this.ctx.fill();
    }
  }
  
  /**
   * Draw particles that are BEHIND the orb (z < 0)
   */
  drawParticlesBehind() {
    // Sort by Z so furthest back are drawn first
    const behindParticles = this.particles.filter(p => p.z < 0).sort((a, b) => a.z - b.z);
    
    for (const p of behindParticles) {
      this.drawParticle(p, true);
    }
  }
  
  /**
   * Draw particles that are IN FRONT of the orb (z >= 0)
   */
  drawParticlesInFront() {
    // Sort by Z so closest are drawn last (on top)
    const frontParticles = this.particles.filter(p => p.z >= 0).sort((a, b) => a.z - b.z);
    
    for (const p of frontParticles) {
      this.drawParticle(p, false);
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

