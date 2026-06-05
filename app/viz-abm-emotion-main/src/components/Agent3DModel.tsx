import { useRef, useEffect } from 'react';
import { useFrame } from '@react-three/fiber';
import { useGLTF } from '@react-three/drei';
import * as THREE from 'three';

interface Agent3DModelProps {
  position: [number, number, number];
  rotation: [number, number, number];
  scale: [number, number, number];
  transport: string;
  emotion: string;
}

const emotionColors = {
  green: '#2ECC40', // calm
  red: '#FF4136',   // threaten
  purple: '#9B59B6', // insecure
  blue: '#0074D9',  // energize
  yellow: '#FFDC00' // stress
};

export function Agent3DModel({ position, rotation, scale, transport, emotion }: Agent3DModelProps) {
  const groupRef = useRef<THREE.Group>(null);
  const { scene } = useGLTF(`/models/${transport}.glb`);

  // Clone the scene to avoid sharing materials between instances
  const clonedScene = scene.clone();

  useEffect(() => {
    if (!clonedScene) return;

    // Apply emotion color to the model
    clonedScene.traverse((child) => {
      if (child instanceof THREE.Mesh) {
        const material = child.material as THREE.MeshStandardMaterial;
        if (material) {
          material.color.set(emotionColors[emotion as keyof typeof emotionColors] || '#FFFFFF');
          material.emissive.set(emotionColors[emotion as keyof typeof emotionColors] || '#FFFFFF');
          material.emissiveIntensity = 0.2;
        }
      }
    });
  }, [clonedScene, emotion]);

  useFrame((state) => {
    if (!groupRef.current) return;

    // Add subtle floating animation
    groupRef.current.position.y = position[1] + Math.sin(state.clock.elapsedTime * 2) * 0.1;
  });

  return (
    <group ref={groupRef} position={position} rotation={rotation} scale={scale}>
      <primitive object={clonedScene} />
    </group>
  );
}

// Preload the models
useGLTF.preload('/models/foot.glb');
useGLTF.preload('/models/car.glb');
useGLTF.preload('/models/bicycle.glb'); 