declare module '@deck.gl/react';
declare module '@deck.gl/layers';
declare module '@deck.gl/core';
declare module '@deck.gl/geo-layers';

import { useState, useEffect, useMemo, useRef } from 'react';
import DeckGL from '@deck.gl/react';
import { Map as MapGL } from 'react-map-gl';
import { ScatterplotLayer, TextLayer, IconLayer, PathLayer } from '@deck.gl/layers';
import { TripsLayer } from '@deck.gl/geo-layers';
import type { MapViewState, PickingInfo } from '@deck.gl/core';
import { FlyToInterpolator, WebMercatorViewport } from '@deck.gl/core';
import { easeCubic } from 'd3-ease';
import styled from 'styled-components';
import 'mapbox-gl/dist/mapbox-gl.css';
import mapboxgl from 'mapbox-gl';
import { useSharedState } from '../services/SharedStateContext';
import { SharedControlPanel } from '../components/SharedControlPanel';

const MAPBOX_ACCESS_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN;
console.log("Map3DView - Mapbox token available:", !!MAPBOX_ACCESS_TOKEN);

// Styled components for UI
// Removed unused KPIContainer and KPIItem styled components

const MapContainer = styled.div`
  width: 100%;
  height: 100vh;
  position: relative;
`;

// New styled component for the inset map
const InsetMapContainer = styled.div`
  position: absolute;
  top: 40px; /* Moved down */
  right: 40px; /* Moved left */
  width: 300px; /* Increased size */
  height: 240px; /* Increased size */
  border: 2px solid #555;
  border-radius: 8px; /* Increased rounding */
  z-index: 1002; /* Ensure it's above most elements */
  background-color: rgba(255, 255, 255, 0.1); /* Slightly visible background */
  pointer-events: none; /* Make the container non-interactive, including its children */
`;

const TransitionOverlay = styled.div<{ $isVisible: boolean }>`
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, ${props => props.$isVisible ? 0.7 : 0});
  transition: background-color 1s ease-in-out;
  pointer-events: none;
  z-index: 1001;
  display: flex;
  justify-content: center;
  align-items: center;
  opacity: ${props => props.$isVisible ? 1 : 0};
`;

const TransitionText = styled.div<{ $isVisible: boolean }>`
  color: white;
  font-size: 24px;
  font-weight: bold;
  text-align: center;
  opacity: ${props => props.$isVisible ? 1 : 0};
  transform: translateY(${props => props.$isVisible ? 0 : '20px'});
  transition: all 0.5s ease-in-out;
`;


// New styled component for the inset map title
const InsetMapTitle = styled.div`
  position: absolute;
  top: 5px;
  left: 10px;
  right: 10px; /* Ensure text doesn't overflow */
  color: #eee;
  background-color: rgba(0, 0, 0, 0.6);
  padding: 3px 6px;
  border-radius: 3px;
  font-size: 12px;
  font-weight: bold;
  text-align: center;
  z-index: 1; /* Above the map but below container border? */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis; /* Add ellipsis if text is too long */
`;

interface TripData {
  agentId: string;
  agentType: string;
  emotion: string;
  transport: string;
  location: string;
  path: Array<[number, number]>;
  timestamps: Array<number>;
}

interface ScatterLayerData {
  agentId: string;
  agentType: string;
  emotion: string;
  transport: string;
  location: string;
  position: [number, number];
  nextPosition: [number, number];
}


interface FollowedAgent {
  agent: TripData;
  startTime: number;
}

const INITIAL_VIEW_STATE: MapViewState = {
  longitude: 1.5218,
  latitude: 42.5063,
  zoom: 18,
  pitch: 30,
  bearing: 0
};

// Helper function to calculate bounding box (can be moved outside component if preferred)
function getPathBoundingBox(path: Array<[number, number]>): { minLng: number, maxLng: number, minLat: number, maxLat: number } | null {
  if (!path || path.length === 0) return null;
  let minLng = path[0][0], maxLng = path[0][0], minLat = path[0][1], maxLat = path[0][1];
  for (let i = 1; i < path.length; i++) {
    minLng = Math.min(minLng, path[i][0]);
    maxLng = Math.max(maxLng, path[i][0]);
    minLat = Math.min(minLat, path[i][1]);
    maxLat = Math.max(maxLat, path[i][1]);
  }
  // Add a small buffer if min/max are the same (single point)
  if (minLng === maxLng) {
    minLng -= 0.001;
    maxLng += 0.001;
  }
   if (minLat === maxLat) {
    minLat -= 0.001;
    maxLat += 0.001;
  }
  return { minLng, maxLng, minLat, maxLat };
}

// New InsetMap component
const InsetMap: React.FC = () => {
  const { state } = useSharedState();
  const [insetViewState, setInsetViewState] = useState<MapViewState | null>(null);
  const [followedAgentPath, setFollowedAgentPath] = useState<Array<[number, number]> | null>(null);
  const [followedAgentId, setFollowedAgentId] = useState<string | null>(null);
  const [currentAgentPosition, setCurrentAgentPosition] = useState<[number, number] | null>(null);

  useEffect(() => {
    // Get the currently followed agent's ID from shared state
    const currentFollowedAgentId = state.followedAgent?.agentId;
    const currentStep = state.currentStep;
    const currentInterpolationStep = state.currentInterpolationStep;

    if (currentFollowedAgentId && state.simulationData?.agents) {
        // Find the full agent data using the ID
       const agentData = state.simulationData.agents.find(agent => agent.agent_id === currentFollowedAgentId);

       if (agentData) {
           // Determine which path to use based on the current step
           let pathToDisplay: Array<[number, number]> | null = null;
           let pathType = 'actual'; // For logging/debugging

          // IMPORTANT: Assumes agentData has an 'intended_path' property
          if (currentStep < 10 && agentData.intended_path && agentData.intended_path.length > 0) {
            // Use intended_path if step < 10 and it exists and is not empty
            pathToDisplay = agentData.intended_path;
            pathType = 'intended';
          } else if (agentData.path && agentData.path.length > 0) {
            // Otherwise, use the actual path if it exists and is not empty
            pathToDisplay = agentData.path;
            pathType = 'actual';
          }

          console.log(`InsetMap: Using ${pathType} path for Agent ${currentFollowedAgentId} (Step ${currentStep})`);

          if (pathToDisplay) {
              setFollowedAgentPath(pathToDisplay);
              setFollowedAgentId(currentFollowedAgentId); // Store ID for title

              // Hide the position marker during the transition step (step 10)
              if (currentStep === 10) {
                  setCurrentAgentPosition(null);
                  console.log(`InsetMap: Hiding position marker during path switch (Step 10)`);
              } else if (pathToDisplay.length > 1) { // Ensure path has at least 2 points for interpolation
                  const maxPathIndex = pathToDisplay.length - 1;
                  const currentPathIndex = Math.min(Math.floor(currentStep), maxPathIndex);
                  const nextPathIndex = Math.min(currentPathIndex + 1, maxPathIndex);

                  const currentPos = pathToDisplay[currentPathIndex];
                  const nextPos = pathToDisplay[nextPathIndex];

                  // Check if indices are valid and positions exist
                  if (currentPos && nextPos && currentPathIndex <= maxPathIndex && nextPathIndex <= maxPathIndex) {
                    const interpolationFactor = currentInterpolationStep / 40;
                    const interpolatedPosition: [number, number] = [
                        currentPos[0] + (nextPos[0] - currentPos[0]) * interpolationFactor,
                        currentPos[1] + (nextPos[1] - currentPos[1]) * interpolationFactor
                    ];
                    setCurrentAgentPosition(interpolatedPosition);
                  } else {
                      // Handle cases where path might be too short or step index invalid after filtering step 10
                      setCurrentAgentPosition(null);
                      console.warn(`InsetMap: Could not calculate current position for Agent ${currentFollowedAgentId} at step ${currentStep}. Path length: ${pathToDisplay.length}`);
                  }
              } else {
                  // Path has 0 or 1 points, cannot interpolate
                  setCurrentAgentPosition(null);
                  console.warn(`InsetMap: Path too short to calculate position for Agent ${currentFollowedAgentId}. Path length: ${pathToDisplay.length}`);
              }

              const bbox = getPathBoundingBox(pathToDisplay);

              if (bbox) {
                const { minLng, maxLng, minLat, maxLat } = bbox;
                try {
                  const viewport = new WebMercatorViewport({ width: 300, height: 240 }); // Match updated container size
                  const { longitude, latitude, zoom } = viewport.fitBounds(
                    [[minLng, minLat], [maxLng, maxLat]],
                    { padding: 20 } // Add some padding
                  );
                  setInsetViewState({
                    longitude,
                    latitude,
                    zoom: Math.min(zoom, 18), // Cap max zoom level if needed
                    pitch: 0,
                    bearing: 0,
                    transitionDuration: 500, // Allow smooth transition between agents
                    transitionEasing: easeCubic
                  });
                } catch (e) {
                  console.error("Error calculating inset map bounds:", e);
                  // Fallback view
                  setInsetViewState({
                    longitude: (minLng + maxLng) / 2,
                    latitude: (minLat + maxLat) / 2,
                    zoom: 14,
                    pitch: 0,
                    bearing: 0,
                  });
                }
              }
           } else {
             // Agent found but no valid path (intended or actual) available
             setFollowedAgentPath(null);
             setInsetViewState(null);
             setFollowedAgentId(null);
             setCurrentAgentPosition(null); // Clear position
          }
       } else {
         // Agent with the specified ID was not found in simulationData.agents
         setFollowedAgentPath(null);
         setInsetViewState(null);
         setFollowedAgentId(null);
         setCurrentAgentPosition(null); // Clear position
       }
    } else {
        // No agent is being followed, or simulation data not loaded
       setFollowedAgentPath(null);
       setInsetViewState(null);
       setFollowedAgentId(null);
       setCurrentAgentPosition(null); // Clear position
    }
  }, [state.followedAgent, state.simulationData, state.currentStep, state.currentInterpolationStep]);

  if (!insetViewState || !followedAgentPath || !followedAgentId) {
    return null; // Don't render if no data or view state
  }

  const layers = [
    new PathLayer({
      id: 'followed-agent-path-inset',
      data: [{ path: followedAgentPath }],
      getPath: d => d.path,
      getColor: [230, 0, 0, 200], // Bright red path
      getWidth: 3,
      widthMinPixels: 2,
      widthMaxPixels: 4,
      rounded: true,
    }),

    // Layer for the current agent position
    ...(currentAgentPosition ? [ // Conditionally add layer only if position exists
        new ScatterplotLayer({
            id: 'followed-agent-position-inset',
            data: [{ position: currentAgentPosition }],
            getPosition: d => d.position,
      getFillColor: () => [0, 0, 128], // Navy blue RGB (constant accessor)
      getRadius: () => 5, // Size of the dot (constant accessor)
            radiusMinPixels: 4,
            radiusMaxPixels: 6,
            pickable: false, // Not interactive
        })
    ] : []),
  ];

  return (
    // Use React.Fragment to return multiple elements (title + map)
    <>
      <InsetMapTitle title={`Agent ${followedAgentId}'s intended path`}>
        {`Agent ${followedAgentId}'s path`}
      </InsetMapTitle>
      <DeckGL
        viewState={insetViewState}
        layers={layers}
        controller={false} // Disable interaction
        onViewStateChange={() => {}} // Add dummy handler required by types
      >
        <MapGL
          mapboxAccessToken={MAPBOX_ACCESS_TOKEN}
          mapStyle="mapbox://styles/mapbox/dark-v10" // Changed to dark style
          attributionControl={false}
          reuseMaps // Important for multiple maps
        />
      </DeckGL>
    </>
  );
};

function Map3DView() {
  const { state, loadSimulationData, setFollowedAgent } = useSharedState();
  const [viewState, setViewState] = useState<MapViewState>(INITIAL_VIEW_STATE);
  // Removed hoverInfo state (tooltips handled via DeckGL getTooltip)
  const [time, setTime] = useState(0);
  const [followedAgent, setFollowedAgent_local] = useState<FollowedAgent | null>(null);
  const followTimerRef = useRef<NodeJS.Timeout | null>(null);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const mapRef = useRef<mapboxgl.Map | null>(null);

  useEffect(() => {
    loadSimulationData();
  }, []);

  useEffect(() => {
    if (state.currentStep > 0) {
      // Update time to include interpolation
      const interpolatedTime = state.currentStep + (state.currentInterpolationStep / 40);
      setTime(interpolatedTime);
    }
  }, [state.currentStep, state.currentInterpolationStep]);

  // Effect to update view state based on followed agent's position
  useEffect(() => {
    // Revert to using followedAgent
    if (!followedAgent || !state.isPlaying) return;

    const updateView = () => {
      // Revert to using followedAgent
      const agent = followedAgent.agent;
      const currentPathIndex = Math.floor(time); 
      const nextPathIndex = Math.min(currentPathIndex + 1, agent.path.length - 1); 
      
      const currentPos = agent.path[currentPathIndex];
      const nextPos = agent.path[nextPathIndex];

      // Safety check (optional, but good practice)
      if (!currentPos || !nextPos) {
        console.warn(`Agent ${agent.agentId} path missing for time ${time}`);
        return;
      }
      
      const interpolationFactor = state.currentInterpolationStep / 40;
      const interpolatedPosition: [number, number] = [
        currentPos[0] + (nextPos[0] - currentPos[0]) * interpolationFactor,
        currentPos[1] + (nextPos[1] - currentPos[1]) * interpolationFactor
      ];

      // Update view state to smoothly follow agent's position
      setViewState(prevViewState => ({
        ...prevViewState, // Keep existing zoom, pitch, etc. unless overridden
        longitude: interpolatedPosition[0],
        latitude: interpolatedPosition[1],
        bearing: prevViewState.bearing, // Keep existing bearing
        transitionDuration: 20, // Smooth transition matching the interval
        transitionInterpolator: new FlyToInterpolator(), // Use default FlyToInterpolator
        transitionEasing: easeCubic
      }));
    };

    // Update more frequently for smoother movement
    const intervalId = setInterval(updateView, 20); // Update every 50ms for smoother following

    return () => {
      clearInterval(intervalId);
    };
  }, [followedAgent, time, state.currentInterpolationStep, state.isPlaying]);

  // Function to randomly select and follow an agent
  const selectRandomAgent = () => {
    if (!state.simulationData?.agents || state.simulationData.agents.length === 0) {
      return;
    }

    // Filter agents that have the 'follow' property set to true
    const followableAgents = state.simulationData.agents.filter(agent => agent.follow);

    if (followableAgents.length === 0) {
      console.log("No agents available to follow.");
      // Optionally, reset the followed agent or keep the current one
      setFollowedAgent_local(null); 
      setFollowedAgent(null); // Update shared state as well
      return;
    }

    const randomIndex = Math.floor(Math.random() * followableAgents.length);
    const agent = followableAgents[randomIndex];
    
    const tripData: TripData = {
      agentId: agent.agent_id,
      agentType: agent.type,
      emotion: agent.emotion[agent.step],
      transport: agent.transport_method[agent.step],
      location: `[${agent.path[agent.step][0].toFixed(4)}, ${agent.path[agent.step][1].toFixed(4)}]`,
      path: agent.path,
      timestamps: agent.path.map((_, i) => i * 40),
    };

    setFollowedAgent_local({
      agent: tripData,
      startTime: Date.now()
    });
  };

  // Function to handle the transition overlay
  const handleAgentTransition = async () => {
    setIsTransitioning(true);
    
    // Wait for fade in
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // Select new agent
    selectRandomAgent(); // This will eventually update the followedAgent state

    // Ensure NO setViewState or logic reading local state is here
    
    // Wait a bit before fading out
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    setIsTransitioning(false);
  };

  // Effect to handle agent following and periodic changes
  useEffect(() => {
    if (!state.isPlaying) return;

    // Start with a random agent if none is selected (using the main state)
    if (!followedAgent) { 
      handleAgentTransition();
    }

    // Set up timer to change focus every minute
    followTimerRef.current = setInterval(() => {
      handleAgentTransition();
    }, 60000); // 60000ms = 1 minute

    return () => {
      if (followTimerRef.current) {
        clearInterval(followTimerRef.current);
      }
    };
  }, [state.isPlaying, state.simulationData]);

  // *** NEW useEffect for Initial Zoom Transition ***
  useEffect(() => {
    if (followedAgent) {
      console.log(`Followed agent changed (${followedAgent.agent.agentId}), setting initial view...`);
      const agent = followedAgent.agent;
      // Calculate current position based on global time/step
      const currentPathIndex = Math.floor(time);
      const nextPathIndex = Math.min(currentPathIndex + 1, agent.path.length - 1);
      
      if (agent.path && agent.path.length > 0) {
        const currentPos = agent.path[currentPathIndex] ?? agent.path[0]; // Fallback needed if time=0 and step=0
        const nextPos = agent.path[nextPathIndex] ?? currentPos;
        const interpolationFactor = state.currentInterpolationStep / 40;
        const interpolatedPosition: [number, number] = [
          currentPos[0] + (nextPos[0] - currentPos[0]) * interpolationFactor,
          currentPos[1] + (nextPos[1] - currentPos[1]) * interpolationFactor
        ];

        setViewState(prev => ({
          ...prev, // Keep current pitch, bearing from previous state
          longitude: interpolatedPosition[0],
          latitude: interpolatedPosition[1],
          zoom: 19, // Set the desired initial zoom level here
          transitionDuration: 1000, // Duration for the initial fly-to
          transitionInterpolator: new FlyToInterpolator({speed: 1.2}),
          transitionEasing: easeCubic,
        }));
      } else {
        console.warn(`Agent ${agent.agentId} has no path data for initial view.`);
      }
    }
    // This effect runs ONLY when followedAgent changes
  }, [followedAgent]); 

  // Add effect to update the shared state when followedAgent changes
  useEffect(() => {
    // Revert to using followedAgent
    if (followedAgent) {
      setFollowedAgent({
        // Revert to using followedAgent
        agentId: followedAgent.agent.agentId,
        agentType: followedAgent.agent.agentType,
        transport: followedAgent.agent.transport,
        emotion: followedAgent.agent.emotion
      });
    } else {
      setFollowedAgent(null);
    }
    // Revert dependency list
  }, [followedAgent, setFollowedAgent]);

  // Update effect to handle followed agent emotion updates during simulation playback
  useEffect(() => {
    // Revert to using followedAgent
    if (followedAgent && state.simulationData?.agents) {
      // Find the current agent in the simulation data
      // Revert to using followedAgent
      const agent = state.simulationData.agents.find(a => a.agent_id === followedAgent.agent.agentId);
      if (agent) {
        const currentPathIndex = Math.floor(time);
        const currentEmotion = agent.emotion[Math.min(currentPathIndex, agent.emotion.length - 1)];
        
        // Only update if the emotion changed
        // Revert to using followedAgent
        if (currentEmotion !== followedAgent.agent.emotion) {
          // Update shared state (consistency check)
          setFollowedAgent({
            // Revert to using followedAgent
            agentId: followedAgent.agent.agentId,
            agentType: followedAgent.agent.agentType, 
            emotion: currentEmotion,
            transport: followedAgent.agent.transport
          });
        }
      }
    }
    // Remove setFollowedAgent_local from dependencies
  }, [time, state.currentStep, state.currentInterpolationStep, followedAgent, state.simulationData, setFollowedAgent]);

  // Heatmap removed

  const layers = useMemo(() => {
    if (!state.simulationData?.agents) return [];

    // Prepare trip data for visualization
    const tripData: TripData[] = state.simulationData.agents.map(agent => ({
      agentId: agent.agent_id,
      agentType: agent.type,
      emotion: agent.emotion[agent.step],
      transport: agent.transport_method[agent.step],
      location: `[${agent.path[agent.step][0].toFixed(4)}, ${agent.path[agent.step][1].toFixed(4)}]`,
      path: agent.path,
      timestamps: agent.path.map((_, i) => i * 40),
    }));

    // Create a scatterplot layer to show agent positions at the current time
    const scatterData: ScatterLayerData[] = state.simulationData.agents.map(agent => {
      if (!agent.path || agent.path.length === 0) {
        return {
          agentId: agent.agent_id,
          agentType: 'red',
          emotion: 'unknown',
          transport: 'unknown',
          location: '[0, 0]',
          position: [0, 0],
          nextPosition: [0, 0]
        };
      }

      const maxPathIndex = agent.path.length - 1; // Calculate max valid index
      const currentPathIndex = Math.min(Math.floor(time), maxPathIndex); // Clamp current index
      const nextPathIndex = Math.min(currentPathIndex + 1, maxPathIndex); // Clamp next index

      const currentPos = agent.path[currentPathIndex];
      const nextPos = agent.path[nextPathIndex];
      
      // Add a check for safety, although clamping should prevent undefined here if path.length > 0
      if (!currentPos || !nextPos) {
        console.error(`Agent ${agent.agent_id} has invalid position data at step ${time}. Path length: ${agent.path.length}`);
        // Return default data or handle appropriately
        return {
          agentId: agent.agent_id,
          agentType: 'red', // Indicate error state?
          emotion: 'unknown',
          transport: 'unknown',
          location: '[0, 0]',
          position: [0, 0],
          nextPosition: [0, 0]
        };
      }
      
      const interpolationFactor = state.currentInterpolationStep / 40;
      const interpolatedPosition: [number, number] = [
        currentPos[0] + (nextPos[0] - currentPos[0]) * interpolationFactor,
        currentPos[1] + (nextPos[1] - currentPos[1]) * interpolationFactor
      ];

      const currentEmotion = agent.emotion?.[currentPathIndex] || 'unknown';
      const currentTransport = agent.transport_method?.[currentPathIndex] || 'unknown';
      
      return {
        agentId: agent.agent_id,
        agentType: agent.type,
        emotion: currentEmotion,
        transport: currentTransport,
        location: `[${interpolatedPosition[0].toFixed(4)}, ${interpolatedPosition[1].toFixed(4)}]`,
        position: interpolatedPosition,
        nextPosition: nextPos
      };
    });

  const agentLayers = [
      // Enhanced TripsLayer for smoother path visualization
      new TripsLayer({
        id: 'trips',
        data: tripData,
        currentTime: state.currentStep * 40 + state.currentInterpolationStep,
        getPath: (d: TripData) => d.path || [],
        getTimestamps: (d: TripData) => d.timestamps || [],
        getColor: (d: TripData) => {
          const transportColors: Record<string, [number, number, number]> = {
            'foot': [255, 255, 255],
            'bicycle': [255, 87, 51],
            'car': [51, 161, 255],
            'bus': [51, 255, 87],
            'train': [255, 51, 233]
          };
          return transportColors[d.transport] || [128, 128, 128];
        },
        opacity: 0.7,
        widthMinPixels: 3,
        rounded: true,
        fadeTrail: true,
        trailLength: 25,
        shadowEnabled: false
      }),

      // Agent ScatterplotLayer (reverted highlighting)
      new ScatterplotLayer({
        id: 'agents',
        data: scatterData,
        pickable: true,
        opacity: 0.8,
        radiusMinPixels: 8, // Reverted
        radiusMaxPixels: 8, // Reverted
        getPosition: (d: ScatterLayerData) => d.position,
        getFillColor: (d: ScatterLayerData) => {
          const emotionColors: Record<string, [number, number, number]> = {
            'green': [0, 255, 0],
            'red': [255, 0, 0],
            'purple': [128, 0, 128],
            'blue': [0, 0, 255],
            'yellow': [255, 255, 0]
          };
          return emotionColors[d.emotion] || [128, 128, 128];
        },
        getLineColor: [255, 255, 255, 100], // Reverted (dimmer white for all)
        getLineWidth: 1, // Reverted
        getRadius: 8 // Reverted
      } as any),
      
      // Icon layer for the followed agent
      new IconLayer({
        id: 'followed-agent-icon',
        data: followedAgent ? scatterData.filter(d => d.agentId === followedAgent.agent.agentId) : [],
        pickable: false,
        iconAtlas: 'https://raw.githubusercontent.com/visgl/deck.gl-data/master/website/icon-atlas.png',
        iconMapping: 'https://raw.githubusercontent.com/visgl/deck.gl-data/master/website/icon-atlas.json',
        getIcon: () => 'marker', // Use a standard marker icon
        sizeScale: 15, // Adjust size as needed
        getPosition: (d: ScatterLayerData) => d.position,
        getSize: 5, // Adjust pixel size as needed
        getColor: [255, 255, 0] // Yellow color for the icon
      })
    ];
    
    // Combine agent layers (heatmap removed)
    return agentLayers;
  }, [state.simulationData, time, followedAgent]);

  // Prepare data for conversation bubbles
  const textLayerData = useMemo(() => {
    if (!state.simulationData?.agents) return [];

    const data: { position: [number, number, number]; text: string }[] = [];
    const currentPathIndex = Math.floor(time);

    state.simulationData.agents.forEach(agent => {
      if (!agent.path || agent.path.length === 0 || !agent.conversation || !agent.conversation_timestamps) {
        return;
      }

      const conversationIndex = agent.conversation_timestamps.findIndex(ts => ts === currentPathIndex);

      if (conversationIndex !== -1) {
        const text = agent.conversation[conversationIndex];

        // Calculate interpolated position (same logic as scatterData)
        const currentPos = agent.path[currentPathIndex];
        const nextPathIndex = Math.min(currentPathIndex + 1, agent.path.length - 1);
        const nextPos = agent.path[nextPathIndex];
        const interpolationFactor = state.currentInterpolationStep / 40;
        const interpolatedPosition: [number, number] = [
          currentPos[0] + (nextPos[0] - currentPos[0]) * interpolationFactor,
          currentPos[1] + (nextPos[1] - currentPos[1]) * interpolationFactor
        ];

        // Add a slight vertical offset for the bubble
        const positionWithOffset: [number, number, number] = [interpolatedPosition[0], interpolatedPosition[1], 10]; // Adjust Z offset as needed

        data.push({ position: positionWithOffset, text });
      }
    });
    return data;
  }, [state.simulationData, time, state.currentInterpolationStep]);

  // Combine agent layers, heatmap layer, and text layer
  const combinedLayers = useMemo(() => {
    const baseLayers = layers; // Get layers calculated in the previous useMemo

    const conversationLayer = new TextLayer({
        id: 'conversation-bubbles',
        data: textLayerData,
        getPosition: d => d.position,
        getText: d => d.text,
        getSize: 14,
        getColor: [255, 255, 255, 255], // White text
        getAngle: 0,
        getTextAnchor: 'middle',
        getAlignmentBaseline: 'center',
        getPixelOffset: [0, -25], // Offset slightly above the agent position
        // Bubble styling
        fontFamily: 'Arial, sans-serif',
        fontWeight: 'bold',
        backgroundColor: [0, 0, 0, 180], // Semi-transparent black background
        outlineWidth: 2,
        outlineColor: [255, 255, 255, 255], // White outline
        // Ensure text background adapts to text length (requires deck.gl v8.x+)
         // If using older versions, background might be fixed size. Consider alternative styling if needed.
         // wordBreak: 'break-word', // Might need adjustment depending on deck.gl version
         // width: 200 // Optional: set max width
      });

    return [...baseLayers, conversationLayer];
  }, [layers, textLayerData]);

  // Removed unused emotionStats computation

  // Add 3D buildings when map is loaded
  const onMapLoad = (event: { target: mapboxgl.Map }) => {
    mapRef.current = event.target;
    
    // Save the map style
    const map = mapRef.current;
    
    // Add 3D building layer
    addBuildingsLayer(map);
    
    // Listen for style changes and re-add buildings when style changes
    map.on('styledata', () => {
      // Need to wait for the style to load completely
      if (!map.isStyleLoaded()) {
        map.once('style.load', () => {
          addBuildingsLayer(map);
        });
      } else {
        addBuildingsLayer(map);
      }
    });
  };
  
  // Helper function to add 3D buildings layer
  const addBuildingsLayer = (map: mapboxgl.Map) => {
    // If buildings layer already exists, remove it first
    if (map.getLayer('3d-buildings')) {
      map.removeLayer('3d-buildings');
    }
    
    // Add 3D buildings layer
    map.addLayer({
      'id': '3d-buildings',
      'source': 'composite',
      'source-layer': 'building',
      'filter': ['==', 'extrude', 'true'],
      'type': 'fill-extrusion',
      'minzoom': 15,
      'paint': {
        'fill-extrusion-color': state.useRealisticMap 
          ? '#aaa' 
          : '#666',
        'fill-extrusion-height': [
          'interpolate', ['linear'], ['zoom'],
          15, 0,
          15.05, ['get', 'height']
        ],
        'fill-extrusion-base': [
          'interpolate', ['linear'], ['zoom'],
          15, 0,
          15.05, ['get', 'min_height']
        ],
        'fill-extrusion-opacity': state.useRealisticMap ? 0.7 : 0.5
      }
    });
  };

  // Update building appearance when map style changes
  useEffect(() => {
    if (mapRef.current && mapRef.current.getLayer('3d-buildings')) {
      mapRef.current.setPaintProperty(
        '3d-buildings', 
        'fill-extrusion-color', 
        state.useRealisticMap ? '#aaa' : '#666'
      );
      
      mapRef.current.setPaintProperty(
        '3d-buildings', 
        'fill-extrusion-opacity', 
        state.useRealisticMap ? 0.7 : 0.5
      );
    }
  }, [state.useRealisticMap]);

  return (
    <MapContainer>
      <DeckGL
        {...({
          viewState: viewState,
          controller: true,
          onViewStateChange: ({ viewState }: { viewState: MapViewState }) => setViewState(viewState),
          layers: combinedLayers,
          getTooltip: ({ object, layer }: PickingInfo) => {
            if (!object) return null;
            // Agent Tooltip (check layer id or object properties)
             if (layer?.id === 'agents' && object.agentId) {
                // Cast object safely
                const agentData = object as ScatterLayerData;
                return {
                  html: `
                    <div><strong>Agent ID:</strong> ${agentData.agentId}</div>
                    <div><strong>Emotion:</strong> ${agentData.emotion}</div>
                    <div><strong>Transport:</strong> ${agentData.transport}</div>
                    <div><strong>Location:</strong> ${agentData.location}</div>
                  `,
                   style: {
                    backgroundColor: 'rgba(0,0,0,0.8)',
                    color: 'white',
                    padding: '10px',
                    borderRadius: '4px',
                    fontSize: '12px',
                    maxWidth: '300px',
                    zIndex: 1005 // Ensure tooltip is above other elements
                  }
                };
             }

            return null; // No tooltip for other layers or objects
          }
        } as any)}
      >
        <MapGL
          mapboxAccessToken={MAPBOX_ACCESS_TOKEN}
          mapStyle={state.useRealisticMap 
            ? "mapbox://styles/mapbox/satellite-streets-v11" 
            : "mapbox://styles/mapbox/dark-v10"
          }
          reuseMaps
          attributionControl={false}
          onLoad={onMapLoad}
          ref={(ref) => {
            if (ref) {
              mapRef.current = ref.getMap();
            }
          }}
        />
      </DeckGL>

      <TransitionOverlay $isVisible={isTransitioning}>
        <TransitionText $isVisible={isTransitioning}>
          {followedAgent ? `Following Agent ${followedAgent.agent.agentId}` : 'Selecting random agent...'}
        </TransitionText>
      </TransitionOverlay>

      {/* Shared Control Panel */}
      <SharedControlPanel />

      {/* Inset Map */}
      <InsetMapContainer>
        <InsetMap />
      </InsetMapContainer>

    </MapContainer>
  );
}

export default Map3DView;
