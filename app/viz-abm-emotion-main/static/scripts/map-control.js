import { createAgent } from './agents.js';
import { 
    getInitAgents, getNewAgentInfo, 
    notifyConversation, notifyNewArea,
    notifyGroupConversationExited
} from './api-fetch.js';
import { 
    initializeAreasOfInterest, checkAreaOfInterest,
    getCoordinateH3Index, checkNotInteractedAgentsSameH3Index, 
    changeTransportSafely, notifyStopAgent
} from './nearest-neighbor.js';
import {
    initializeMap, plotRoute, plotAgent,
    plotAreasOfInterest, plotH3Hexagons,
    changeEmotionColor, changeTransportColor
} from './map-drawer.js';
import { logAgentIsInConversation, logAgentEndedConversation } from './logger.js';
import {
    SECONDS_PER_MINUTE, ANIMATION_MOVEMENT_SPEED, SIMULATION_SPEED,
    SHOW_H3_HEXAGONS,
    DEFAULT_STOPPED_TRANSPORT_NAME, DEFAULT_STOPPED_TRANSPORT_COLOR, 
    DEFAULT_STOPPED_TRANSPORT_INTERACTIVE
} from './consts.js';


// Where you want to render the map.
let agentCircles = {};
let interactiveTransportMethods;

let stoppedTransportName = DEFAULT_STOPPED_TRANSPORT_NAME;
let stoppedTransportColor = DEFAULT_STOPPED_TRANSPORT_COLOR;
let stoppedTransportInteractive = DEFAULT_STOPPED_TRANSPORT_INTERACTIVE;


function deg2rad(deg) {
    return deg * (Math.PI/180);
}

function getDistanceFromLatLonInKm(lat1,lon1,lat2,lon2) {
    var R = 6371; // Radius of the earth in km
    var dLat = deg2rad(lat2-lat1);  // deg2rad below
    var dLon = deg2rad(lon2-lon1); 
    var a = 
        Math.sin(dLat/2) * Math.sin(dLat/2) +
        Math.cos(deg2rad(lat1)) * Math.cos(deg2rad(lat2)) * 
        Math.sin(dLon/2) * Math.sin(dLon/2)
    ; 
    var c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a)); 
    var d = R * c; // Distance in km
    return d;
}

function configureTransports(stoppedTransportNameConfig, transportConfig){
    if (stoppedTransportNameConfig) {
        stoppedTransportName = stoppedTransportNameConfig;
    }

    if (transportConfig.hasOwnProperty(stoppedTransportName)){
        stoppedTransportColor = transportConfig[stoppedTransportName].color;
        stoppedTransportInteractive = transportConfig[stoppedTransportName].interactive;
    }

    interactiveTransportMethods = []
    for (const transport in transportConfig){
        if(transport !== stoppedTransportName && transportConfig[transport].interactive){
            interactiveTransportMethods.push(transport);
        }
    }
    console.log("Interactive transport methods: " + interactiveTransportMethods);
    interactiveTransportMethods = new Set(interactiveTransportMethods);
}

function addAgentMarker(initialAgentConfig){
    for (const agentId in initialAgentConfig) {
        const agentConfig = initialAgentConfig[agentId];
        const agentCoordinate = agentConfig.coordinate;
        
        // Target's GPS coordinates.
        var target = L.latLng(agentCoordinate.lat, agentCoordinate.lng);
        let [circleBase, circleEmotion, circleTransport] = plotAgent(agentId, target, agentConfig, stoppedTransportColor);
        
        let actualH3Index = getCoordinateH3Index(agentCoordinate);

        agentCircles[agentId] = createAgent(
            agentId, agentConfig, circleBase, circleEmotion, 
            circleTransport, agentCoordinate, actualH3Index
        )

        checkAreaOfInterest(agentId, actualH3Index, agentCircles[agentId]);
    }
}

function moveLayerCircles(agentCircleDict, lat, long){
    let agentCircle = agentCircleDict.drawElement;
    agentCircleDict.drawElement.setLatLng(L.latLng(lat, long));
    agentCircleDict.emotionCircle.setLatLng(agentCircle.getBounds().getNorthEast());
    agentCircleDict.transportCircle.setLatLng(agentCircle.getBounds().getNorthWest());
}

// NOTE: We do an assumption that the following case is not possible that happens, 
// if they always move in the best route and the map is sufficiently big so that 
// constant collisions in a same coordinate does not happen:
//   - Two agents interact during a route and end their interaction
//   - An agent reaches is destination and chooses a new route while the other agent has not reached yet its destination
//   - The agent with the renewed route collisions again with the agent that has not finished its route yet
// If this happens, the agent with the renewed route will stop while the other agent will not interact and continue.
// The way to solve this would make the simulation much slower (check always lock, even if not interacted), and this
// being a marginal case without huge simulation impact is not worth it
function startMovement(
    agentId, agentCircleDict, agentNewCoordinate, 
    diffLat, diffLong, simulationTime, resolveMovement
){
    const intervalId = setInterval(async () => {
        let circleLatLong = agentCircleDict.drawElement.getLatLng();
        let actualH3Index = getCoordinateH3Index(circleLatLong);
        const areaEntered = checkAreaOfInterest(agentId, actualH3Index, agentCircleDict);
        if (areaEntered){
            notifyNewArea(agentId, agentCircleDict.inAreaOfInterest, circleLatLong);
        }
        // Check if there has been contact with other agents and lock those who did not interact before
        let notAlreadyInteractedAgents = await checkNotInteractedAgentsSameH3Index(
            agentId, actualH3Index, agentCircles, agentCircleDict
        );
        
        // CASE 1: No contact with other agents that have not interacted before in the route
        if (notAlreadyInteractedAgents.length === 0){
            var newLat, newLong;

            if (diffLat == 0){
                newLat = agentNewCoordinate.lat;
            } else {
                newLat = circleLatLong.lat + (diffLat / simulationTime);
                if (
                    (diffLat < 0 && newLat < agentNewCoordinate.lat) ||
                    (diffLat > 0 && newLat > agentNewCoordinate.lat)
                ) {
                    newLat = agentNewCoordinate.lat;
                }
            }
            
            if (diffLong == 0){
                newLong = agentNewCoordinate.lng;
            } else {
                newLong = circleLatLong.lng + (diffLong / simulationTime);
            
                if (
                    (diffLong < 0 && newLong < agentNewCoordinate.lng) ||
                    (diffLong > 0 && newLong > agentNewCoordinate.lng)
                ) {
                    newLong = agentNewCoordinate.lng;
                }
            }
            
            if(
                newLat === agentNewCoordinate.lat && 
                newLong === agentNewCoordinate.lng
            ){
                // CASE: Coordinates given by OSRM are NaN (coordinates have no valid near route to move)
                moveLayerCircles(agentCircleDict, agentNewCoordinate.lat, agentNewCoordinate.lng);
                agentCircleDict.lastCoordinate = agentNewCoordinate;
                clearInterval(intervalId);
                resolveMovement();
            } else {
                moveLayerCircles(agentCircleDict, newLat, newLong)
            }
        // CASE 2: Contact has ocurred with other agent not interacted before: start conversation and stop moving
        } else {
            clearInterval(intervalId);

            for (const interactedAgentId of notAlreadyInteractedAgents){
                // 1. For each conversation lock this agent to wait for all conversation responses
                agentCircleDict.interactionLock.lock();
                
                logAgentIsInConversation(agentId, interactedAgentId);

                // 2. Call backend to notify conversation and wait for response
                notifyConversation(agentId, interactedAgentId, circleLatLong).then((response) => {
                    let thatAgent = agentCircles[interactedAgentId]

                    // 3. Add this agent to the interaction list of the other agent so he is notified of the
                    // agent that started the interaction
                    thatAgent.alreadyInteracted.add(agentId)

                    // 3. Unlock the other agent lock
                    thatAgent.interactionLock.unlock()

                    // 4. Unlock this agent lock to continue process
                    agentCircleDict.interactionLock.unlock();

                    logAgentEndedConversation(agentId, interactedAgentId);
                });
            }

            // 4. Wait my own lock in case there were new agents that started a conversation with me meanwhile
            // WARNING! Worst case scenario: I unlock and while creating new interval a new agent starts conversation
            //   - In this case, if conversation is at least longer than 20 ms there would be no problem as it will have enough time
            //     to detect new agent in next cycle and lock itself
            await agentCircleDict.interactionLock.accessLock()

            console.log("After this Agent " + agentId + " lock: " + agentCircleDict.interactionLock.lockCount)
            
            // So now agent is leaving of conversation group
            notifyGroupConversationExited(agentId);

            startMovement(agentId, agentCircleDict, agentNewCoordinate, diffLat, diffLong, simulationTime, resolveMovement)
        }
    }, SIMULATION_SPEED);
}

function moveAgent(agentId, agentCircleDict, agentNewCoordinate, transportMinutes){
    if(isNaN(transportMinutes)){
        transportMinutes = 1;
    }
    const simulationTime = (transportMinutes * SECONDS_PER_MINUTE) * (1000 / ANIMATION_MOVEMENT_SPEED);
    const agentLastCoordinate = agentCircleDict.lastCoordinate;
    const diffLat = agentNewCoordinate.lat - agentLastCoordinate.lat
    const diffLong = agentNewCoordinate.lng - agentLastCoordinate.lng

    return new Promise((resolve, reject) => {
        startMovement(agentId, agentCircleDict, agentNewCoordinate, diffLat, diffLong, simulationTime, resolve);
    });
}

async function updateAgentMarkers(agentId, agentInfoData){
    const agentCircleDict = agentCircles[agentId];
    const agentRoutingInfoData = agentInfoData.routingInfo;

    // CHANGE EMOTION COLOR
    const emotionColor = agentInfoData.emotionColor;
    changeEmotionColor(agentCircleDict.emotionCircle, emotionColor)

    if (agentInfoData.transportMethod == stoppedTransportName) {
        console.log("Agent ID " + agentId + " is stopping for " + agentInfoData.stopTime + " seconds...");
        await new Promise(r => setTimeout(r, parseInt(agentInfoData.stopTime) * 1000))
    } else {
        // CHANGE TRANSPORT METHOD
        await changeTransportSafely(agentCircleDict, interactiveTransportMethods.has(agentInfoData.transportMethod))
        //  - Verify that all conversations ended while stopped
        await agentCircleDict.interactionLock.accessLock()

        // CHANGE TRANSPORT COLOR
        const transportColor = agentInfoData.transportColor;
        changeTransportColor(agentCircleDict.transportCircle, transportColor);

        // ADD ROUTE REPRESENTATION
        const routeCoordinates = agentRoutingInfoData.routeCoordinates;
        const transportMinutes = agentRoutingInfoData.transportMinutes;
        const routeTotalDistance = agentRoutingInfoData.routeTotalDistance;
        console.log("Agent ID " + agentId + " Routes: " + routeCoordinates);

        plotRoute(agentId, routeCoordinates);

        for(let actualStop = 1; actualStop < routeCoordinates.length; actualStop++){
            let routeCoordinate = routeCoordinates[actualStop];
            // Route coordinates composed of [long, lat]
            let agentNewCoordinate = {
                lng: routeCoordinate[0],
                lat: routeCoordinate[1]
            }

            const distanceStep = getDistanceFromLatLonInKm(
                agentCircleDict.lastCoordinate.lat, agentCircleDict.lastCoordinate.lng, 
                agentNewCoordinate.lat, agentNewCoordinate.lng
            ) * 1000;
            const minutesCovered = distanceStep / routeTotalDistance;
            await moveAgent(agentId, agentCircleDict, agentNewCoordinate, transportMinutes * minutesCovered);
        }
        
        await notifyStopAgent(agentId, agentCircleDict, stoppedTransportInteractive);

        changeTransportColor(agentCircleDict.transportCircle, stoppedTransportColor);
    }
}

async function awaitAgentInfoUpdates(agentId){
    let agentInfoData = await getNewAgentInfo(agentId, agentCircles, SHOW_H3_HEXAGONS);
    if (SHOW_H3_HEXAGONS){
        plotH3Hexagons(agentId, agentInfoData.hexagons);
    }
    updateAgentMarkers(agentId, agentInfoData).then(() => { 
        awaitAgentInfoUpdates(agentId);
    });
}

async function main(){
    let initializationData = await getInitAgents();
    let initialMapBoundsConfig = initializationData.initialMapBoundsConfig;
    let initialMapAreasOfInterestConfig = initializationData.initialMapAreasOfInterestConfig;
    let initialAgentConfig = initializationData.initialAgentConfig;
    let transportConfig = initializationData.transportConfig;
    let stoppedTransportNameConfig = initializationData.stoppedTransportNameConfig;

    initializeMap(initialMapBoundsConfig);
    initializeAreasOfInterest(initialMapAreasOfInterestConfig);
    plotAreasOfInterest(initialMapAreasOfInterestConfig);
    addAgentMarker(initialAgentConfig);
    configureTransports(stoppedTransportNameConfig, transportConfig);

    for (const agentId in agentCircles){
        awaitAgentInfoUpdates(agentId);
    }   
}

main();