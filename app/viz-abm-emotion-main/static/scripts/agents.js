import { LockCounter } from './lock-counter.js'

export function createAgent(
    agentId, agentConfig, circleBase, circleEmotion, 
    circleTransport, agentCoordinate, actualH3Index
){
    return {
        "agentType": agentConfig.type,
        "drawElement": circleBase,
        "emotionCircle": circleEmotion,
        "transportCircle": circleTransport,
        "isInteractiveTransportMethod": true,
        "lastCoordinate": agentCoordinate,
        "lastH3Index": actualH3Index,
        "interactionLock": new LockCounter(agentId),
        "inAreaOfInterest": undefined,
        "alreadyInteracted": new Set([agentId])
    }
}