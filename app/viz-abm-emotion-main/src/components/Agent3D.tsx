import { useRef, useEffect } from 'react';
import { useFrame } from '@react-three/fiber';
import { Html } from '@react-three/drei';
import * as THREE from 'three';
import { gsap } from 'gsap';

interface Agent3DProps {
  position: [number, number, number];
  emotion: string;
  stress: number;
  agentId: number;
  location: string;
}

const emotionColors = {
  insecure: '#FF6B6B',
  energize: '#4ECDC4',
  threaten: '#FF4136',
  stress: '#FF851B',
  calm: '#2ECC40',
};

const Agent3D: React.FC<Agent3DProps> = ({ position, emotion, stress, agentId, location }) => {
  const meshRef = useRef<THREE.Mesh>(null);
  const glowRef = useRef<THREE.Mesh<THREE.SphereGeometry, THREE.MeshBasicMaterial>>(null);
  const particlesRef = useRef<THREE.Points>(null);

  // Create particle system for emotional aura
  useEffect(() => {
    if (!particlesRef.current) return;

    const particleCount = 50;
    const positions = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);
    const color = new THREE.Color(emotionColors[emotion as keyof typeof emotionColors] || '#FFFFFF');

    for (let i = 0; i < particleCount; i++) {
      const radius = 0.5 + Math.random() * 0.5;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.random() * Math.PI;

      positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = radius * Math.cos(phi);

      colors[i * 3] = color.r;
      colors[i * 3 + 1] = color.g;
      colors[i * 3 + 2] = color.b;
    }

    particlesRef.current.geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    particlesRef.current.geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  }, [emotion]);

  // Animate based on stress level and emotion
  useFrame((state) => {
    if (!meshRef.current || !glowRef.current || !particlesRef.current) return;

    // Pulse effect based on stress
    const pulseScale = 1 + Math.sin(state.clock.elapsedTime * 2) * (stress * 0.1);
    meshRef.current.scale.setScalar(pulseScale);

    // Rotate particles
    particlesRef.current.rotation.y += 0.005;

    // Glow intensity based on emotion
    const glowIntensity = 0.5 + Math.sin(state.clock.elapsedTime * 3) * 0.2;
    if (glowRef.current.material) {
      glowRef.current.material.opacity = glowIntensity;
    }
  });

  // Update effects when emotion or stress changes
  useEffect(() => {
    if (!meshRef.current || !glowRef.current) return;

    const color = emotionColors[emotion as keyof typeof emotionColors] || '#FFFFFF';
    const threeColor = new THREE.Color(color);

    gsap.to(meshRef.current.material, {
      duration: 0.5,
      emissiveIntensity: 0.5 + stress * 0.5,
    });

    if (glowRef.current.material) {
      gsap.to(glowRef.current.material, {
        duration: 0.5,
        opacity: 0.2,
      });
      glowRef.current.material.color = threeColor;
    }
  }, [emotion, stress]);

  return (
    <group position={position}>
      {/* Main agent body */}
      <mesh ref={meshRef}>
        <octahedronGeometry args={[0.3, 0]} />
        <meshPhongMaterial
          color={emotionColors[emotion as keyof typeof emotionColors] || '#FFFFFF'}
          emissive={emotionColors[emotion as keyof typeof emotionColors] || '#FFFFFF'}
          emissiveIntensity={0.5}
          shininess={100}
        />
      </mesh>

      {/* Glow effect */}
      <mesh ref={glowRef}>
        <sphereGeometry args={[0.4, 32, 32]} />
        <meshBasicMaterial
          color={emotionColors[emotion as keyof typeof emotionColors] || '#FFFFFF'}
          transparent
          opacity={0.2}
        />
      </mesh>

      {/* Particle system */}
      <points ref={particlesRef}>
        <bufferGeometry />
        <pointsMaterial
          size={0.05}
          vertexColors
          transparent
          opacity={0.6}
          blending={THREE.AdditiveBlending}
        />
      </points>

      {/* Hover info */}
      <Html
        position={[0, 0.6, 0]}
        style={{
          display: 'none',
          backgroundColor: 'rgba(0, 0, 0, 0.8)',
          padding: '8px',
          borderRadius: '4px',
          color: 'white',
          fontSize: '12px',
          whiteSpace: 'nowrap',
          pointerEvents: 'none',
        }}
        className="agent-tooltip"
      >
        <div>
          <strong>Agent ID:</strong> {agentId}
          <br />
          <strong>Emotion:</strong> {emotion}
          <br />
          <strong>Stress:</strong> {stress.toFixed(2)}
          <br />
          <strong>Location:</strong> {location}
        </div>
      </Html>
    </group>
  );
};

export default Agent3D; 