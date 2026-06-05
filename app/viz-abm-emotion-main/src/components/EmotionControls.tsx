import React from 'react';
import styled from 'styled-components';
import { 
  RadarChart, 
  PolarGrid, 
  PolarAngleAxis, 
  PolarRadiusAxis, 
  Radar, 
  Tooltip, 
  ResponsiveContainer 
} from 'recharts';
import { useSharedState } from '../services/SharedStateContext';

const ControlsContainer = styled.div`
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1rem;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  margin-bottom: 1rem;
  height: 100%;
`;

const AgentBadge = styled.div`
  background-color: rgba(100, 108, 255, 0.3);
  border: 1px solid #646cff;
  color: white;
  border-radius: 4px;
  padding: 0.3rem 0.6rem;
  margin: 0 auto 0.5rem auto;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
`;

const AgentDot = styled.div`
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background-color: #646cff;
`;

const ChartContainer = styled.div`
  flex: 1;
  min-height: 300px;
  width: 100%;
`;

const Title = styled.h3`
  color: #fff;
  margin: 0 0 1rem 0;
  text-align: center;
`;

const Subtitle = styled.div`
  color: #aaa;
  font-size: 0.9rem;
  text-align: center;
  margin-bottom: 0.5rem;
`;

const Values = styled.div`
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  margin-top: 1rem;
`;

const ValueItem = styled.div`
  display: flex;
  align-items: center;
  margin: 0.5rem;
`;

const ValueLabel = styled.span`
  color: #fff;
  margin-right: 0.5rem;
`;

const ValueText = styled.span`
  font-weight: bold;
`;

const LegendContainer = styled.div`
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  margin-top: 0.5rem;
  gap: 0.5rem;
`;

const LegendItem = styled.div`
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 0.7rem;
  color: #ccc;
`;

const LegendColor = styled.div<{ $bgColor: string }>`
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: ${props => props.$bgColor};
`;

// Define Ekman emotions interface
interface Emotions {
  ANGER: number;
  CONTEMPT: number;
  DISGUST: number;
  ENJOYMENT: number;
  FEAR: number;
  SADNESS: number;
  SURPRISE: number;
}

interface EmotionControlsProps {
  emotions?: Emotions;
  onEmotionsChange?: (emotions: Emotions) => void;
}

// Color mapping for emotions (matching HABMSentiments)
const emotionColors = {
  ANGER: '#FF0000',     // Red
  CONTEMPT: '#A020F0',  // Purple
  DISGUST: '#32CD32',   // Green
  ENJOYMENT: '#FFD700',  // Gold/Yellow
  FEAR: '#800080',      // Dark Purple
  SADNESS: '#1E90FF',   // Blue
  SURPRISE: '#FFA500'   // Orange
};

// Define emotion abbreviations to ensure unique labels
const emotionShortNames: Record<keyof Emotions, string> = {
  ANGER: 'ANG',
  CONTEMPT: 'CNT',
  DISGUST: 'DSG',
  ENJOYMENT: 'ENJ',
  FEAR: 'FER',
  SADNESS: 'SAD',
  SURPRISE: 'SUR'
};

const CustomizedShape = (props: any) => {
  const { cx, cy, payload, emotion, value, index } = props;
  // Get emotion color
  const emotionKey = payload.subject as keyof typeof emotionColors;
  const color = emotionColors[emotionKey];
  
  return (
    <g>
      <circle 
        cx={props.cx} 
        cy={props.cy} 
        r={5} 
        fill={color} 
        stroke="white" 
        strokeWidth={1} 
      />
    </g>
  );
};

function EmotionControls({ emotions, onEmotionsChange }: EmotionControlsProps) {
  const { state } = useSharedState();
  const [calculatedEmotions, setCalculatedEmotions] = React.useState<Emotions>({
    ANGER: 0,
    CONTEMPT: 0,
    DISGUST: 0,
    ENJOYMENT: 0,
    FEAR: 0,
    SADNESS: 0,
    SURPRISE: 0
  });
  
  const [dataLoaded, setDataLoaded] = React.useState(false);
  
  // Calculate emotions for display - always show aggregate data for all agents
  React.useEffect(() => {
    if (!state.simulationData?.agents || state.simulationData.agents.length === 0) {
      console.log("No simulation data available");
      setDataLoaded(false);
      return;
    }
    
    console.log("Calculating aggregate emotions for all agents");
    // Initialize counters for each emotion
    const emotionSums: Emotions = {
      ANGER: 0,
      CONTEMPT: 0,
      DISGUST: 0,
      ENJOYMENT: 0,
      FEAR: 0,
      SADNESS: 0,
      SURPRISE: 0
    };
    
    let agentCount = 0;
    let processedAgents = 0;
    
    // Sum up the mood vectors across all agents
    state.simulationData.agents.forEach(agent => {
      // Make sure current step exists in the agent's mood vector array
      const step = Math.min(state.currentStep, agent.mood_vector.length - 1);
      if (step < 0 || !agent.mood_vector[step]) {
        return; // Skip agents without mood data for this step
      }
      
      const moodVector = agent.mood_vector[step];
      processedAgents++;
      
      // Skip invalid mood vectors
      if (!Array.isArray(moodVector) || moodVector.length !== 7) {
        console.log(`Invalid mood vector for agent ${agent.agent_id}:`, moodVector);
        return;
      }
      
      // Add each emotion value to the running sum
      emotionSums.ANGER += moodVector[0] || 0;
      emotionSums.CONTEMPT += moodVector[1] || 0;
      emotionSums.DISGUST += moodVector[2] || 0;
      emotionSums.ENJOYMENT += moodVector[3] || 0;
      emotionSums.FEAR += moodVector[4] || 0;
      emotionSums.SADNESS += moodVector[5] || 0;
      emotionSums.SURPRISE += moodVector[6] || 0;
      
      agentCount++;
    });
    
    console.log(`Processed ${processedAgents} agents, valid data for ${agentCount} agents`);
    
    // Calculate the average for each emotion if we have agents
    if (agentCount > 0) {
      const avgEmotions: Emotions = {
        ANGER: emotionSums.ANGER / agentCount,
        CONTEMPT: emotionSums.CONTEMPT / agentCount,
        DISGUST: emotionSums.DISGUST / agentCount,
        ENJOYMENT: emotionSums.ENJOYMENT / agentCount,
        FEAR: emotionSums.FEAR / agentCount,
        SADNESS: emotionSums.SADNESS / agentCount,
        SURPRISE: emotionSums.SURPRISE / agentCount
      };
      
      console.log("Average emotions:", avgEmotions);
      setCalculatedEmotions(avgEmotions);
      setDataLoaded(true);
    } else {
      console.log("No valid agents with mood data found");
      setDataLoaded(false);
    }
  }, [state.simulationData, state.currentStep]);
  
  // Use the provided emotions, calculated emotions, or state emotions
  const displayEmotions = emotions || calculatedEmotions;
  
  // Create separate data for each emotion value to display properly
  const chartData = [
    { subject: 'ANGER', value: displayEmotions.ANGER, fullMark: 1, color: emotionColors.ANGER, shortName: emotionShortNames.ANGER },
    { subject: 'CONTEMPT', value: displayEmotions.CONTEMPT, fullMark: 1, color: emotionColors.CONTEMPT, shortName: emotionShortNames.CONTEMPT },
    { subject: 'DISGUST', value: displayEmotions.DISGUST, fullMark: 1, color: emotionColors.DISGUST, shortName: emotionShortNames.DISGUST },
    { subject: 'ENJOYMENT', value: displayEmotions.ENJOYMENT, fullMark: 1, color: emotionColors.ENJOYMENT, shortName: emotionShortNames.ENJOYMENT },
    { subject: 'FEAR', value: displayEmotions.FEAR, fullMark: 1, color: emotionColors.FEAR, shortName: emotionShortNames.FEAR },
    { subject: 'SADNESS', value: displayEmotions.SADNESS, fullMark: 1, color: emotionColors.SADNESS, shortName: emotionShortNames.SADNESS },
    { subject: 'SURPRISE', value: displayEmotions.SURPRISE, fullMark: 1, color: emotionColors.SURPRISE, shortName: emotionShortNames.SURPRISE }
  ];

  // Handle radar chart click
  const handleRadarClick = (dataPoint: any) => {
    if (!onEmotionsChange || !dataPoint || !dataPoint.payload) return;
    
    const emotionKey = dataPoint.payload.subject as keyof Emotions;
    const newValue = (displayEmotions[emotionKey] || 0) + 0.1 > 1 ? 0 : (displayEmotions[emotionKey] || 0) + 0.1;
    
    onEmotionsChange({
      ...displayEmotions,
      [emotionKey]: newValue
    });
  };

  return (
    <ControlsContainer>
      <Title>Population Emotion Distribution</Title>
      <Subtitle>Current Step: {state.currentStep}</Subtitle>
      
      <ChartContainer>
        {!dataLoaded ? (
          <div style={{ color: "#aaa", textAlign: "center", marginTop: "30px" }}>
            Loading emotion data...
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart cx="50%" cy="50%" outerRadius="70%" data={chartData}>
              <PolarGrid gridType="polygon" stroke="#444" />
              <PolarAngleAxis 
                dataKey="shortName" 
                tick={({ payload, x, y, cx, cy, ...rest }) => {
                  const emotion = payload.subject;
                  const color = payload.color;
                  return (
                    <g transform={`translate(${x},${y})`}>
                      <text
                        x={0}
                        y={0}
                        textAnchor="middle"
                        fill={color}
                        fontWeight="bold"
                        fontSize={11}
                        dy={3}
                      >
                        {payload.shortName}
                      </text>
                    </g>
                  );
                }}
              />
              <PolarRadiusAxis domain={[0, 1]} axisLine={false} tick={{ fill: '#fff' }} />
              <Tooltip 
                contentStyle={{ backgroundColor: '#333', borderColor: '#555' }} 
                formatter={(value: number, name: string, props: any) => {
                  const { payload } = props;
                  const emotion = payload.subject;
                  const color = payload.color;
                  return [
                    value.toFixed(2),
                    emotion,
                    <div style={{ backgroundColor: color, width: '10px', height: '10px', display: 'inline-block', marginRight: '5px' }}></div>
                  ];
                }}
              />
              <Radar
                name="Emotion Levels"
                dataKey="value"
                stroke="rgba(100, 108, 255, 0.8)"
                fill="rgba(100, 108, 255, 0.5)"
                fillOpacity={0.5}
                dot={(props: any) => {
                  const emotionKey = props.payload.subject as keyof typeof emotionColors;
                  return (
                    <circle 
                      key={`dot-${props.payload?.subject || ''}-${props.index || Math.random()}`}
                      cx={props.cx} 
                      cy={props.cy} 
                      r={5} 
                      fill={emotionColors[emotionKey]} 
                      stroke="white" 
                      strokeWidth={1} 
                    />
                  );
                }}
                activeDot={{ r: 8, strokeWidth: 2 }}
                onClick={handleRadarClick}
              />
            </RadarChart>
          </ResponsiveContainer>
        )}
      </ChartContainer>

      <LegendContainer>
        {chartData.map(item => (
          <LegendItem key={item.subject}>
            <LegendColor $bgColor={item.color} />
            <span>{item.shortName}</span>
          </LegendItem>
        ))}
      </LegendContainer>
      
      <Values>
        {Object.entries(displayEmotions).map(([emotion, value]) => (
          <ValueItem key={emotion}>
            <ValueLabel>{emotion}:</ValueLabel>
            <ValueText style={{ color: emotionColors[emotion as keyof typeof emotionColors] }}>
              {value.toFixed(2)}
            </ValueText>
          </ValueItem>
        ))}
      </Values>
    </ControlsContainer>
  );
}

export default EmotionControls; 