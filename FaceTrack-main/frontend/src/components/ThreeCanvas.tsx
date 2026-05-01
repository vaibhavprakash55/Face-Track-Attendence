import { useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Float, Sphere, Stars } from "@react-three/drei";
import * as THREE from "three";

function TechGlobe() {
  const meshRef = useRef<THREE.Group>(null);
  
  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.rotation.y = state.clock.elapsedTime * 0.15;
      meshRef.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.5) * 0.2;
    }
  });

  return (
    <Float speed={1.5} rotationIntensity={0.5} floatIntensity={1}>
      <group ref={meshRef}>
        {/* Core solid sphere */}
        <Sphere args={[2, 32, 32]}>
          <meshStandardMaterial 
            color="#0f766e" // Teal 700
            emissive="#115e59"
            emissiveIntensity={0.4}
            transparent
            opacity={0.8}
            roughness={0.1}
          />
        </Sphere>
        
        {/* Outer wireframe sphere */}
        <Sphere args={[2.2, 16, 16]}>
          <meshBasicMaterial 
            color="#34d399" // Emerald 400
            wireframe
            transparent
            opacity={0.3}
          />
        </Sphere>
        
        {/* Larger dynamic wireframe */}
        <Sphere args={[2.8, 12, 12]}>
          <meshBasicMaterial 
            color="#2dd4bf" // Teal 400
            wireframe
            transparent
            opacity={0.15}
          />
        </Sphere>
      </group>
    </Float>
  );
}

export default function ThreeCanvas() {
  return (
    <div className="absolute inset-0 z-0 pointer-events-none">
      <Canvas camera={{ position: [0, 0, 7], fov: 50 }}>
        {/* Ambient lighting */}
        <ambientLight intensity={0.4} />
        <directionalLight position={[5, 5, 5]} intensity={1.5} color="#2dd4bf" />
        <directionalLight position={[-5, -5, -5]} intensity={0.5} color="#059669" />
        
        {/* Floating tech globe */}
        <TechGlobe />
        
        {/* Background stars/particles */}
        <Stars radius={10} depth={50} count={1000} factor={4} saturation={0} fade speed={1} />
      </Canvas>
      
      {/* Soft overlay gradient to blend into the UI */}
      <div className="absolute inset-0 bg-gradient-to-t from-teal-950/20 to-transparent"></div>
    </div>
  );
}
