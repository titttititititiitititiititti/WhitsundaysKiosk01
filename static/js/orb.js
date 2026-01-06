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
    // Ambient light for base visibility
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
    this.scene.add(ambientLight);
    
    // Main directional light
    const mainLight = new THREE.DirectionalLight(0xffffff, 0.8);
    mainLight.position.set(2, 3, 4);
    this.scene.add(mainLight);
    
    // Accent light (purple tint)
    const accentLight = new THREE.PointLight(this.settings.orbColor, 0.6, 10);
    accentLight.position.set(-2, -1, 3);
    this.scene.add(accentLight);
    
    // Blue rim light
    const rimLight = new THREE.PointLight(this.settings.glowColor, 0.4, 8);
    rimLight.position.set(0, 2, -3);
    this.scene.add(rimLight);
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
   * Start speaking animation
   */
  startSpeaking() {
    this.isSpeaking = true;
    this.targetAmplitude = 0.3; // Start with some amplitude for immediate feedback
    this.updateUIState(true);
    
    // Resume audio context if needed
    if (this.audioContext && this.audioContext.state === 'suspended') {
      this.audioContext.resume();
    }
    
    console.log('🔮 Orb speaking...');
  }
  
  /**
   * Stop speaking animation
   */
  stopSpeaking() {
    this.isSpeaking = false;
    this.targetAmplitude = 0;
    this.currentAmplitude = 0;
    this.updateUIState(false);
    console.log('🔮 Orb idle');
  }
  
  /**
   * Update CSS elements for speaking state
   */
  updateUIState(speaking) {
    const glowRing = this.container.querySelector('.orb-glow-ring');
    const particles = this.container.querySelectorAll('.orb-particle');
    const status = this.container.querySelector('.orb-status');
    
    if (glowRing) {
      glowRing.classList.toggle('speaking', speaking);
    }
    
    particles.forEach(p => p.classList.toggle('speaking', speaking));
    
    if (status) {
      status.classList.toggle('visible', speaking);
    }
  }
  
  /**
   * Calculate RMS amplitude from audio data
   */
  getAmplitude() {
    // If not speaking, return 0
    if (!this.isSpeaking) {
      return 0;
    }
    
    // If no analyser connected, return simulated amplitude for visual feedback
    if (!this.isAudioConnected || !this.analyser) {
      // Return simulated pulsing when speaking but no audio connected
      const time = this.clock.getElapsedTime();
      return 0.3 + Math.sin(time * 8) * 0.2;
    }
    
    try {
      // Resume audio context if needed
      if (this.audioContext && this.audioContext.state === 'suspended') {
        this.audioContext.resume();
      }
      
      this.analyser.getByteFrequencyData(this.dataArray);
      
      // Calculate RMS with emphasis on voice frequencies (85-255 Hz range, indices ~2-15)
      let sum = 0;
      let count = 0;
      for (let i = 2; i < Math.min(30, this.dataArray.length); i++) {
        sum += this.dataArray[i] * this.dataArray[i];
        count++;
      }
      const rms = Math.sqrt(sum / count) / 255;
      
      // Boost the signal for better visual response
      const boostedRms = Math.min(1, rms * 2.5);
      
      // If we're getting no data but supposed to be speaking, use simulated
      if (boostedRms < 0.01 && this.isSpeaking) {
        const time = this.clock.getElapsedTime();
        return 0.25 + Math.sin(time * 6) * 0.15;
      }
      
      return boostedRms;
    } catch (e) {
      console.warn('Error getting amplitude:', e);
      return 0;
    }
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
    
    // Get audio amplitude
    const rawAmplitude = this.getAmplitude();
    
    // Smooth amplitude changes
    this.targetAmplitude = rawAmplitude;
    this.currentAmplitude += (this.targetAmplitude - this.currentAmplitude) * this.settings.amplitudeSmoothing;
    
    // Idle breathing animation - more pronounced
    const breathing = Math.sin(time * this.settings.breathingSpeed) * this.settings.breathingAmount;
    const secondaryBreath = Math.sin(time * 0.8) * 0.02;
    
    // Calculate scale based on amplitude + breathing
    const amplitudeScale = 1 + (this.currentAmplitude * (this.settings.maxScale - 1));
    const finalScale = (this.baseScale + breathing + secondaryBreath) * (this.isSpeaking ? amplitudeScale : 1);
    
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

