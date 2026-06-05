const BASE_URL = window.location.origin;

export async function getInitAgents(){
    let initializationData = await fetch(BASE_URL + '/init', {
        method: 'GET'
    });
    return await initializationData.json();
}

export async function getNewAgentInfo(agentId, agentCircles, withH3Hexagons){
    let agentLastCoordinate = agentCircles[agentId].lastCoordinate;
    let newAgentInfoData = await fetch(
        BASE_URL + '/agent/'+ agentId +'/move?' + new URLSearchParams({
            "actualLat": agentLastCoordinate.lat,
            "actualLong": agentLastCoordinate.lng,
            "withH3Hexagons": withH3Hexagons
        }).toString(), {
        method: 'GET',
    });
    return await newAgentInfoData.json();
}


export async function notifyConversation(thisAgentId, thatAgentId, actualCoordinate){
    let conversationInfo = await fetch(
        BASE_URL + '/agent/'+ thisAgentId + '/conversation/' + thatAgentId + '?' + new URLSearchParams({
            "actualLat": actualCoordinate.lat,
            "actualLong": actualCoordinate.lng,
        }).toString(), {
        method: 'GET',
    });
    return await conversationInfo.json();
}

export async function notifyGroupConversationExited(thisAgentId){
    fetch(
        BASE_URL + '/agent/'+ thisAgentId + '/conversation-group/exit', {
        method: 'GET',
    });
}

export async function notifyNewArea(agentId, newAoI, actualCoordinate){
    let extra_args = {
        "actualLat": actualCoordinate.lat,
        "actualLong": actualCoordinate.lng,
    }
    if (newAoI !== undefined){
        extra_args["newAoI"] = newAoI
    }

    let areaResponseInfo = await fetch(BASE_URL + '/agent/'+ agentId + '/aoi?' 
        + new URLSearchParams(extra_args).toString(), {
        method: 'GET',
    });
    return await areaResponseInfo.json();
}