import { useEffect, useMemo, useState, useRef } from 'react';
import styled from 'styled-components';
import AgentVisualizationToggle from '../components/AgentVisualizationToggle';
import { useSharedState } from '../services/SharedStateContext';
import { SharedControlPanel } from '../components/SharedControlPanel';

const Container = styled.div`
	display: flex;
	flex-direction: column;
	height: 100vh;
	background: rgb(0, 0, 0);
	font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
	color: #fff;
	overflow: hidden;
`;

const InfoRow = styled.div`
	flex: 1;
	display: grid;
	grid-template-columns: repeat(2, minmax(0, 1fr));
	gap: 20px;
	padding: 10px 20px 20px 20px;
	min-height: 0;
`;

const Card = styled.div`
	background: rgba(0, 0, 0, 0.8);
	border-radius: 12px;
	padding: 20px;
	display: flex;
	flex-direction: column;
	overflow: hidden;
	min-height: 0;
`;

const TopLayout = styled.div`
	flex: 2.6;
	display: grid;
	grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr) minmax(0, 1fr);
	gap: 20px;
	padding: 20px 20px 10px 20px;
	min-height: 0;
`;

const ChatColumn = styled.div`
	display: flex;
	flex-direction: column;
	gap: 20px;
	height: 100%;
	min-height: 0;
`;

const VideoCard = styled(Card)`
	height: 100%;
`;

const ChatCard = styled(Card)`
	flex: 1;
	min-height: 0;
	background-image: none;
	box-shadow: 0 12px 28px rgba(0, 0, 0, 0.35);
	margin-top: 18px;
	overflow: visible;
`;

const AgentName = styled.h2`
	margin: 0 0 16px 0;
	font-size: 2.4rem;
	font-weight: 300;
	letter-spacing: -0.3px;
`;

const InfoList = styled.ul`
	list-style: none;
	padding: 0;
	margin: 0;
	font-size: 1.1rem;
	line-height: 1.9rem;
`;

const InfoItem = styled.li`
	display: flex;
	justify-content: space-between;
	color: rgba(255, 255, 255, 0.9);
`;

const InfoLabel = styled.span`
	font-weight: 500;
	margin-right: 8px;
	color: #fff;
`;

const MessageList = styled.div`
	flex: 1;
	overflow-y: auto;
	padding-right: 10px;

	&::-webkit-scrollbar {
		width: 6px;
	}

	&::-webkit-scrollbar-track {
		background: rgba(255, 255, 255, 0.1);
		border-radius: 3px;
	}

	&::-webkit-scrollbar-thumb {
		background: rgba(100, 108, 255, 0.6);
		border-radius: 3px;
	}

	&::-webkit-scrollbar-thumb:hover {
		background: rgba(100, 108, 255, 0.8);
	}
`;

const MessageRow = styled.div<{ $align: 'flex-start' | 'flex-end' }>`
	display: flex;
	justify-content: ${props => props.$align};
	margin-bottom: 12px;
`;

const MessageBubble = styled.div<{
	$bg: string;
	$align: 'left' | 'right';
	$border: string;
	$text: string;
}>`
	background: ${props => props.$bg};
	border: 1px solid ${props => props.$border};
	border-radius: 16px;
	padding: 12px 16px;
	max-width: 85%;
	font-size: 1rem;
	line-height: 1.5;
	color: ${props => props.$text};
	position: relative;
	box-shadow: 0 10px 20px rgba(0, 0, 0, 0.25);

	&::before,
	&::after {
		content: '';
		position: absolute;
		top: 50%;
		transform: translateY(-50%);
		border-style: solid;
		border-color: transparent;
	}

	&::before {
		border-width: 9px;
		${props => props.$align === 'left'
			? `left: -18px; border-right-color: ${props.$border};`
			: `right: -18px; border-left-color: ${props.$border};`}
	}

	&::after {
		border-width: 8px;
		${props => props.$align === 'left'
			? `left: -16px; border-right-color: ${props.$bg};`
			: `right: -16px; border-left-color: ${props.$bg};`}
	}
`;

const MessageMeta = styled.div<{ $align: 'left' | 'right'; $color: string }>`
	font-size: 0.8rem;
	color: ${props => props.$color};
	margin-bottom: 6px;
	text-align: ${props => (props.$align === 'left' ? 'left' : 'right')};
`;

const ConversationLegend = styled.div`
	display: flex;
	justify-content: space-between;
	align-items: center;
	margin-bottom: 12px;
	font-size: 0.9rem;
	color: rgba(255, 255, 255, 0.7);
`;

const LegendItem = styled.div<{ $align: 'left' | 'right' }>`
	display: flex;
	align-items: center;
	gap: 8px;
	flex-direction: ${props => (props.$align === 'left' ? 'row' : 'row-reverse')};
	text-transform: uppercase;
	letter-spacing: 0.8px;
	font-size: 0.75rem;
`;

const LegendDot = styled.span<{ $color: string }>`
	width: 12px;
	height: 12px;
	border-radius: 50%;
	background: ${props => props.$color};
	box-shadow: 0 0 12px ${props => props.$color};
`;

type ConversationMessage = {
	agentId: string;
	step: number;
	text: string;
	key: string;
};

type AgentProfile = {
	age: number | string;
	personality: string;
	occupation: string;
};

const colorToEkman: Record<string, string> = {
	red: 'Anger',
	purple: 'Insecure',
	blue: 'Energize',
	orange: 'Stress',
	green: 'Calm'
};

const agentProfiles: Record<string, AgentProfile> = {
	Carlos: {
		age: 56,
		personality: 'Extroverted',
		occupation: 'Teacher'
	},
	Elena: {
		age: 54,
		personality: 'Introverted',
		occupation: 'Doctor'
	}
};

const PRIMARY_AGENT_IDS = ['Carlos', 'Elena'] as const;

const getVideoEmotion = (moodVector?: number[]) => {
	if (!moodVector || moodVector.length < 3) {
		return 'happy';
	}

	const [happy, angry, sad] = [moodVector[0], moodVector[1], moodVector[2]];

	if (sad >= happy && sad >= angry) {
		return 'sad';
	}
	if (angry >= happy && angry >= sad) {
		return 'angry';
	}

	return 'happy';
};

const formatLabel = (value: string) => (value ? value.charAt(0).toUpperCase() + value.slice(1) : value);

const AGENT_THEMES: Record<string, {
	align: 'left' | 'right';
	bubble: string;
	border: string;
	text: string;
	meta: string;
}> = {
	Carlos: {
		align: 'left',
		bubble: 'rgba(100, 108, 255, 0.18)',
		border: 'rgba(100, 108, 255, 0.6)',
		text: '#eef0ff',
		meta: '#a8acff'
	},
	Elena: {
		align: 'right',
		bubble: 'rgba(76, 201, 91, 0.2)',
		border: 'rgba(76, 201, 91, 0.6)',
		text: '#e6ffe9',
		meta: '#9ff5b1'
	}
};

const DEFAULT_THEME = {
	align: 'left' as const,
	bubble: 'rgba(255, 255, 255, 0.12)',
	border: 'rgba(255, 255, 255, 0.25)',
	text: '#f5f5f5',
	meta: '#b5b5b5'
};

interface CombinedChatPanelProps {
	agentIds: string[];
}

function CombinedChatPanel({ agentIds }: CombinedChatPanelProps) {
	const { state } = useSharedState();
	const [messages, setMessages] = useState<ConversationMessage[]>([]);
	const messagesEndRef = useRef<HTMLDivElement | null>(null);

	const agentKey = agentIds.join('|');
	const uniqueAgentIds = useMemo(() => Array.from(new Set(agentIds)), [agentKey]);
	const activeAgentIds = uniqueAgentIds.length ? uniqueAgentIds : Array.from(PRIMARY_AGENT_IDS);

	const stepMessages = useMemo(() => {
		if (!state.simulationData?.agents) {
			return [] as ConversationMessage[];
		}

		const collected: ConversationMessage[] = [];

		activeAgentIds.forEach(agentId => {
			const agent = state.simulationData!.agents.find(a => a.agent_id === agentId);
			if (!agent || !agent.conversation || !agent.conversation_timestamps) {
				return;
			}
			agent.conversation_timestamps.forEach((timestamp, index) => {
				if (timestamp === state.currentStep) {
					collected.push({
						agentId,
						step: timestamp,
						text: agent.conversation[index],
						key: `${agentId}-${timestamp}-${index}`
					});
				}
			});
		});

		collected.sort((a, b) => {
			if (a.step === b.step) {
				return a.agentId.localeCompare(b.agentId);
			}
			return a.step - b.step;
		});

		return collected;
	}, [state.simulationData, state.currentStep, agentKey]);

	useEffect(() => {
		setMessages([]);
	}, [agentKey]);

	useEffect(() => {
		if (state.currentStep === 0) {
			setMessages([]);
		}
	}, [state.currentStep]);

	useEffect(() => {
		if (!stepMessages.length) {
			return;
		}

		setMessages(prev => {
			const combined = [...prev];
			stepMessages.forEach(message => {
				if (!combined.some(existing => existing.key === message.key)) {
					combined.push(message);
				}
			});

			const maxItems = 200;
			return combined.slice(-maxItems);
		});
	}, [stepMessages]);

	useEffect(() => {
		messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
	}, [messages]);

	return (
		<ChatCard>
			<ConversationLegend>
				{activeAgentIds.map(agentId => {
					const theme = AGENT_THEMES[agentId] || DEFAULT_THEME;
					return (
						<LegendItem key={agentId} $align={theme.align}>
							<LegendDot $color={theme.border} />
							<span>Agent {agentId}</span>
						</LegendItem>
					);
				})}
			</ConversationLegend>
			<MessageList>
				{!messages.length && (
					<div style={{ textAlign: 'center', color: '#777', marginTop: '20px' }}>
						Waiting for {activeAgentIds.join(' & ')}...
					</div>
				)}
				{messages.map(message => {
					const theme = AGENT_THEMES[message.agentId] || DEFAULT_THEME;
					const alignment = theme.align === 'left' ? 'flex-start' : 'flex-end';
					return (
						<MessageRow key={message.key} $align={alignment}>
							<MessageBubble
								$bg={theme.bubble}
								$align={theme.align}
								$border={theme.border}
								$text={theme.text}
							>
								<MessageMeta $align={theme.align} $color={theme.meta}>
									Agent {message.agentId} · Step {message.step}
								</MessageMeta>
								<div>{message.text}</div>
							</MessageBubble>
						</MessageRow>
					);
				})}
				<div ref={messagesEndRef} />
			</MessageList>
		</ChatCard>
	);
}

type DualAgent = {
	id: string;
	displayEmotion: string;
	videoEmotion: string;
	moodVector?: number[];
	videoPath: string;
	ekmanEmotion: string;
	profile: AgentProfile;
	isPlaceholder?: boolean;
};

function DualVisualizationView() {
	const { state, loadSimulationData } = useSharedState();

	useEffect(() => {
		loadSimulationData();
			// eslint-disable-next-line react-hooks/exhaustive-deps
	}, []);

	const agents = useMemo<DualAgent[]>(() => {
		return PRIMARY_AGENT_IDS.map(id => {
			const agentData = state.simulationData?.agents?.find(agent => agent.agent_id === id);
			const profile = agentProfiles[id] || {
				age: '-',
				personality: 'Unknown',
				occupation: 'Unknown'
			};

			if (!agentData) {
				return {
					id,
					displayEmotion: 'Calm',
					videoEmotion: 'happy',
					videoPath: `/faces/${id}/happy.mp4`,
					ekmanEmotion: 'Calm',
					profile,
					isPlaceholder: true
				};
			}

			const moodVector = agentData.mood_vector && agentData.mood_vector.length > 0
				? agentData.mood_vector[Math.min(state.currentStep, agentData.mood_vector.length - 1)]
				: undefined;

			const emotionColor = agentData.emotion && agentData.emotion.length > 0
				? agentData.emotion[Math.min(state.currentStep, agentData.emotion.length - 1)]
				: undefined;

			const displayEmotion = emotionColor ? colorToEkman[emotionColor] || 'Calm' : 'Calm';
			const videoEmotion = getVideoEmotion(moodVector);

			return {
				id,
				moodVector,
				displayEmotion,
				videoEmotion,
				videoPath: `/faces/${id}/${videoEmotion}.mp4`,
				ekmanEmotion: displayEmotion,
				profile,
				isPlaceholder: false
			};
		});
	}, [state.simulationData, state.currentStep]);

	const leftAgent = agents[0];
	const rightAgent = agents[1];

	return (
		<Container>
			<TopLayout>
				{leftAgent && (
					<VideoCard>
						<AgentName>Agent {leftAgent.id}</AgentName>
						{leftAgent.isPlaceholder ? (
							<div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#777' }}>
								Waiting for active conversation
							</div>
						) : (
							<div style={{ flex: 1, minHeight: 0 }}>
								<AgentVisualizationToggle
									videoPath={leftAgent.videoPath}
									emotion={leftAgent.displayEmotion}
									moodVector={leftAgent.moodVector}
								/>
							</div>
						)}
					</VideoCard>
				)}
				<ChatColumn>
					<CombinedChatPanel agentIds={agents.map(agent => agent.id)} />
				</ChatColumn>
				{rightAgent && (
					<VideoCard>
						<AgentName>Agent {rightAgent.id}</AgentName>
						{rightAgent.isPlaceholder ? (
							<div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#777' }}>
								Waiting for active conversation
							</div>
						) : (
							<div style={{ flex: 1, minHeight: 0 }}>
								<AgentVisualizationToggle
									videoPath={rightAgent.videoPath}
									emotion={rightAgent.displayEmotion}
									moodVector={rightAgent.moodVector}
								/>
							</div>
						)}
					</VideoCard>
				)}
			</TopLayout>

			<InfoRow>
				{agents.map(agent => (
					<Card key={`${agent.id}-info`}>
						<AgentName>Agent {agent.id}</AgentName>
						<InfoList>
							<InfoItem>
								<InfoLabel>Age</InfoLabel>
								<span>{agent.profile.age}</span>
							</InfoItem>
							<InfoItem>
								<InfoLabel>Personality</InfoLabel>
								<span>{agent.profile.personality}</span>
							</InfoItem>
							<InfoItem>
								<InfoLabel>Occupation</InfoLabel>
								<span>{agent.profile.occupation}</span>
							</InfoItem>
							<InfoItem>
								<InfoLabel>Current Mood</InfoLabel>
								<span>{agent.isPlaceholder ? '-' : agent.displayEmotion}</span>
							</InfoItem>
							<InfoItem>
								<InfoLabel>Video Focus</InfoLabel>
								<span>{agent.isPlaceholder ? '-' : formatLabel(agent.videoEmotion)}</span>
							</InfoItem>
						</InfoList>
					</Card>
				))}
			</InfoRow>

			<SharedControlPanel />
		</Container>
	);
}

export default DualVisualizationView;

