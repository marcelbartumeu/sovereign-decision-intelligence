import { useState, useEffect } from 'react';
import styled from 'styled-components';
import HeadEmotionVisualization from './HeadEmotionVisualization';

const Container = styled.div`
  background: #111;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
  height: 100%;
`;

const ContentWrapper = styled.div<{ $isVisible: boolean; $isTransitioning: boolean }>`
  position: absolute;
  inset: 0;
  opacity: ${props => props.$isVisible ? 1 : 0};
  transform: ${props => 
    props.$isTransitioning 
      ? props.$isVisible 
        ? 'scale(1)' 
        : 'scale(0.95)'
      : 'scale(1)'
  };
  transition: all 2s ease-in-out;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
`;

const VideoWrapper = styled.div`
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  
  video {
    width: 100%;
    height: 100%;
    border-radius: 8px;
    object-fit: contain;
  }
`;

const VisualizationWrapper = styled.div`
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
`;

interface AgentVisualizationToggleProps {
  videoPath: string;
  emotion: string;
  moodVector?: number[];
}

function AgentVisualizationToggle({ videoPath, emotion, moodVector }: AgentVisualizationToggleProps) {
  const [showVideo, setShowVideo] = useState(true);
  const [isTransitioning, setIsTransitioning] = useState(false);

  useEffect(() => {
    const cycleVisualization = () => {
      setIsTransitioning(true);
      
      setTimeout(() => {
        setShowVideo(prev => !prev);
        setIsTransitioning(false);
      }, 2000); // 2 seconds transition
    };

    // Start the cycle
    const interval = setInterval(cycleVisualization, 5000); // 3 seconds display + 2 seconds transition

    return () => clearInterval(interval);
  }, []);

  return (
    <Container>
      {/* Video Content */}
      <ContentWrapper $isVisible={showVideo} $isTransitioning={isTransitioning}>
        <VideoWrapper>
          <video autoPlay loop muted key={videoPath}>
            <source src={videoPath} type="video/mp4" />
            Your browser does not support the video tag.
          </video>
        </VideoWrapper>
      </ContentWrapper>

      {/* Emotion Visualization Content */}
      <ContentWrapper $isVisible={!showVideo} $isTransitioning={isTransitioning}>
        <VisualizationWrapper>
          <HeadEmotionVisualization 
            emotion={emotion} 
            moodVector={moodVector}
          />
        </VisualizationWrapper>
      </ContentWrapper>
    </Container>
  );
}

export default AgentVisualizationToggle;