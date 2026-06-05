import { logAgentEnteredAreaOfInterest, logAgentExitedAreaOfInterest } from './logger.js'
import { FILTER_CONVERSATIONS_BY_AGENT_TYPE } from './consts.js'

const H3_RESOLUTION = 12

let agentsH3Indeces = {}
let aoiH3Indeces = {}

function saveAgentH3Index(agentId, thisAgentCircleDict, actualH3Index){
    // Add agent to new actual H3 index
    if (agentsH3Indeces.hasOwnProperty(actualH3Index)){
        agentsH3Indeces[actualH3Index].add(agentId);
    } else {
        // We add agent as first to contact this H3 hex (NOTE: Set used for avoiding duplicates)
        agentsH3Indeces[actualH3Index] = new Set([agentId]);
    }

    // Remove agent from last index he was (if different to actual)
    if (thisAgentCircleDict.lastH3Index !== actualH3Index){
        agentsH3Indeces[thisAgentCircleDict.lastH3Index].delete(agentId);
        thisAgentCircleDict.lastH3Index = actualH3Index;
    }
}

export function initializeAreasOfInterest(initialMapAreasOfInterestConfig){
    for (const aoiConfig of initialMapAreasOfInterestConfig){
        let h3IndecesInArea = [];

        if (aoiConfig.hasOwnProperty('polygon')){
            h3IndecesInArea = h3.polygonToCells([
                aoiConfig.polygon.upper_left_coordinate,
                aoiConfig.polygon.upper_right_coordinate,
                aoiConfig.polygon.bottom_right_coordinate,
                aoiConfig.polygon.bottom_left_coordinate
            ], H3_RESOLUTION);
        } else if (aoiConfig.hasOwnProperty('circle')){
            h3IndecesInArea = h3.polygonToCells(
                aoiConfig.circle.polygonRep, 
            H3_RESOLUTION);
        }

        for (const h3Index of h3IndecesInArea){
            aoiH3Indeces[h3Index] = aoiConfig.name;
        }
    }
}

export function getCoordinateH3Index(coordinate){
    return h3.latLngToCell(coordinate.lat, coordinate.lng, H3_RESOLUTION);
}

export async function checkNotInteractedAgentsSameH3Index(agentId, actualH3Index, agentCircles, thisAgentCircleDict){
    let notAlreadyInteractedAgents = []
    let agentsInSameIndexWithInteractive = await navigator.locks.request("near-neighbor-search", async (lock) => {
        saveAgentH3Index(agentId, thisAgentCircleDict, actualH3Index);

        if (!thisAgentCircleDict.isInteractiveTransportMethod){
            // console.log('Agent ' + agentId + ' is in a non-interactive transport method. No interactions will be made.');
            return notAlreadyInteractedAgents;
        }

        // Check if interaction has ocurred before with this agent and is in interactive transport
        return Array.from(agentsH3Indeces[actualH3Index].values())
                    .filter(h3AgentId => agentCircles[h3AgentId].isInteractiveTransportMethod
                                            && !thisAgentCircleDict.alreadyInteracted.has(h3AgentId));
    });
    
    if (agentsInSameIndexWithInteractive.length != 0){
        if (FILTER_CONVERSATIONS_BY_AGENT_TYPE){
            // Check if agent is not the of the same type
            agentsInSameIndexWithInteractive = agentsInSameIndexWithInteractive.filter(
                (thatAgentId) => agentCircles[thatAgentId].agentType === thisAgentCircleDict.agentType
            )
        }
    
        for (const sameH3AgentId of agentsInSameIndexWithInteractive) {
            let thatAgentCircleDict = agentCircles[sameH3AgentId];
    
            // Update own agent interaction info (for no future interactions in the route)
            thisAgentCircleDict.alreadyInteracted.add(sameH3AgentId);
    
            // Update other agent interaction locks to wait for conversation to end
            thatAgentCircleDict.interactionLock.lock();
    
            // Add to not already interacted agents list
            notAlreadyInteractedAgents.push(sameH3AgentId);
        }
    }

    return notAlreadyInteractedAgents;
}

export function changeTransportSafely(agentCircleDict, newTransportMethodIsInteractive){
    return navigator.locks.request("near-neighbor-search", async (lock) => {
        agentCircleDict.isInteractiveTransportMethod = newTransportMethodIsInteractive;
    });
}

export async function notifyStopAgent(agentId, agentCircleDict, STOPPED_TRANSPORT_INTERACTIVE){
    agentCircleDict.alreadyInteracted = new Set([agentId])
    await changeTransportSafely(agentCircleDict, STOPPED_TRANSPORT_INTERACTIVE)
}

export function checkAreaOfInterest(agentId, actualH3Index, thisAgentCircleDict){
    let areaOfInterestInActualH3Index = aoiH3Indeces[actualH3Index]

    if (areaOfInterestInActualH3Index !== undefined){
        if (thisAgentCircleDict.inAreaOfInterest !== areaOfInterestInActualH3Index){
            thisAgentCircleDict.inAreaOfInterest = areaOfInterestInActualH3Index;
            logAgentEnteredAreaOfInterest(agentId, areaOfInterestInActualH3Index);
            return true;
        }
    } else {
        if (thisAgentCircleDict.inAreaOfInterest !== undefined){
            logAgentExitedAreaOfInterest(agentId, thisAgentCircleDict.inAreaOfInterest);
            thisAgentCircleDict.inAreaOfInterest = undefined;
            return true;
        }
    }

    return false;
}