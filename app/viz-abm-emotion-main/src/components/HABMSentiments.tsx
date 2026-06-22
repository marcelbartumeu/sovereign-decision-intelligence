import { useEffect, useRef, useCallback, useState } from 'react';
import { createPortal } from 'react-dom';
import styled from 'styled-components';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { useSharedState } from '../services/SharedStateContext';

const Container = styled.div`
  width: 100%;
  height: 100%;
  position: relative;
  background: #000;
  border-radius: 8px;
  overflow: hidden;
`;

const Title = styled.div`
  position: absolute;
  top: 8px;
  left: 10px;
  color: rgba(255,255,255,0.4);
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0;
  z-index: 10;
  background: rgba(0,0,0,0.7);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  padding: 3px 8px;
  border-radius: 999px;
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Inter', sans-serif;
  pointer-events: none;
`;

const CanvasContainer = styled.div`
  width: 100%;
  height: 100%;
  position: absolute;
  top: 0;
  left: 0;
`;

const LabelsOverlay = styled.div`
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  pointer-events: none;
  z-index: 1000;
`;

const EmotionLabel = styled.div`
  position: absolute;
  color: white;
  font-size: 11px;
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Inter', sans-serif;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  pointer-events: none;
  transform: translate(-50%, -50%);
`;

interface Emotions {
  ANGER: number;
  CONTEMPT: number;
  DISGUST: number;
  ENJOYMENT: number;
  FEAR: number;
  SADNESS: number;
  SURPRISE: number;
}

interface AgentData {
  agent_id: string;
  step: number;
  type: string;
  mood_vector: number[][];
}

interface HABMSentimentsProps {
  agents?: Array<{
    id: string;
    emotions: {
      insecure: number;
      energize: number;
      threaten: number;
      stress: number;
      calm: number;
    };
  }>;
}

// Ekman emotions index mapping
const EKMAN_EMOTIONS = [
  'ANGER',
  'CONTEMPT',
  'DISGUST',
  'ENJOYMENT', 
  'FEAR',
  'SADNESS',
  'SURPRISE'
] as const;

type EkmanEmotion = typeof EKMAN_EMOTIONS[number];

// Define emotion colors — must stay in sync with EKMAN_COLORS in AgentAnalyticsView.tsx
const emotionColors = {
  ANGER:    new THREE.Color('#FF453A'),  // sys-red
  CONTEMPT: new THREE.Color('#BF5AF2'),  // sys-purple
  DISGUST:  new THREE.Color('#FFD60A'),  // sys-yellow
  ENJOYMENT:new THREE.Color('#30D158'),  // sys-green
  FEAR:     new THREE.Color('#FF9F0A'),  // sys-orange
  SADNESS:  new THREE.Color('#0A84FF'),  // sys-blue
  SURPRISE: new THREE.Color('#64D2FF'),  // sys-teal
};

// Define cluster centers - fixed positions for stability
const clusterCenters = {
  ANGER: new THREE.Vector3(-8, 0, 0),
  CONTEMPT: new THREE.Vector3(-5, 5, 0),
  DISGUST: new THREE.Vector3(0, 8, 0),
  ENJOYMENT: new THREE.Vector3(5, 5, 0),
  FEAR: new THREE.Vector3(8, 0, 0),
  SADNESS: new THREE.Vector3(0, -8, 0),
  SURPRISE: new THREE.Vector3(0, 0, 8)
};

// Placeholder agents so all 7 emotion clusters populate when no live simulation
// mood data is present (frontend placeholder for visualisation).
const PLACEHOLDER_AGENTS = Array.from({ length: 350 }, (_, i) => {
  const dom = i % 7;
  const mood = Array.from({ length: 7 }, (_, j) => (j === dom ? 0.6 + Math.random() * 0.4 : Math.random() * 0.25));
  return { agent_id: `PH-${i}`, mood_vector: [mood] };
});

// Interface for tracking particle positions and movement
interface ParticleState {
  id: string | number;
  currentPos: THREE.Vector3;
  targetPos: THREE.Vector3;
  dominantEmotion: EkmanEmotion;
  velocity: THREE.Vector3;
  size: number;
  isTransitioning: boolean;
}

interface Label {
  id: string;
  position: { x: number, y: number };
  text: string;
  color: string;
}

function HABMSentiments({ agents = [] }: HABMSentimentsProps) {
  const { state } = useSharedState();
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasContainerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const particlesRef = useRef<THREE.Points | null>(null);
  const backgroundParticlesRef = useRef<THREE.Points | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const timeRef = useRef<number>(0);
  const lastUpdateTimeRef = useRef<number>(0);
  
  // Use state for labels instead of refs to trigger React rendering
  const [labels, setLabels] = useState<Label[]>([]);
  
  // Track particle states for smooth transitions
  const particleStatesRef = useRef<Map<string | number, ParticleState>>(new Map());
  
  // Additional particles per agent for a denser visualization
  const particlesPerAgent = 3;
  // Smoother movement: lower = smoother but slower
  const transitionSpeed = 0.01;
  const transitionSpeedDuringChange = 0.008;
  // Damping factor to create smooth deceleration (0-1, lower = more damping)
  const dampingFactor = 0.94;
  const dampingFactorDuringChange = 0.85;
  // Background particle count
  const backgroundParticleCount = 5000;

  // Get the dominant emotion for an agent's mood vector
  const getDominantEmotion = useCallback((moodVector: number[]): EkmanEmotion => {
    // Find the index of the max value in the mood vector
    const maxIndex = moodVector.reduce((maxIdx, value, idx, arr) => 
      value > arr[maxIdx] ? idx : maxIdx, 0);
    
    // Return the corresponding Ekman emotion
    return EKMAN_EMOTIONS[maxIndex];
  }, []);

  // Initialize the Three.js scene
  const initScene = useCallback(() => {
    if (!canvasContainerRef.current) return;

    // Create scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x000000);
    sceneRef.current = scene;

    // Add ambient light
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.2);
    scene.add(ambientLight);

    // Add directional light
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.5);
    directionalLight.position.set(1, 1, 1);
    scene.add(directionalLight);

    // Create camera
    const aspect = canvasContainerRef.current.clientWidth / canvasContainerRef.current.clientHeight;
    const camera = new THREE.PerspectiveCamera(60, aspect, 0.1, 1000);
    camera.position.set(0, 0, 20);
    cameraRef.current = camera;

    // Create renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(canvasContainerRef.current.clientWidth, canvasContainerRef.current.clientHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    canvasContainerRef.current.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Add orbit controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.rotateSpeed = 0.7;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.5;
    controlsRef.current = controls;

    // First clear any existing labels
    setLabels([]);
    
    // Track which emotions we've already processed to avoid duplicates
    const emotionsAdded = new Set<string>();

    // Create cluster centers visualization (small spheres)
    Object.entries(clusterCenters).forEach(([emotion, position]) => {
      // Skip if this emotion has already been processed
      if (emotionsAdded.has(emotion)) return;
      emotionsAdded.add(emotion);
      
      const geometry = new THREE.SphereGeometry(0.3, 16, 16);
      const material = new THREE.MeshBasicMaterial({ 
        color: emotionColors[emotion as keyof typeof emotionColors],
        transparent: true, 
        opacity: 0.7 
      });
      const sphere = new THREE.Mesh(geometry, material);
      sphere.position.copy(position);
      scene.add(sphere);
      
      // Add a glow effect to the cluster centers
      const glowGeometry = new THREE.SphereGeometry(1.5, 32, 32);
      const glowMaterial = new THREE.MeshBasicMaterial({
        color: emotionColors[emotion as keyof typeof emotionColors],
        transparent: true,
        opacity: 0.1,
        side: THREE.BackSide
      });
      const glow = new THREE.Mesh(glowGeometry, glowMaterial);
      glow.position.copy(position);
      scene.add(glow);
      
      // Initialize labels (now using React state) with a unique ID
      setLabels(prevLabels => [
        ...prevLabels,
        {
          id: `emotion-${emotion}`,
          position: { x: 0, y: 0 }, // Will be updated in updateLabelPositions
          text: emotion.charAt(0).toUpperCase() + emotion.slice(1),
          color: `#${emotionColors[emotion as keyof typeof emotionColors].getHexString()}`
        }
      ]);
    });

    // Add ambient nebula effect
    createNebulaBackground();
    
    // Initialize agent particles
    initializeParticles();

    return () => {
      if (renderer && canvasContainerRef.current) {
        canvasContainerRef.current.removeChild(renderer.domElement);
      }
    };
  }, []);

  // Create a nebula-like background with more particles
  const createNebulaBackground = useCallback(() => {
    if (!sceneRef.current) return;

    const particleCount = backgroundParticleCount;
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);
    const sizes = new Float32Array(particleCount);

    // Create particles distributed throughout the scene
    for (let i = 0; i < particleCount; i++) {
      const i3 = i * 3;
      
      // Position particles in a large sphere
      const radius = 40 * Math.random();
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.random() * Math.PI;
      
      positions[i3] = radius * Math.sin(phi) * Math.cos(theta);
      positions[i3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
      positions[i3 + 2] = radius * Math.cos(phi);
      
      // Slightly colored background particles
      colors[i3] = 0.2 + Math.random() * 0.1;
      colors[i3 + 1] = 0.2 + Math.random() * 0.1;
      colors[i3 + 2] = 0.3 + Math.random() * 0.2;
      
      // Vary the size
      sizes[i] = 0.05 + Math.random() * 0.15;
    }
    
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));
    
    const material = new THREE.PointsMaterial({
      size: 0.1,
      vertexColors: true,
      transparent: true,
      opacity: 0.3,
      blending: THREE.AdditiveBlending,
      sizeAttenuation: true
    });
    
    const particles = new THREE.Points(geometry, material);
    sceneRef.current.add(particles);
    backgroundParticlesRef.current = particles;
  }, []);

  // Initialize particle system for agents
  const initializeParticles = useCallback(() => {
    if (!sceneRef.current) return;
    
    const geometry = new THREE.BufferGeometry();
    // We'll update these attributes in the animation loop
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array([]), 3));
    geometry.setAttribute('color', new THREE.Float32BufferAttribute(new Float32Array([]), 3));
    geometry.setAttribute('size', new THREE.Float32BufferAttribute(new Float32Array([]), 1));
    
    const material = new THREE.PointsMaterial({
      size: 0.5,
      vertexColors: true,
      transparent: true,
      opacity: 0.8,
      blending: THREE.AdditiveBlending,
      sizeAttenuation: true
    });
    
    const particles = new THREE.Points(geometry, material);
    sceneRef.current.add(particles);
    particlesRef.current = particles;
  }, []);

  // Generate a random position near a cluster center
  const getRandomPositionNearCluster = useCallback((center: THREE.Vector3, spread: number = 2) => {
    const radius = spread + Math.random() * spread;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.random() * Math.PI;
    
    return new THREE.Vector3(
      center.x + radius * Math.sin(phi) * Math.cos(theta),
      center.y + radius * Math.sin(phi) * Math.sin(theta),
      center.z + radius * Math.cos(phi)
    );
  }, []);

  // Update particle targets based on simulation data
  const updateParticleTargets = useCallback(() => {
    const simAgents = (state.simulationData?.agents && state.simulationData.agents.length)
      ? state.simulationData.agents
      : PLACEHOLDER_AGENTS;
    const step = (state as any).currentStep ?? 0;

    // Track which agent IDs we've processed
    const processedIds = new Set<string | number>();
    
    // Track how many agents are in each emotion cluster
    const clusterCounts: Record<EkmanEmotion, number> = {
      ANGER: 0,
      CONTEMPT: 0,
      DISGUST: 0,
      ENJOYMENT: 0,
      FEAR: 0,
      SADNESS: 0,
      SURPRISE: 0
    };
    
    let totalAgents = 0;
    
    // Update existing particles and create new ones as needed
    simAgents.forEach(agent => {
      // Get current mood vector based on the current step
      const currentStep = Math.min(step, agent.mood_vector.length - 1);
      const moodVector = agent.mood_vector[currentStep];
      
      if (!moodVector) return; // Skip if no mood data available
      
      totalAgents++;
      const dominantEmotion = getDominantEmotion(moodVector);
      clusterCounts[dominantEmotion]++;
      
      // Generate multiple particles per agent
      for (let i = 0; i < particlesPerAgent; i++) {
        const particleId = `${agent.agent_id}-${i}`;
        processedIds.add(particleId);
        
        const center = clusterCenters[dominantEmotion];
        const targetPos = getRandomPositionNearCluster(center);
        
        if (particleStatesRef.current.has(particleId)) {
          // Update existing particle
          const state = particleStatesRef.current.get(particleId)!;
          
          // If emotion changed, trigger transition
          if (state.dominantEmotion !== dominantEmotion) {
            state.targetPos = targetPos;
            state.dominantEmotion = dominantEmotion;
            state.isTransitioning = true;
            state.velocity.set(0, 0, 0);
          } else {
            // If emotion is the same, ensure it's not marked as transitioning
            if (state.isTransitioning) {
              // If it was transitioning but target hasn't changed, maybe stop?
            } else {
              // Optional: Re-enable minimal jitter if desired later
              // if (Math.random() < 0.01) { state.targetPos = targetPos; }
            }
          }
        } else {
          // Create new particle - start at target, not transitioning
          particleStatesRef.current.set(particleId, {
            id: particleId,
            currentPos: targetPos.clone(),
            targetPos: targetPos,
            dominantEmotion,
            velocity: new THREE.Vector3(0, 0, 0),
            size: 0.3 + Math.random() * 0.4,
            isTransitioning: false
          });
        }
      }
    });
    
    // Remove particles that no longer exist
    particleStatesRef.current.forEach((state, id) => {
      if (!processedIds.has(id)) {
        particleStatesRef.current.delete(id);
      }
    });
    
    // Update label texts with counts and percentages
    setLabels(prevLabels => 
      prevLabels.map(label => {
        // Extract the emotion name from the label ID (removing the 'emotion-' prefix)
        const emotionId = label.id.replace('emotion-', '') as EkmanEmotion;
        const count = clusterCounts[emotionId];
        const percentage = totalAgents > 0 ? Math.round((count / totalAgents) * 100) : 0;
        return {
          ...label,
          text: `${emotionId}: ${count} (${percentage}%)`
        };
      })
    );
  }, [state.simulationData, state.currentStep, getDominantEmotion, getRandomPositionNearCluster]);

  // Update particle system with current positions
  const updateParticlePositions = useCallback(() => {
    if (!sceneRef.current || !particlesRef.current) return;
    
    const particles = particleStatesRef.current;
    const particleCount = particles.size;
    
    if (particleCount === 0) return;
    
    const positions = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);
    const sizes = new Float32Array(particleCount);
    
    let index = 0;
    particles.forEach(particle => {
      const i3 = index * 3;
      
      // Only apply physics if transitioning
      if (particle.isTransitioning) {
        // Calculate direction to target
        const direction = new THREE.Vector3().subVectors(particle.targetPos, particle.currentPos);
        const distance = direction.length();
        
        // Use specific physics parameters during transition
        particle.velocity.add(direction.normalize().multiplyScalar(distance * transitionSpeedDuringChange));
        particle.velocity.multiplyScalar(dampingFactorDuringChange);
        
        // Update position
        particle.currentPos.add(particle.velocity);
        
        // Stop transitioning if close enough to target and velocity is low
        if (distance < 0.1 && particle.velocity.length() < 0.05) {
          particle.isTransitioning = false;
          particle.currentPos.copy(particle.targetPos);
          particle.velocity.set(0, 0, 0);
        }
      } else {
        // If not transitioning, keep position static (or apply minimal jitter here if desired)
        // Snapping to targetPos ensures particles don't drift slightly due to leftover velocity
        // particle.currentPos.copy(particle.targetPos); 
        // Keep current pos unless snapping becomes necessary
      }
      
      // Set position in buffer
      positions[i3] = particle.currentPos.x;
      positions[i3 + 1] = particle.currentPos.y;
      positions[i3 + 2] = particle.currentPos.z;
      
      // Set color based on dominant emotion
      const emotionColor = emotionColors[particle.dominantEmotion as keyof typeof emotionColors];
      colors[i3] = emotionColor.r;
      colors[i3 + 1] = emotionColor.g;
      colors[i3 + 2] = emotionColor.b;
      
      // Set particle size
      sizes[index] = particle.size;
      
      index++;
    });
    
    // Update geometry attributes
    particlesRef.current.geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    particlesRef.current.geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
    particlesRef.current.geometry.setAttribute('size', new THREE.Float32BufferAttribute(sizes, 1));
    
    // Mark attributes as needing update
    particlesRef.current.geometry.attributes.position.needsUpdate = true;
    particlesRef.current.geometry.attributes.color.needsUpdate = true;
    particlesRef.current.geometry.attributes.size.needsUpdate = true;
  }, []);

  // Animate background particles
  const animateBackgroundParticles = useCallback((time: number) => {
    if (!backgroundParticlesRef.current) return;
    
    const positions = backgroundParticlesRef.current.geometry.attributes.position.array as Float32Array;
    const count = positions.length / 3;
    
    for (let i = 0; i < count; i++) {
      const i3 = i * 3;
      const x = positions[i3];
      const y = positions[i3 + 1];
      const z = positions[i3 + 2];
      
      // Add subtle movement to background particles
      positions[i3] = x + Math.sin(time * 0.0005 + i * 0.1) * 0.01;
      positions[i3 + 1] = y + Math.cos(time * 0.0005 + i * 0.1) * 0.01;
      positions[i3 + 2] = z + Math.sin(time * 0.0005 + i * 0.05) * 0.01;
    }
    
    backgroundParticlesRef.current.geometry.attributes.position.needsUpdate = true;
  }, []);

  // Update label positions in 2D using React state
  const updateLabelPositions = useCallback(() => {
    if (!cameraRef.current || !containerRef.current) return;
    
    const camera = cameraRef.current;
    const container = containerRef.current;
    const rect = container.getBoundingClientRect();
    
    setLabels(prevLabels => 
      prevLabels.map(label => {
        // Extract the emotion name from the label ID (removing the 'emotion-' prefix)
        const emotionId = label.id.replace('emotion-', '');
        const position = clusterCenters[emotionId as keyof typeof clusterCenters];
        
        // Project 3D position to 2D screen coordinates
        const vector = position.clone();
        vector.project(camera);
        
        const x = (vector.x * 0.5 + 0.5) * rect.width + rect.left;
        const y = (-(vector.y * 0.5) + 0.5) * rect.height + rect.top;
        
        return {
          ...label,
          position: { x, y }
        };
      })
    );
  }, []);

  // Animation loop
  const animate = useCallback((time: number) => {
    animationFrameRef.current = requestAnimationFrame(animate);
    
    if (!rendererRef.current || !sceneRef.current || !cameraRef.current) return;
    
    timeRef.current = time;
    
    // Update particle positions every frame for smooth movement
    updateParticlePositions();
    
    // Animate background particles
    animateBackgroundParticles(time);
    
    const deltaTime = time - lastUpdateTimeRef.current;
    // Throttle some updates for better performance
    if (deltaTime > 100) { // Update every 100ms
      lastUpdateTimeRef.current = time;
      updateLabelPositions();
    }
    
    if (controlsRef.current) {
      controlsRef.current.update();
    }
    
    rendererRef.current.render(sceneRef.current, cameraRef.current);
  }, [updateParticlePositions, updateLabelPositions, animateBackgroundParticles]);

  // Handle window resize - updated to use canvasContainerRef
  const handleResize = useCallback(() => {
    if (!containerRef.current || !cameraRef.current || !rendererRef.current || !canvasContainerRef.current) return;
    
    const width = containerRef.current.clientWidth;
    const height = containerRef.current.clientHeight;
    
    cameraRef.current.aspect = width / height;
    cameraRef.current.updateProjectionMatrix();
    
    rendererRef.current.setSize(width, height);
    updateLabelPositions();
  }, [updateLabelPositions]);

  // Initialize and clean up
  useEffect(() => {
    const cleanup = initScene();
    
    // Start animation loop
    animationFrameRef.current = requestAnimationFrame(animate);
    
    // Add resize event listener
    window.addEventListener('resize', handleResize);
    
    return () => {
      if (cleanup) cleanup();
      
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      
      window.removeEventListener('resize', handleResize);
    };
  }, [initScene, animate, handleResize]);

  // Update visualization when simulation data or step changes (every 10 steps),
  // OR once on mount when there is no live data (placeholder mode).
  useEffect(() => {
    const noLive = !(state as any).simulationData;
    if (noLive || ((state as any).currentStep ?? 0) % 10 === 0) {
      updateParticleTargets();
    }
  }, [state.simulationData, state.currentStep, updateParticleTargets]);

  // Get the portal container (create if it doesn't exist)
  const getPortalContainer = () => {
    let portalContainer = document.getElementById('habm-labels-portal');
    if (!portalContainer) {
      portalContainer = document.createElement('div');
      portalContainer.id = 'habm-labels-portal';
      document.body.appendChild(portalContainer);
    }
    return portalContainer;
  };

  return (
    <Container ref={containerRef}>
      <Title>Agent Emotions (Paul Ekman's Model)</Title>
      <CanvasContainer ref={canvasContainerRef} />
      {createPortal(
        <LabelsOverlay>
          {labels.map(label => (
            <EmotionLabel
              key={label.id}
              style={{
                left: `${label.position.x}px`,
                top: `${label.position.y}px`,
                color: label.color
              }}
            >
              {label.text}
            </EmotionLabel>
          ))}
        </LabelsOverlay>,
        getPortalContainer()
      )}
    </Container>
  );
}

export default HABMSentiments; 