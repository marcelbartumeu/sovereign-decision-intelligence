import styled from 'styled-components';
import HABMSentiments from '../components/HABMSentiments';
import AgentVisualizationToggle from '../components/AgentVisualizationToggle';
import { useSharedState } from '../services/SharedStateContext';
import { useEffect, useMemo, useState, useRef } from 'react';
import RealTimeChat from '../components/RealTimeChat';

const Container = styled.div`
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 100vh;
  position: relative;
  background: rgb(0, 0, 0);
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
  color: #fff;
  overflow: hidden;
`;

const TopContainer = styled.div`
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  padding: 20px;
  min-height: 0;
`;

const BottomContainer = styled.div`
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 20px;
  padding: 20px;
  min-height: 0;
`;

const AgentInfo = styled.div`
  background: rgba(0, 0, 0, 0.8);
  border-radius: 12px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  
  h2 {
    color: #fff;
    margin: 0 0 20px 0;
    font-size: 3rem;
    font-weight: 300;
    letter-spacing: -0.5px;
  }
  
  ul {
    list-style-type: none;
    padding: 0;
    margin: 0;
  }
  
  li {
    margin-bottom: 16px;
    font-size: 25px;
    color: rgba(255, 255, 255, 0.9);
    letter-spacing: 0.2px;
  }
  
  span {
    font-weight: 500;
    margin-right: 8px;
    color: #fff;
  }
`;

const SentimentsContainer = styled.div`
  background: rgba(0, 0, 0, 0.8);
  border-radius: 12px;
  padding: 20px;
  overflow: hidden;
  
  h2 {
    color: #fff;
    margin: 0 0 20px 0;
    font-size: 1.8rem;
    font-weight: 300;
  }
`;

function VisualizationView() {
  const { state, updateState, loadSimulationData } = useSharedState();
  const [currentEmotion, setCurrentEmotion] = useState('happy');
  const lastEmotionChangeTime = useRef(Date.now());

  useEffect(() => {
    loadSimulationData();
  }, []);

  // Import the Emotions type from EmotionControls or define it here
  type Emotions = {
    ANGER: number;
    CONTEMPT: number;
    DISGUST: number;
    ENJOYMENT: number;
    FEAR: number;
    SADNESS: number;
    SURPRISE: number;
  };

  // Calculate current emotions distribution from agent data
  const currentEmotions = useMemo(() => {
    if (!state.simulationData?.agents) return state.emotions;

    // Initialize Ekman emotions
    const emotions = {
      ANGER: 0,
      CONTEMPT: 0,
      DISGUST: 0,
      ENJOYMENT: 0,
      FEAR: 0,
      SADNESS: 0,
      SURPRISE: 0
    };

    // Map colors to emotion types
    const colorToEmotion: Record<string, keyof typeof emotions> = {
      'red': 'ANGER',
      'green': 'ENJOYMENT',
      'purple': 'CONTEMPT',
      'blue': 'SURPRISE',
      'orange': 'FEAR'
    };

    state.simulationData.agents.forEach(agent => {
      const emotionKey = colorToEmotion[agent.emotion[agent.step]] || 'FEAR';
      emotions[emotionKey]++;
    });

    const total = state.simulationData.agents.length || 1;
    
    // Convert counts to percentages
    return {
      ANGER: emotions.ANGER / total,
      CONTEMPT: emotions.CONTEMPT / total,
      DISGUST: emotions.DISGUST / total,
      ENJOYMENT: emotions.ENJOYMENT / total,
      FEAR: emotions.FEAR / total,
      SADNESS: emotions.SADNESS / total,
      SURPRISE: emotions.SURPRISE / total
    };
  }, [state.simulationData, state.currentStep]);

  // Calculate average stress level from mood vectors
  const currentStressLevel = useMemo(() => {
    if (!state.simulationData?.agents) return 0;

    const totalStress = state.simulationData.agents.reduce((sum, agent) => {
      const moodVector = agent.mood_vector[agent.step];
      return sum + (moodVector ? moodVector.reduce((a, b) => a + b, 0) / moodVector.length : 0);
    }, 0);

    return totalStress / state.simulationData.agents.length;
  }, [state.simulationData, state.currentStep]);

  // Determine which emotion to display in the head visualization
  const displayEmotion = useMemo(() => {
    // If we have a followed agent, use its emotion
    if (state.followedAgent) {
      return state.followedAgent.emotion;
    }
    
    // Otherwise fallback to the dominant emotion from all agents
    return Object.entries(currentEmotions).reduce(
      (max, [emotion, value]) => value > max[1] ? [emotion, value] : max, 
      ['calm', 0]
    )[0];
  }, [state.followedAgent, currentEmotions]);

  // Get the mood vector of the followed agent for the head visualization
  const agentMoodVector = useMemo(() => {
    if (!state.followedAgent || !state.simulationData?.agents) {
      return undefined;
    }
    
    // Find the agent in the simulation data
    const agent = state.simulationData.agents.find(
      agent => agent.agent_id === state.followedAgent?.agentId
    );
    
    if (!agent) {
      return undefined;
    }
    
    // Return the mood vector at the current simulation step, not the agent's internal step
    // Make sure we don't go beyond the available data
    const stepIndex = Math.min(state.currentStep, agent.mood_vector.length - 1);
    return agent.mood_vector[stepIndex];
  }, [state.followedAgent, state.simulationData, state.currentStep]);

  // Detect emotion changes and enforce 15-second minimum display time
  useEffect(() => {
    if (!agentMoodVector) return;
    
    // Logic to determine emotion from mood vector
    const sad = agentMoodVector[2];
    const happy = agentMoodVector[0];
    const angry = agentMoodVector[1];
    
    let newEmotion = 'happy'; // Default emotion
    
    if (sad > happy && sad > angry) {
      newEmotion = 'sad';
    } else if (angry > happy && angry > sad) {
      newEmotion = 'angry';
    } else {
      newEmotion = 'happy';
    }
    
    // Only change emotion if 15 seconds have passed
    const now = Date.now();
    if (newEmotion !== currentEmotion && now - lastEmotionChangeTime.current >= 15000) {
      setCurrentEmotion(newEmotion);
      lastEmotionChangeTime.current = now;
    }
  }, [agentMoodVector, currentEmotion]);

  // Determine video path based on current emotion
  const videoPath = useMemo(() => {
    const agentId = state.followedAgent?.agentId || 'Carlos';

    return `/faces/${agentId}/${currentEmotion}.mp4`;
  }, [currentEmotion, state.followedAgent]);

  // Agent details to display
  const agentDetails = useMemo(() => {
    if (state.followedAgent) {
      return {
        id: state.followedAgent.agentId,
        age: state.followedAgent.agentId === 'Carlos' ? 56 : 54, // Example data - would come from actual agent data
        sex: state.followedAgent.agentId === 'Carlos' ? 'Male' : 'Female', // Example data
        personality: state.followedAgent.agentId === 'Carlos' ? 'Extroverted' : 'Introverted', // Example data
        occupation: state.followedAgent.agentId === 'Carlos' ? 'Teacher' : 'Doctor', // Example data
        currentEmotion: agentMoodVector
      };
    }
    
    return {
      id: 'None',
      age: '-',
      sex: '-',
      personality: '-',
      occupation: '-',
      currentEmotion: displayEmotion
    };
  }, [state.followedAgent, displayEmotion]);

  return (
    <Container>
      <TopContainer>
        <AgentInfo>
          <h2>{state.followedAgent ? `Agent ${state.followedAgent.agentId}` : 'Overall Agent Representation'}</h2>
          <ul>
            <li><span>ID:</span> {agentDetails.id}</li>
            <li><span>Age:</span> {agentDetails.age}</li>
            <li><span>Personality:</span> {agentDetails.personality}</li>
            <li><span>Occupation:</span> {agentDetails.occupation}</li>
          </ul>
        </AgentInfo>
        
        <AgentVisualizationToggle
          videoPath={videoPath}
          emotion={displayEmotion}
          moodVector={agentMoodVector}
        />
      </TopContainer>
      
      <BottomContainer>
        <RealTimeChat />
        
        <SentimentsContainer>
          <h2>Population Emotion Distribution</h2>
          <HABMSentiments agents={state.simulationData?.agents.map(agent => ({
            id: agent.agent_id,
            emotions: {
              insecure: agent.emotion[agent.step] === 'purple' ? 1 : 0,
              energize: agent.emotion[agent.step] === 'blue' ? 1 : 0,
              threaten: agent.emotion[agent.step] === 'red' ? 1 : 0,
              stress: agent.emotion[agent.step] === 'orange' ? 1 : 0,
              calm: agent.emotion[agent.step] === 'green' ? 1 : 0
            }
          })) || []} />
        </SentimentsContainer>
      </BottomContainer>
    </Container>
  );
}

export default VisualizationView; 