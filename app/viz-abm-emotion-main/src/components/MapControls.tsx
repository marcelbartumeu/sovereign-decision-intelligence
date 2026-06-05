import styled from 'styled-components';

// Control panel components
export const ControlPanel = styled.div`
  position: absolute;
  top: 10px;
  right: 10px;
  background: rgba(0, 0, 0, 0.7);
  padding: 12px;
  border-radius: 4px;
  z-index: 10;
  display: flex;
  flex-direction: column;
  gap: 8px;
`;

export interface ControlButtonProps {
  active?: boolean;
}

export const ControlButton = styled.button<ControlButtonProps>`
  background: ${props => props.active ? 'rgba(65, 105, 225, 0.8)' : 'rgba(40, 40, 40, 0.8)'};
  color: white;
  border: none;
  padding: 8px 12px;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s;
  
  &:hover {
    background: ${props => props.active ? 'rgba(65, 105, 225, 0.9)' : 'rgba(60, 60, 60, 0.8)'};
  }
  
  span {
    font-size: 0.9rem;
  }
`; 