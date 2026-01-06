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
    
    // Settings
    this.settings = {
      orbColor: 0x8b5cf6,        // Purple
      orbEmissive: 0x4c1d95,     // Dark purple glow
      glowColor: 0x3b82f6,       // Blue accent
      idleRotationSpeed: 0.2,
      breathingSpeed: 0.5,
      breathingAmount: 0.03,
      amplitudeSmoothing: 0.15,
      maxScale: 1.25,
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
    
    // Material with emissive glow
    const material = new THREE.MeshStandardMaterial({
      color: this.settings.orbColor,
      emissive: this.settings.orbEmissive,
      emissiveIntensity: 0.3,
      metalness: 0.3,
      roughness: 0.4,
      transparent: true,
      opacity: 0.95
    });
    
    this.orb = new THREE.Mesh(geometry, material);
    this.scene.add(this.orb);
    
    // Inner core glow
    const coreGeometry = new THREE.IcosahedronGeometry(0.8, 3);
    const coreMaterial = new THREE.MeshBasicMaterial({
      color: this.settings.glowColor,
      transparent: true,
      opacity: 0.15
    });
    this.core = new THREE.Mesh(coreGeometry, coreMaterial);
    this.orb.add(this.core);
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
    
    try {
      // Create audio context if needed
      if (!this.audioContext) {
        this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
      }
      
      // Resume context if suspended (required by browsers)
      if (this.audioContext.state === 'suspended') {
        this.audioContext.resume();
      }
      
      // Create analyser
      if (!this.analyser) {
        this.analyser = this.audioContext.createAnalyser();
        this.analyser.fftSize = 256;
        this.analyser.smoothingTimeConstant = 0.8;
        this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);
      }
      
      // Disconnect previous source if any
      if (this.audioSource) {
        try {
          this.audioSource.disconnect();
        } catch (e) {
          // Ignore disconnect errors
        }
      }
      
      // Create and connect new source
      this.audioSource = this.audioContext.createMediaElementSource(audioElement);
      this.audioSource.connect(this.analyser);
      this.analyser.connect(this.audioContext.destination);
      
      this.isAudioConnected = true;
      console.log('🔊 Audio connected to orb visualizer');
      
    } catch (error) {
      console.error('Error connecting audio:', error);
      // Audio might already be connected, that's okay
      this.isAudioConnected = true;
    }
  }
  
  /**
   * Start speaking animation
   */
  startSpeaking() {
    this.isSpeaking = true;
    this.updateUIState(true);
    console.log('🔮 Orb speaking...');
  }
  
  /**
   * Stop speaking animation
   */
  stopSpeaking() {
    this.isSpeaking = false;
    this.targetAmplitude = 0;
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
    if (!this.isAudioConnected || !this.analyser || !this.isSpeaking) {
      return 0;
    }
    
    this.analyser.getByteFrequencyData(this.dataArray);
    
    // Calculate RMS
    let sum = 0;
    for (let i = 0; i < this.dataArray.length; i++) {
      sum += this.dataArray[i] * this.dataArray[i];
    }
    const rms = Math.sqrt(sum / this.dataArray.length) / 255;
    
    return rms;
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
    
    // Idle breathing animation
    const breathing = Math.sin(time * this.settings.breathingSpeed) * this.settings.breathingAmount;
    
    // Calculate scale based on amplitude + breathing
    const amplitudeScale = 1 + (this.currentAmplitude * (this.settings.maxScale - 1));
    const finalScale = (this.baseScale + breathing) * (this.isSpeaking ? amplitudeScale : 1);
    
    if (this.orb) {
      // Apply scale
      this.orb.scale.setScalar(finalScale);
      
      // Idle rotation
      this.orb.rotation.y += this.settings.idleRotationSpeed * 0.01;
      this.orb.rotation.x = Math.sin(time * 0.3) * 0.1;
      
      // Update emissive intensity based on amplitude
      const emissiveIntensity = 0.3 + this.currentAmplitude * 0.7;
      this.orb.material.emissiveIntensity = emissiveIntensity;
      
      // Apply surface displacement
      if (this.isSpeaking) {
        this.applyDisplacement(this.currentAmplitude);
      }
    }
    
    // Update core glow
    if (this.core) {
      this.core.material.opacity = 0.1 + this.currentAmplitude * 0.3;
      this.core.scale.setScalar(0.95 + this.currentAmplitude * 0.1);
    }
    
    // Update particles
    this.updateParticles(this.currentAmplitude);
    
    // Rotate particle system slowly
    if (this.particleSystem) {
      this.particleSystem.rotation.y += 0.001;
      this.particleSystem.rotation.x = Math.sin(time * 0.2) * 0.1;
    }
    
    // Update bloom intensity based on speech
    if (this.bloomPass) {
      this.bloomPass.strength = 0.6 + this.currentAmplitude * 0.8;
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
    this.container.classList.add('visible');
    this.container.classList.remove('hidden');
  }
  
  hide() {
    this.container.classList.remove('visible');
    this.container.classList.add('hidden');
  }
  
  toggle() {
    if (this.container.classList.contains('visible')) {
      this.hide();
    } else {
      this.show();
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
  if (aiOrb) {
    console.log('AI Orb already initialized');
    return aiOrb;
  }
  
  const container = document.getElementById('ai-orb-container');
  if (!container) {
    console.log('Orb container not found, will init when available');
    return null;
  }
  
  aiOrb = new AIOrb('ai-orb-container');
  window.aiOrb = aiOrb;
  
  return aiOrb;
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

