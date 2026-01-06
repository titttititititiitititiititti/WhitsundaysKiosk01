/**
 * AI Speaking Orb - Audio-Reactive Visualizer
 * 
 * Premium geometric orb that reacts to ElevenLabs speech audio
 * Uses Three.js for WebGL rendering with bloom postprocessing
 */

class AIOrb {
  constructor(containerId = 'ai-orb-container') {
    this.container = document.getElementById(containerId);
    if (!this.container) {
      console.warn('Orb container not found:', containerId);
      return;
    }
    
    // Core Three.js components
    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.orb = null;
    this.particles = [];
    this.composer = null;
    
    // Audio analysis
    this.audioContext = null;
    this.analyser = null;
    this.audioSource = null;
    this.dataArray = null;
    this.isAudioConnected = false;
    
    // Animation state
    this.isSpeaking = false;
    this.currentAmplitude = 0;
    this.targetAmplitude = 0;
    this.baseScale = 1;
    this.clock = new THREE.Clock();
    this.animationId = null;
    
    // Settings - BRIGHT and VISIBLE
    this.settings = {
      orbColor: 0xa78bfa,        // Bright purple
      orbEmissive: 0x8b5cf6,     // Strong purple glow
      glowColor: 0x60a5fa,       // Bright blue accent
      idleRotationSpeed: 0.3,
      breathingSpeed: 0.6,
      breathingAmount: 0.05,
      amplitudeSmoothing: 0.2,
      maxScale: 1.4,             // More dramatic scaling
      particleCount: 12
    };
    
    this.init();
  }
  
  init() {
    this.setupScene();
    this.createOrb();
    this.setupLighting();
    this.setupPostProcessing();
    this.setupParticles();
    this.animate();
    
    // Handle resize
    window.addEventListener('resize', () => this.onResize());
    
    console.log('🔮 AI Orb initialized');
  }
  
  setupScene() {
    const width = this.container.clientWidth || 320;
    const height = this.container.clientHeight || 320;
    
    // Scene
    this.scene = new THREE.Scene();
    
    // Camera
    this.camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    this.camera.position.z = 5;
    
    // Renderer with transparency
    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance'
    });
    
    // Cap pixel ratio for performance
    const maxPixelRatio = Math.min(window.devicePixelRatio, 2);
    this.renderer.setPixelRatio(maxPixelRatio);
    this.renderer.setSize(width, height);
    this.renderer.setClearColor(0x000000, 0);
    
    // Get or create canvas
    let canvas = this.container.querySelector('#orb-canvas');
    if (canvas) {
      this.container.removeChild(canvas);
    }
    this.renderer.domElement.id = 'orb-canvas';
    this.container.appendChild(this.renderer.domElement);
  }
  
  createOrb() {
    // Create sphere geometry with decent detail for smoothness
    const geometry = new THREE.IcosahedronGeometry(1.2, 4);
    
    // Store original vertex positions for displacement
    this.originalPositions = geometry.attributes.position.array.slice();
    
    // Material with STRONG emissive glow - very visible
    const material = new THREE.MeshStandardMaterial({
      color: this.settings.orbColor,
      emissive: this.settings.orbEmissive,
      emissiveIntensity: 0.8,  // Much brighter!
      metalness: 0.2,
      roughness: 0.3,
      transparent: true,
      opacity: 1.0
    });
    
    this.orb = new THREE.Mesh(geometry, material);
    this.scene.add(this.orb);
    
    // Inner core glow - brighter
    const coreGeometry = new THREE.IcosahedronGeometry(0.9, 3);
    const coreMaterial = new THREE.MeshBasicMaterial({
      color: 0xffffff,  // White hot core
      transparent: true,
      opacity: 0.4
    });
    this.core = new THREE.Mesh(coreGeometry, coreMaterial);
    this.orb.add(this.core);
    
    // Outer glow shell
    const glowGeometry = new THREE.IcosahedronGeometry(1.4, 3);
    const glowMaterial = new THREE.MeshBasicMaterial({
      color: this.settings.orbColor,
      transparent: true,
      opacity: 0.15,
      side: THREE.BackSide
    });
    this.glowShell = new THREE.Mesh(glowGeometry, glowMaterial);
    this.orb.add(this.glowShell);
  }
  
  setupLighting() {
    // Strong ambient light for high visibility
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
    this.scene.add(ambientLight);
    
    // Main directional light - bright
    const mainLight = new THREE.DirectionalLight(0xffffff, 1.2);
    mainLight.position.set(2, 3, 4);
    this.scene.add(mainLight);
    
    // Fill light from below
    const fillLight = new THREE.DirectionalLight(0xffffff, 0.6);
    fillLight.position.set(-2, -2, 2);
    this.scene.add(fillLight);
    
    // Accent light (purple tint) - brighter
    const accentLight = new THREE.PointLight(0xa78bfa, 1.5, 15);
    accentLight.position.set(-2, -1, 3);
    this.scene.add(accentLight);
    
    // Blue rim light - brighter
    const rimLight = new THREE.PointLight(0x60a5fa, 1.0, 12);
    rimLight.position.set(0, 2, -3);
    this.scene.add(rimLight);
    
    // Front purple light
    const frontLight = new THREE.PointLight(0xc4b5fd, 1.0, 10);
    frontLight.position.set(0, 0, 5);
    this.scene.add(frontLight);
  }
  
  setupPostProcessing() {
    // Check if postprocessing is available
    if (typeof THREE.EffectComposer === 'undefined') {
      console.log('Postprocessing not available, using basic rendering');
      return;
    }
    
    const width = this.container.clientWidth || 320;
    const height = this.container.clientHeight || 320;
    
    // Effect composer
    this.composer = new THREE.EffectComposer(this.renderer);
    
    // Render pass
    const renderPass = new THREE.RenderPass(this.scene, this.camera);
    this.composer.addPass(renderPass);
    
    // Bloom pass for glow effect
    if (typeof THREE.UnrealBloomPass !== 'undefined') {
      this.bloomPass = new THREE.UnrealBloomPass(
        new THREE.Vector2(width, height),
        0.8,  // strength
        0.4,  // radius
        0.85  // threshold
      );
      this.composer.addPass(this.bloomPass);
    }
  }
  
  setupParticles() {
    // CSS particles are handled in orb.css
    // This creates Three.js particles for additional depth
    const particleGeometry = new THREE.BufferGeometry();
    const particleCount = 50;
    const positions = new Float32Array(particleCount * 3);
    const sizes = new Float32Array(particleCount);
    
    for (let i = 0; i < particleCount; i++) {
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      const radius = 1.8 + Math.random() * 0.5;
      
      positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = radius * Math.cos(phi);
      
      sizes[i] = Math.random() * 0.03 + 0.01;
    }
    
    particleGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    particleGeometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));
    
    // Store original particle positions
    this.originalParticlePositions = positions.slice();
    
    const particleMaterial = new THREE.PointsMaterial({
      color: this.settings.orbColor,
      size: 0.04,
      transparent: true,
      opacity: 0.6,
      blending: THREE.AdditiveBlending,
      sizeAttenuation: true
    });
    
    this.particleSystem = new THREE.Points(particleGeometry, particleMaterial);
    this.scene.add(this.particleSystem);
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
    
    // Store reference to audio element
    this.audioElement = audioElement;
    
    try {
      // Create audio context if needed
      if (!this.audioContext) {
        this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        console.log('🔊 Created new AudioContext');
      }
      
      // Resume context if suspended (required by browsers)
      if (this.audioContext.state === 'suspended') {
        this.audioContext.resume().then(() => {
          console.log('🔊 AudioContext resumed');
        });
      }
      
      // Create analyser if needed
      if (!this.analyser) {
        this.analyser = this.audioContext.createAnalyser();
        this.analyser.fftSize = 256;
        this.analyser.smoothingTimeConstant = 0.7;
        this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);
        console.log('🔊 Created analyser node');
      }
      
      // Check if this audio element already has a source
      if (audioElement._orbSourceNode) {
        console.log('🔊 Audio element already connected, reusing');
        this.audioSource = audioElement._orbSourceNode;
        this.isAudioConnected = true;
        return;
      }
      
      // Create and connect new source
      this.audioSource = this.audioContext.createMediaElementSource(audioElement);
      audioElement._orbSourceNode = this.audioSource; // Store reference to avoid re-creating
      
      this.audioSource.connect(this.analyser);
      this.analyser.connect(this.audioContext.destination);
      
      this.isAudioConnected = true;
      console.log('🔊 Audio connected to orb visualizer successfully');
      
    } catch (error) {
      console.error('Error connecting audio:', error);
      // If error is about already connected source, that's okay
      if (error.message && error.message.includes('already connected')) {
        this.isAudioConnected = true;
        console.log('🔊 Audio was already connected');
      }
    }
  }
  
  /**
   * Start speaking animation - orb will pulse dramatically
   */
  startSpeaking() {
    console.log('🔮 START SPEAKING - Orb activating!');
    console.log('🔮 this:', this);
    console.log('🔮 this === window.aiOrb:', this === window.aiOrb);
    console.log('🔮 Before: isSpeaking =', this.isSpeaking);
    
    this.isSpeaking = true;
    this.targetAmplitude = 0.5; // Start with strong amplitude
    this.currentAmplitude = 0.3; // Immediate visual feedback
    
    console.log('🔮 After: isSpeaking =', this.isSpeaking);
    
    this.updateUIState(true);
    
    // Resume audio context if needed
    if (this.audioContext && this.audioContext.state === 'suspended') {
      this.audioContext.resume();
    }
  }
  
  /**
   * Stop speaking animation - return to gentle breathing
   */
  stopSpeaking() {
    console.log('🔮 STOP SPEAKING - Orb returning to idle');
    this.isSpeaking = false;
    this.targetAmplitude = 0;
    // Smooth transition back to idle (don't instantly set to 0)
    this.updateUIState(false);
  }
  
  /**
   * Update CSS elements for speaking state
   */
  updateUIState(speaking) {
    console.log('🔮 updateUIState:', speaking, 'container:', this.container);
    
    if (!this.container) {
      console.warn('⚠️ No container for UI state update');
      return;
    }
    
    const glowRing = this.container.querySelector('.orb-glow-ring');
    const particles = this.container.querySelectorAll('.orb-particle');
    const status = this.container.querySelector('.orb-status');
    const debugIndicator = this.container.querySelector('#orb-debug');
    
    console.log('🔮 Found elements - glowRing:', !!glowRing, 'particles:', particles.length, 'debug:', !!debugIndicator);
    
    if (glowRing) {
      glowRing.classList.toggle('speaking', speaking);
      console.log('🔮 Glow ring speaking class:', glowRing.classList.contains('speaking'));
    }
    
    particles.forEach(p => p.classList.toggle('speaking', speaking));
    
    if (status) {
      status.classList.toggle('visible', speaking);
    }
    
    // DEBUG: Show/hide speaking indicator
    if (debugIndicator) {
      debugIndicator.style.opacity = speaking ? '1' : '0';
    }
  }
  
  /**
   * Calculate amplitude - uses audio if available, otherwise simulates speech pattern
   */
  getAmplitude() {
    // DEBUG: Force speaking mode for testing
    // Remove this line once working!
    // this.isSpeaking = true;
    
    // If not speaking, return 0 (just breathing animation)
    if (!this.isSpeaking) {
      return 0;
    }
    
    const time = this.clock.getElapsedTime();
    
    // Try to get real audio data if connected
    if (this.isAudioConnected && this.analyser && this.audioContext) {
      try {
        // Resume audio context if needed
        if (this.audioContext.state === 'suspended') {
          this.audioContext.resume();
        }
        
        this.analyser.getByteFrequencyData(this.dataArray);
        
        // Calculate RMS with emphasis on voice frequencies
        let sum = 0;
        let count = 0;
        for (let i = 2; i < Math.min(40, this.dataArray.length); i++) {
          sum += this.dataArray[i] * this.dataArray[i];
          count++;
        }
        const rms = Math.sqrt(sum / count) / 255;
        
        // If we got real audio data, use it (boosted)
        if (rms > 0.02) {
          return Math.min(1, rms * 3.0);
        }
      } catch (e) {
        // Fall through to simulated
      }
    }
    
    // SIMULATED SPEECH PATTERN - always works when speaking
    // Create a natural-feeling speech rhythm with multiple waves
    const wave1 = Math.sin(time * 6) * 0.2;           // Fast pulse
    const wave2 = Math.sin(time * 2.5) * 0.15;        // Medium rhythm
    const wave3 = Math.sin(time * 0.8) * 0.1;         // Slow variation
    const noise = Math.random() * 0.1;                // Random variation
    
    // Combine for natural speech feel (0.2 to 0.75 range)
    const simulated = 0.4 + wave1 + wave2 + wave3 + noise;
    return Math.max(0.15, Math.min(0.85, simulated));
  }
  
  /**
   * Apply surface displacement based on amplitude
   */
  applyDisplacement(amplitude) {
    if (!this.orb || !this.originalPositions) return;
    
    const positions = this.orb.geometry.attributes.position.array;
    const time = this.clock.getElapsedTime();
    
    for (let i = 0; i < positions.length; i += 3) {
      const ox = this.originalPositions[i];
      const oy = this.originalPositions[i + 1];
      const oz = this.originalPositions[i + 2];
      
      // Calculate displacement using noise-like function
      const noiseScale = 0.3;
      const noise = Math.sin(ox * 3 + time * 2) * 
                    Math.cos(oy * 3 + time * 1.5) * 
                    Math.sin(oz * 3 + time);
      
      const displacement = noise * amplitude * noiseScale;
      
      // Apply displacement along normal (radial direction)
      const length = Math.sqrt(ox * ox + oy * oy + oz * oz);
      const nx = ox / length;
      const ny = oy / length;
      const nz = oz / length;
      
      positions[i] = ox + nx * displacement;
      positions[i + 1] = oy + ny * displacement;
      positions[i + 2] = oz + nz * displacement;
    }
    
    this.orb.geometry.attributes.position.needsUpdate = true;
  }
  
  /**
   * Update particles based on amplitude
   */
  updateParticles(amplitude) {
    if (!this.particleSystem || !this.originalParticlePositions) return;
    
    const positions = this.particleSystem.geometry.attributes.position.array;
    const time = this.clock.getElapsedTime();
    
    // Contract/expand particle halo based on speech
    const radiusMultiplier = 1 - (amplitude * 0.3); // Tighten during speech
    
    for (let i = 0; i < positions.length; i += 3) {
      const ox = this.originalParticlePositions[i];
      const oy = this.originalParticlePositions[i + 1];
      const oz = this.originalParticlePositions[i + 2];
      
      // Apply radius change
      positions[i] = ox * radiusMultiplier;
      positions[i + 1] = oy * radiusMultiplier;
      positions[i + 2] = oz * radiusMultiplier;
      
      // Add subtle orbit
      const angle = time * 0.2 + i * 0.1;
      positions[i] += Math.sin(angle) * 0.05;
      positions[i + 1] += Math.cos(angle) * 0.05;
    }
    
    this.particleSystem.geometry.attributes.position.needsUpdate = true;
    
    // Update particle opacity
    this.particleSystem.material.opacity = 0.4 + amplitude * 0.6;
  }
  
  animate() {
    this.animationId = requestAnimationFrame(() => this.animate());
    
    const time = this.clock.getElapsedTime();
    const delta = this.clock.getDelta();
    
    // DEBUG: Log speaking state every 2 seconds
    if (Math.floor(time) % 2 === 0 && Math.floor(time) !== this._lastLogTime) {
      this._lastLogTime = Math.floor(time);
      console.log('🔮 Animation tick - isSpeaking:', this.isSpeaking, 'amplitude:', this.currentAmplitude.toFixed(2));
    }
    
    // Get audio amplitude (real or simulated)
    const rawAmplitude = this.getAmplitude();
    
    // Smooth amplitude changes - faster when speaking for responsiveness
    const smoothing = this.isSpeaking ? 0.3 : 0.1;
    this.targetAmplitude = rawAmplitude;
    this.currentAmplitude += (this.targetAmplitude - this.currentAmplitude) * smoothing;
    
    // Idle breathing animation - more pronounced
    const breathing = Math.sin(time * this.settings.breathingSpeed) * this.settings.breathingAmount;
    const secondaryBreath = Math.sin(time * 0.8) * 0.02;
    
    // Calculate scale based on amplitude + breathing
    // When speaking, scale varies from 1.0 to 1.5 based on amplitude
    const speakingScale = this.isSpeaking ? (1.0 + this.currentAmplitude * 0.5) : 1.0;
    const finalScale = (this.baseScale + breathing + secondaryBreath) * speakingScale;
    
    // DEBUG: Log when speaking with significant amplitude
    if (this.isSpeaking && this.currentAmplitude > 0.2) {
      console.log('🔮 SPEAKING - amplitude:', this.currentAmplitude.toFixed(2), 'scale:', finalScale.toFixed(2));
    }
    
    if (this.orb) {
      // Apply scale with smooth transition
      this.orb.scale.setScalar(finalScale);
      
      // More dynamic rotation when speaking
      const rotationSpeed = this.isSpeaking ? 0.03 : 0.01;
      this.orb.rotation.y += this.settings.idleRotationSpeed * rotationSpeed;
      this.orb.rotation.x = Math.sin(time * 0.3) * 0.15;
      this.orb.rotation.z = Math.cos(time * 0.25) * 0.05;
      
      // Update emissive intensity based on amplitude - MUCH stronger
      const emissiveIntensity = 0.6 + this.currentAmplitude * 1.2;
      this.orb.material.emissiveIntensity = Math.min(2.0, emissiveIntensity);
      
      // Change color slightly when speaking
      if (this.isSpeaking && this.currentAmplitude > 0.1) {
        // Shift towards brighter purple/white when loud
        const colorShift = this.currentAmplitude * 0.3;
        this.orb.material.color.setRGB(
          0.65 + colorShift,
          0.55 + colorShift * 0.5,
          0.98
        );
      } else {
        this.orb.material.color.setHex(this.settings.orbColor);
      }
      
      // Apply surface displacement
      if (this.isSpeaking) {
        this.applyDisplacement(this.currentAmplitude);
      }
    }
    
    // Update core glow - much more reactive
    if (this.core) {
      const coreOpacity = this.isSpeaking ? (0.3 + this.currentAmplitude * 0.5) : 0.25;
      this.core.material.opacity = coreOpacity;
      this.core.scale.setScalar(0.9 + this.currentAmplitude * 0.15);
      // Pulse the core
      this.core.rotation.y -= 0.02;
    }
    
    // Update outer glow shell
    if (this.glowShell) {
      const glowOpacity = this.isSpeaking ? (0.1 + this.currentAmplitude * 0.25) : 0.08;
      this.glowShell.material.opacity = glowOpacity;
      this.glowShell.scale.setScalar(1 + this.currentAmplitude * 0.2);
    }
    
    // Update particles
    this.updateParticles(this.currentAmplitude);
    
    // Rotate particle system - faster when speaking
    if (this.particleSystem) {
      const particleSpeed = this.isSpeaking ? 0.005 : 0.001;
      this.particleSystem.rotation.y += particleSpeed;
      this.particleSystem.rotation.x = Math.sin(time * 0.2) * 0.1;
    }
    
    // Update bloom intensity based on speech
    if (this.bloomPass) {
      this.bloomPass.strength = 0.8 + this.currentAmplitude * 1.0;
    }
    
    // Render
    if (this.composer) {
      this.composer.render();
    } else {
      this.renderer.render(this.scene, this.camera);
    }
  }
  
  onResize() {
    const width = this.container.clientWidth || 320;
    const height = this.container.clientHeight || 320;
    
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    
    this.renderer.setSize(width, height);
    
    if (this.composer) {
      this.composer.setSize(width, height);
    }
  }
  
  show() {
    if (this.container) {
      this.container.classList.remove('hidden');
      console.log('🔮 Orb shown');
    }
  }
  
  hide() {
    if (this.container) {
      this.container.classList.add('hidden');
      console.log('🔮 Orb hidden');
    }
  }
  
  toggle() {
    if (this.container.classList.contains('hidden')) {
      this.show();
    } else {
      this.hide();
    }
  }
  
  destroy() {
    if (this.animationId) {
      cancelAnimationFrame(this.animationId);
    }
    
    if (this.audioSource) {
      this.audioSource.disconnect();
    }
    
    if (this.audioContext) {
      this.audioContext.close();
    }
    
    if (this.renderer) {
      this.renderer.dispose();
    }
    
    window.removeEventListener('resize', this.onResize);
  }
}

// Global instance
let aiOrb = null;

/**
 * Initialize the AI Orb visualizer
 */
function initAIOrb() {
  const container = document.getElementById('ai-orb-container');
  if (!container) {
    console.log('🔮 Orb container not found, will init when available');
    return null;
  }
  
  // If already initialized, just return existing instance
  if (aiOrb && aiOrb.renderer) {
    console.log('🔮 AI Orb already initialized, returning existing');
    container.classList.remove('hidden');
    return aiOrb;
  }
  
  console.log('🔮 Creating new AI Orb instance...');
  
  try {
    aiOrb = new AIOrb('ai-orb-container');
    window.aiOrb = aiOrb;
    
    // Make sure container is visible
    container.classList.remove('hidden');
    
    console.log('🔮 AI Orb initialized successfully');
    return aiOrb;
  } catch (error) {
    console.error('🔮 Error initializing orb:', error);
    return null;
  }
}

/**
 * Connect ElevenLabs audio to the orb
 * Call this when setting up the audio element
 */
function connectOrbToAudio(audioElement) {
  if (!aiOrb) {
    aiOrb = initAIOrb();
  }
  
  if (aiOrb && audioElement) {
    aiOrb.connectAudio(audioElement);
  }
}

/**
 * Notify orb that speech is starting
 */
function orbStartSpeaking() {
  if (aiOrb) {
    aiOrb.startSpeaking();
  }
}

/**
 * Notify orb that speech has ended
 */
function orbStopSpeaking() {
  if (aiOrb) {
    aiOrb.stopSpeaking();
  }
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initAIOrb);
} else {
  // Delay slightly to ensure container is in DOM
  setTimeout(initAIOrb, 100);
}

// Export for use in other modules
window.AIOrb = AIOrb;
window.initAIOrb = initAIOrb;
window.connectOrbToAudio = connectOrbToAudio;
window.orbStartSpeaking = orbStartSpeaking;
window.orbStopSpeaking = orbStopSpeaking;

// DEBUG: Test function - call from browser console: testOrb()
window.testOrb = function() {
  console.log('🧪 Testing orb...');
  console.log('🧪 window.aiOrb:', window.aiOrb);
  
  if (window.aiOrb) {
    console.log('🧪 Current isSpeaking:', window.aiOrb.isSpeaking);
    console.log('🧪 Current amplitude:', window.aiOrb.currentAmplitude);
    console.log('🧪 Calling startSpeaking...');
    window.aiOrb.startSpeaking();
    console.log('🧪 After startSpeaking - isSpeaking:', window.aiOrb.isSpeaking);
    
    // Auto-stop after 5 seconds
    setTimeout(() => {
      console.log('🧪 Auto-stopping after 5 seconds');
      window.aiOrb.stopSpeaking();
    }, 5000);
  } else {
    console.log('🧪 No orb instance found! Try calling initAIOrb() first');
  }
};

