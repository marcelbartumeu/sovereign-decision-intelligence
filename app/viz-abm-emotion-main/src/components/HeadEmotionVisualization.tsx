import * as THREE from 'three';
import { useRef, useState, useEffect } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, useGLTF } from '@react-three/drei';
import styled from 'styled-components';

const Container = styled.div`
  width: 100%;
  height: 100%;
  position: relative;
  background: #000;
  border-radius: 8px;
  overflow: hidden;
`;

// Changed interface to accept Ekman emotions vector
interface HeadEmotionVisualizationProps {
  moodVector?: number[]; // Ekman emotions: [ANGER, CONTEMPT, DISGUST, ENJOYMENT, FEAR, SADNESS, SURPRISE]
  emotion?: string; // Keep for backward compatibility
}

// Map emotion strings to emotion objects (for backward compatibility)
const mapEmotionStringToObject = (emotionString: string): Emotions => {
  const baseEmotions: Emotions = {
    insecure: 0,
    energize: 0,
    threaten: 0,
    stress: 0,
    calm: 0
  };
  
  // Ensure this mapping matches the colors in Map3DView
  switch(emotionString) {
    case 'green':
      return { ...baseEmotions, calm: 1 };
    case 'red':
      return { ...baseEmotions, threaten: 1 };
    case 'purple':
      return { ...baseEmotions, insecure: 1 };
    case 'blue':
      return { ...baseEmotions, energize: 1 };
    case 'yellow':
      return { ...baseEmotions, stress: 1 };
    default:
      // Default to balanced emotions if unknown
      return {
        insecure: 0.2,
        energize: 0.2,
        threaten: 0.2,
        stress: 0.2,
        calm: 0.2
      };
  }
};

interface Emotions {
  insecure: number;
  energize: number;
  threaten: number;
  stress: number;
  calm: number;
}

const emotionColors = {
  insecure: new THREE.Color(0x9370DB),   // Purple
  energize: new THREE.Color(0xffd700),   // Gold
  threaten: new THREE.Color(0x8b0000),   // Dark Red
  stress: new THREE.Color(0xFFC0CB),    // Pink
  calm: new THREE.Color(0x00ff7f)        // Spring Green
};

const emotionParameters = {
  insecure: { rotationSpeed: 0.005, amplitude: 1.5 },
  energize: { rotationSpeed: 0.01, amplitude: 2.0 },
  threaten: { rotationSpeed: 0.02, amplitude: 1.8 },
  stress: { rotationSpeed: 0.015, amplitude: 1.0 },
  calm: { rotationSpeed: 0.001, amplitude: 0.5 }
};

// Function to calculate weighted parameters based on emotions
const calculateParameters = (emotions: Emotions) => {
  const totalWeight = Object.values(emotions).reduce((sum, val) => sum + val, 0) || 1;
  const color = new THREE.Color(0, 0, 0);
  let rotationSpeed = 0;
  let amplitude = 0;
  
  // New movement parameters
  let pulsationFrequency = 0;
  let turbulence = 0;
  let expansionFactor = 0;
  let waviness = 0;
  let asymmetry = 0;

  Object.entries(emotions).forEach(([emotion, value]) => {
    const weight = value / totalWeight;
    const emotionColor = emotionColors[emotion as keyof Emotions];
    const params = emotionParameters[emotion as keyof Emotions];

    color.r += emotionColor.r * weight;
    color.g += emotionColor.g * weight;
    color.b += emotionColor.b * weight;
    rotationSpeed += params.rotationSpeed * weight;
    amplitude += params.amplitude * weight;
    
    // Apply different movement patterns based on emotion
    switch(emotion) {
      case 'threaten': // Anger + contempt
        turbulence += 2.0 * weight;     // More chaotic movement
        asymmetry += 1.5 * weight;      // Asymmetric deformation
        break;
      case 'insecure': // Fear + sadness
        waviness += 2.0 * weight;       // Wavy, unstable movement
        pulsationFrequency += 3.0 * weight; // Rapid pulsation
        break;
      case 'stress': // Disgust + some surprise
        turbulence += 1.0 * weight;     // Some chaos
        pulsationFrequency += 2.0 * weight; // Medium pulsation
        break;
      case 'energize': // Surprise
        expansionFactor += 1.5 * weight; // Expanding outward motion
        pulsationFrequency += 1.0 * weight; // Quick pulses
        break;
      case 'calm': // Enjoyment
        expansionFactor += 0.5 * weight; // Gentle expansion
        waviness += 0.5 * weight;        // Smooth waves
        break;
    }
  });

  return { 
    color, 
    rotationSpeed, 
    amplitude,
    pulsationFrequency,
    turbulence,
    expansionFactor,
    waviness,
    asymmetry
  };
};

// Point Cloud Head Model Component
function HeadModel() {
  const pointsRef = useRef<THREE.Points>(null);
  const linesRef = useRef<THREE.LineSegments>(null);
  const timeRef = useRef(0);
  const groupRef = useRef<THREE.Group>(null);
  
  useEffect(() => {
    // Using a model URL that's reliable for testing
    const modelUrl = 'https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/models/gltf/LeePerrySmith/LeePerrySmith.glb';
    
    // Load using drei's useGLTF helper outside of the component render function
    const loadAndProcessModel = async () => {
      try {
        // Use dynamic import to load the GLTFLoader
        const { GLTFLoader } = await import('three/examples/jsm/loaders/GLTFLoader.js');
        const loader = new GLTFLoader();
        
        // Load the model
        loader.load(
          modelUrl,
          (gltf) => {
            let headMesh: THREE.Mesh | null = null;
            
            // Find the first mesh in the model
            gltf.scene.traverse((child) => {
              if (child instanceof THREE.Mesh && !headMesh) {
                headMesh = child as THREE.Mesh;
              }
            });
            
            if (!headMesh) {
              console.error('No mesh found in the model');
              return;
            }
            
            // Process the mesh
            createPointCloudFromMesh(headMesh);
          },
          (xhr) => {
            console.log(`${(xhr.loaded / xhr.total) * 100}% loaded`);
          },
          (error) => {
            console.error('Error loading model:', error);
          }
        );
      } catch (error) {
        console.error('Error loading GLTFLoader:', error);
      }
    };
    
    const createPointCloudFromMesh = (mesh: THREE.Mesh) => {
      if (!mesh.geometry) {
        console.error('Mesh does not have geometry');
        return;
      }
      
      // Get the mesh geometry
      const geometry = mesh.geometry.clone();
      
      // Apply model transformations
      if (mesh.parent) {
        const worldMatrix = new THREE.Matrix4();
        mesh.updateMatrixWorld(true);
        worldMatrix.copy(mesh.matrixWorld);
        geometry.applyMatrix4(worldMatrix);
      }
      
      // Compute bounding box for later calculations
      geometry.computeBoundingBox();
      const bbox = geometry.boundingBox;
      
      // Position attributes of the mesh
      const positionAttribute = geometry.attributes.position as THREE.BufferAttribute;
      const vertexCount = positionAttribute.count;
      
      // Arrays to store our point cloud data
      const positions: number[] = [];
      const sizes: number[] = [];
      const colors: number[] = [];
      
      // Create spatial filtering to avoid points that are too close to each other
      const minDistanceSquared = 0.08; // Minimum squared distance between points
      const existingPoints: THREE.Vector3[] = [];
      
      // Function to check if a point is too close to existing points
      const isTooClose = (point: THREE.Vector3): boolean => {
        for (const existingPoint of existingPoints) {
          const distSquared = point.distanceToSquared(existingPoint);
          if (distSquared < minDistanceSquared) {
            return true;
          }
        }
        return false;
      };
      
      // First pass: Sample vertices using distance filtering
      for (let i = 0; i < vertexCount; i++) {
        // Skip some vertices randomly to speed up initial sampling
        if (Math.random() > 0.3) continue;
        
        // Get vertex position
        const x = positionAttribute.getX(i);
        const y = positionAttribute.getY(i);
        const z = positionAttribute.getZ(i);
        
        const point = new THREE.Vector3(x, y, z);
        
        // Skip if too close to existing points
        if (isTooClose(point)) continue;
        
        // Add to our collection of points
        existingPoints.push(point.clone());
        
        // Vary point size based on position (smaller near facial features for better detail)
        let pointSize;
        
        // Make eyes and mouth areas have finer detail with smaller points
        const isFacialFeature = 
          (Math.abs(x) > 0.3 && Math.abs(x) < 0.6 && y > 0.1 && y < 0.5) || // Eyes
          (Math.abs(x) < 0.5 && y > -0.5 && y < -0.1); // Mouth
          
        if (isFacialFeature) {
          pointSize = 0.1 + 0.05 * Math.random();
        } else {
          pointSize = 0.15 + 0.05 * Math.random();
        }
        
        // Store position and size
        positions.push(x, y, z);
        sizes.push(pointSize);
        
        // Create subtle color gradient based on position
        let heightFactor = 0.5; // Default if no bounding box
        let depthFactor = 0.5;
        
        if (bbox) {
          const minY = bbox.min.y || 0;
          const maxY = bbox.max.y || 1;
          const minZ = bbox.min.z || 0;
          const maxZ = bbox.max.z || 1;
          
          heightFactor = (y - minY) / (maxY - minY);
          depthFactor = (z - minZ) / (maxZ - minZ);
        }
        
        const r = 0.65 + 0.25 * heightFactor + 0.1 * depthFactor;
        const g = 0.65 + 0.25 * heightFactor + 0.1 * depthFactor;
        const b = 0.75 + 0.20 * heightFactor + 0.05 * depthFactor;
        
        colors.push(r, g, b);
      }
      
      // If we don't have enough points, do a second pass with relaxed distance constraints
      if (existingPoints.length < 2000) {
        const secondPassDistanceSquared = minDistanceSquared * 0.7;
        
        for (let i = 0; i < vertexCount; i += 2) {
          // Get vertex position
          const x = positionAttribute.getX(i);
          const y = positionAttribute.getY(i);
          const z = positionAttribute.getZ(i);
          
          const point = new THREE.Vector3(x, y, z);
          
          // Check distance with reduced constraint
          let isTooCloseInSecondPass = false;
          for (const existingPoint of existingPoints) {
            const distSquared = point.distanceToSquared(existingPoint);
            if (distSquared < secondPassDistanceSquared) {
              isTooCloseInSecondPass = true;
              break;
            }
          }
          
          if (isTooCloseInSecondPass) continue;
          
          // Add to our collection of points
          existingPoints.push(point.clone());
          
          // Store position and size
          positions.push(x, y, z);
          sizes.push(0.15 + 0.05 * Math.random());
          
          // Create color
          let heightFactor = 0.5;
          let depthFactor = 0.5;
          
          if (bbox) {
            const minY = bbox.min.y || 0;
            const maxY = bbox.max.y || 1;
            const minZ = bbox.min.z || 0;
            const maxZ = bbox.max.z || 1;
            
            heightFactor = (y - minY) / (maxY - minY);
            depthFactor = (z - minZ) / (maxZ - minZ);
          }
          
          const r = 0.65 + 0.25 * heightFactor + 0.1 * depthFactor;
          const g = 0.65 + 0.25 * heightFactor + 0.1 * depthFactor;
          const b = 0.75 + 0.20 * heightFactor + 0.05 * depthFactor;
          
          colors.push(r, g, b);
        }
      }
      
      console.log(`Generated ${existingPoints.length} points with spatial filtering`);
      
      // Create points geometry
      const pointsGeometry = new THREE.BufferGeometry();
      pointsGeometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
      pointsGeometry.setAttribute('size', new THREE.Float32BufferAttribute(sizes, 1));
      pointsGeometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
      
      // Create points material
      const texture = new THREE.TextureLoader().load('https://threejs.org/examples/textures/sprites/disc.png');
      const pointsMaterial = new THREE.PointsMaterial({
        size: 0.18,
        map: texture,
        vertexColors: true,
        transparent: true,
        opacity: 0.9,
        depthWrite: false,
        blending: THREE.AdditiveBlending
      });
      
      // Create and update points
      if (pointsRef.current) {
        pointsRef.current.geometry = pointsGeometry;
        pointsRef.current.material = pointsMaterial;
      }
      
      // Create connecting lines between points
      const linePositions: number[] = [];
      const lineColors: number[] = [];
      
      // We'll connect nearby points, but not ones that are too close
      const maxDist = 0.7; // Maximum distance for connection
      const minLineDist = 0.2; // Minimum distance for connection to avoid too dense lines
      
      // Process a subset of points for lines to maintain performance
      for (let i = 0; i < positions.length; i += 9) { // Step by 3 vertices (9 values)
        const ix = positions[i];
        const iy = positions[i + 1];
        const iz = positions[i + 2];
        
        let connections = 0;
        const maxConnections = 3; // Limit connections per point
        
        for (let j = 0; j < positions.length; j += 9) {
          if (i === j) continue;
          
          const jx = positions[j];
          const jy = positions[j + 1];
          const jz = positions[j + 2];
          
          // Calculate distance
          const dx = ix - jx;
          const dy = iy - jy;
          const dz = iz - jz;
          const dist = Math.sqrt(dx*dx + dy*dy + dz*dz);
          
          // Connect if distance is in the right range and limit connections per point
          if (dist >= minLineDist && dist < maxDist && connections < maxConnections) {
            // Add line segment
            linePositions.push(ix, iy, iz, jx, jy, jz);
            
            // Use point colors for lines but more transparent
            const iColorIdx = Math.floor(i / 3) * 3;
            const jColorIdx = Math.floor(j / 3) * 3;
            
            lineColors.push(
              colors[iColorIdx] * 0.9, colors[iColorIdx + 1] * 0.9, colors[iColorIdx + 2] * 0.9,
              colors[jColorIdx] * 0.9, colors[jColorIdx + 1] * 0.9, colors[jColorIdx + 2] * 0.9
            );
            
            connections++;
          }
        }
      }
      
      // Create lines geometry
      const linesGeometry = new THREE.BufferGeometry();
      linesGeometry.setAttribute('position', new THREE.Float32BufferAttribute(linePositions, 3));
      linesGeometry.setAttribute('color', new THREE.Float32BufferAttribute(lineColors, 3));
      
      // Create lines material
      const linesMaterial = new THREE.LineBasicMaterial({
        vertexColors: true,
        transparent: true,
        opacity: 0.35,
        blending: THREE.AdditiveBlending
      });
      
      if (linesRef.current) {
        linesRef.current.geometry = linesGeometry;
        linesRef.current.material = linesMaterial;
      }
      
      // Scale and position the model to fit the scene
      if (groupRef.current) {
        // Apply scaling
        const scale = 4.0;
        groupRef.current.scale.set(scale, scale, scale);
        
        // Position adjustment (might need tweaking based on the model)
        groupRef.current.position.set(0, -2, 0);
        groupRef.current.rotation.set(0, Math.PI, 0); // Rotate to face forward
      }
    };
    
    // Start loading the model
    loadAndProcessModel();
  }, []);
  
  // Animate the point cloud subtly
  useFrame((_, delta) => {
    if (!pointsRef.current || !linesRef.current || !groupRef.current) return;
    
    timeRef.current += delta * 0.15;
    
    // Add gentle rotation
    groupRef.current.rotation.y += delta * 0.025;
    
    // Add subtle pulse animation
    const pulseScale = 1.0 + 0.01 * Math.sin(timeRef.current * 2);
    groupRef.current.scale.set(pulseScale * 4, pulseScale * 4, pulseScale * 4);
  });
  
  return (
    <group ref={groupRef}>
      <points ref={pointsRef}>
        <bufferGeometry />
        <pointsMaterial />
      </points>
      <lineSegments ref={linesRef}>
        <bufferGeometry />
        <lineBasicMaterial />
      </lineSegments>
    </group>
  );
}

// Emotion Visualization Component
function EmotionVisualization({ emotions }: { emotions: Emotions }) {
  const pointsRef = useRef<THREE.Points>(null);
  const linesRef = useRef<THREE.LineSegments>(null);
  const basePositionsRef = useRef<Float32Array | null>(null);
  const timeRef = useRef(0);
  const params = useRef(calculateParameters(emotions));
  
  // Update parameters when emotions change
  useEffect(() => {
    params.current = calculateParameters(emotions);
  }, [emotions]);
  
  // Setup points and lines
  useEffect(() => {
    // Create points for emotion visualization
    const numPoints = 1200; // Increased from 800 for more detail
    const baseRadius = 5.5;
    const pointsGeometry = new THREE.BufferGeometry();
    const positions = new Float32Array(numPoints * 3);
    const goldenRatio = (1 + Math.sqrt(5)) / 2;

    // Create a more brain-like shape by adding some distortion
    for (let i = 0; i < numPoints; i++) {
      const theta = 2 * Math.PI * i / goldenRatio;
      const phi = Math.acos(1 - 2 * (i + 0.5) / numPoints);
      
      // Base sphere coordinates
      let x = baseRadius * Math.cos(theta) * Math.sin(phi);
      let y = baseRadius * Math.sin(theta) * Math.sin(phi) - 1.5;
      let z = baseRadius * Math.cos(phi);
      
      // Add some "brain-like" distortion
      // Make it a bit flatter on the sides and more elongated top to bottom
      x *= 0.85 + 0.3 * Math.sin(5 * theta) * Math.sin(3 * phi);
      y *= 1.1 + 0.15 * Math.cos(4 * phi);
      z *= 0.9 + 0.2 * Math.sin(6 * theta);
      
      // Add some small bumps for a brain-like texture
      const bumpFactor = 0.15 * Math.sin(10 * theta) * Math.sin(10 * phi);
      x += x * bumpFactor;
      y += y * bumpFactor;
      z += z * bumpFactor;
      
      positions[i * 3] = x;
      positions[i * 3 + 1] = y;
      positions[i * 3 + 2] = z;
    }

    basePositionsRef.current = new Float32Array(positions);
    pointsGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

    // Create points material
    const sprite = new THREE.TextureLoader().load('https://threejs.org/examples/textures/sprites/disc.png');
    const pointsMaterial = new THREE.PointsMaterial({
      size: 0.3, // Increased size for better visibility
      map: sprite,
      vertexColors: true,
      transparent: true,
      alphaTest: 0.5,
      color: params.current.color,
      blending: THREE.AdditiveBlending
    });

    if (pointsRef.current) {
      pointsRef.current.geometry = pointsGeometry;
      pointsRef.current.material = pointsMaterial;
    }

    // Create lines for more complexity
    const linesGeometry = new THREE.BufferGeometry();
    const linesPositions: number[] = [];
    const k = 4; // Increased from 3 for more connections

    // Function to calculate distance between points
    const distance = (p1: number[], p2: number[]) => {
      const dx = p1[0] - p2[0],
            dy = p1[1] - p2[1],
            dz = p1[2] - p2[2];
      return Math.sqrt(dx * dx + dy * dy + dz * dz);
    };

    // Create k-nearest neighbors connections
    for (let i = 0; i < numPoints; i += 2) {
      const currentPoint = [positions[i * 3], positions[i * 3 + 1], positions[i * 3 + 2]];
      const distArr = [];
      for (let j = 0; j < numPoints; j += 2) {
        if (i === j) continue;
        const otherPoint = [positions[j * 3], positions[j * 3 + 1], positions[j * 3 + 2]];
        distArr.push({ index: j, dist: distance(currentPoint, otherPoint) });
      }
      distArr.sort((a, b) => a.dist - b.dist);
      for (let n = 0; n < k; n++) {
        const neighborIndex = distArr[n].index;
        linesPositions.push(
          positions[i * 3], positions[i * 3 + 1], positions[i * 3 + 2],
          positions[neighborIndex * 3], positions[neighborIndex * 3 + 1], positions[neighborIndex * 3 + 2]
        );
      }
    }

    linesGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(linesPositions), 3));
    const linesMaterial = new THREE.LineBasicMaterial({
      color: params.current.color,
      transparent: true,
      opacity: 0.7, // Increased opacity for better visibility
      blending: THREE.AdditiveBlending,
      linewidth: 1.5 // Note: linewidth only works in WebGL1, not WebGL2
    });

    if (linesRef.current) {
      linesRef.current.geometry = linesGeometry;
      linesRef.current.material = linesMaterial;
    }
  }, []);

  // Animation loop
  useFrame((_, delta) => {
    timeRef.current += delta;
    const { 
      color, 
      rotationSpeed, 
      amplitude, 
      pulsationFrequency,
      turbulence,
      expansionFactor,
      waviness,
      asymmetry
    } = params.current;

    if (pointsRef.current) {
      const positions = pointsRef.current.geometry.attributes.position.array as Float32Array;
      const basePositions = basePositionsRef.current!;
      
      // Update point positions with more dynamic movement based on emotions
      for (let i = 0; i < positions.length; i += 3) {
        // Base values to work with
        const baseX = basePositions[i];
        const baseY = basePositions[i + 1];
        const baseZ = basePositions[i + 2];
        
        // Distance from center for scaling effects
        const distFromCenter = Math.sqrt(baseX * baseX + baseY * baseY + baseZ * baseZ);
        
        // Time factors with different frequencies for varied animation
        const timeBase = timeRef.current;
        const time1 = timeBase * (1.0 + pulsationFrequency * 0.5);
        const time2 = timeBase * 0.7;
        const time3 = timeBase * 1.3;
        
        // Basic pulsation - smooth sine wave with constrained amplitude
        let pulseFactor = Math.sin(time1 + i * 0.05) * amplitude * 0.2;
        
        // Add turbulence - more chaotic movement when angry/threatened (reduced further)
        const turbulenceFactor = turbulence * (
          Math.sin(time2 + i * 0.21) *
          Math.cos(time3 + i * 0.17) *
          0.0375 // Halved from 0.075
        );
        
        // Add asymmetry - different parts move differently (reduced further)
        const asymmetryFactor = asymmetry * (
          Math.sin(baseX * 2.0 + timeBase) *
          Math.cos(baseZ * 1.5 + timeBase * 0.7) *
          0.025 // Halved from 0.05
        );
        
        // Add waviness - smooth wave patterns (reduced further)
        const waveFactor = waviness * (
          Math.sin(distFromCenter * 1.5 + timeBase) *
          0.025 // Halved from 0.05
        );
        
        // Add expansion - overall growth/contraction (reduced further)
        const expansionWave = Math.sin(timeBase * 0.5) * 0.5 + 0.5; // 0 to 1 wave
        const expansionAmount = expansionFactor * expansionWave * 0.05; // Halved from 0.1
        
        // Combine all effects with constraints to prevent excessive movement
        // Apply a hard limit to totalFactor to prevent extreme scaling
        const rawTotalFactor = 1.0 + pulseFactor + turbulenceFactor + waveFactor + expansionAmount;
        const totalFactor = Math.max(0.8, Math.min(1.2, rawTotalFactor)); // Limit between 0.8 and 1.2
        
        // Limit asymmetry offset to prevent points from moving too far
        const maxOffset = 0.1; // Reduced from 0.2
        const offsetX = Math.max(-maxOffset, Math.min(maxOffset, baseX * asymmetryFactor));
        const offsetY = Math.max(-maxOffset, Math.min(maxOffset, baseY * asymmetryFactor));
        const offsetZ = Math.max(-maxOffset, Math.min(maxOffset, baseZ * asymmetryFactor));
        
        // Apply to points
        positions[i] = baseX * totalFactor + offsetX;
        positions[i + 1] = baseY * totalFactor + offsetY;
        positions[i + 2] = baseZ * totalFactor + offsetZ;
      }
      
      pointsRef.current.geometry.attributes.position.needsUpdate = true;
      (pointsRef.current.material as THREE.PointsMaterial).color = color;
      
      // Limit rotation to prevent excessive movement
      const maxRotationSpeed = 0.01; // Maximum rotation speed per frame
      pointsRef.current.rotation.y += delta * Math.min(rotationSpeed * 1, maxRotationSpeed); // Reduced multiplier from 2 to 1
      pointsRef.current.rotation.x += delta * Math.min(rotationSpeed * turbulence * 0.25, maxRotationSpeed * 0.5); // Reduced multiplier from 0.5 to 0.25
      pointsRef.current.rotation.z += delta * Math.min(rotationSpeed * asymmetry * 0.15, maxRotationSpeed * 0.3); // Reduced multiplier from 0.3 to 0.15
    }

    if (linesRef.current) {
      (linesRef.current.material as THREE.LineBasicMaterial).color = color;
      
      // Apply same rotation to lines
      if (pointsRef.current) {
        linesRef.current.rotation.copy(pointsRef.current.rotation);
      }
    }
  });

  return (
    <group position={[0, 8, 0]}>
      <points ref={pointsRef}>
        <bufferGeometry />
        <pointsMaterial />
      </points>
      <lineSegments ref={linesRef}>
        <bufferGeometry />
        <lineBasicMaterial />
      </lineSegments>
    </group>
  );
}

// Scene setup
function Scene({ emotions }: { emotions: Emotions }) {
  return (
    <>
      <ambientLight intensity={0.8} />
      <directionalLight position={[5, 10, 7.5]} intensity={1.5} />
      <directionalLight position={[-5, -10, -7.5]} intensity={0.8} />
      <HeadModel />
      <EmotionVisualization emotions={emotions} />
      <OrbitControls enableDamping dampingFactor={0.05} rotateSpeed={0.7} />
    </>
  );
}

// New function to map mood vector to visualization parameters
const mapMoodVectorToEmotions = (moodVector?: number[]): Emotions => {
  // Default emotions if no mood vector provided
  if (!moodVector || moodVector.length !== 7) {
    return {
      insecure: 0.2,
      energize: 0.2,
      threaten: 0.2,
      stress: 0.2,
      calm: 0.2
    };
  }
  
  const [anger, contempt, disgust, enjoyment, fear, sadness, surprise] = moodVector;
  
  // Map Ekman emotions to our visualization emotions
  return {
    threaten: (anger + contempt) / 2, // Anger and contempt contribute to threatening feeling
    insecure: (fear + sadness) / 2,   // Fear and sadness contribute to insecurity
    stress: (disgust + surprise) / 2,  // Disgust and surprise contribute to stress
    energize: surprise,                // Surprise is energizing
    calm: enjoyment                    // Enjoyment is calming
  };
};

function HeadEmotionVisualization({ emotion, moodVector }: HeadEmotionVisualizationProps) {
  // Use mood vector if provided, otherwise fall back to emotion string
  const emotions = moodVector 
    ? mapMoodVectorToEmotions(moodVector)
    : (emotion ? mapEmotionStringToObject(emotion) : mapMoodVectorToEmotions());
  
  return (
    <Container>
      <Canvas 
        camera={{ position: [0, 9, 27], fov: 70 }}
        gl={{ antialias: true, powerPreference: 'low-power' }}
      >
        <Scene emotions={emotions} />
      </Canvas>
    </Container>
  );
}

export default HeadEmotionVisualization; 