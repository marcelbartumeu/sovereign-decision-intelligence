let conversationUlElement = document.getElementById('conversation-logger');
let aoiUlElement = document.getElementById('aoi-logger');

let dateFormatter = new Intl.DateTimeFormat("en-GB", {
    dateStyle: "long",
    timeStyle: "long"
})

function getDateFormatted(){
    const actualTime = new Date();
    return dateFormatter.format(actualTime) + ":  ";
}

export async function logAgentIsInConversation(thisAgentId, thatAgentId){
    const logText = "Agent " + thisAgentId + " started a conversation with agent " + thatAgentId;
    const timeText = getDateFormatted();

    var li = document.createElement("li");
    li.appendChild(document.createTextNode(timeText + logText));
    console.log(logText);

    conversationUlElement.prepend(li);
}

export async function logAgentEndedConversation(thisAgentId, thatAgentId){
    const logText = "Agent " + thisAgentId + " ended a conversation with agent " + thatAgentId;
    const timeText = getDateFormatted();

    var li = document.createElement("li");
    li.appendChild(document.createTextNode(timeText + logText));
    console.log(logText);

    conversationUlElement.prepend(li);
}


export async function logAgentEnteredAreaOfInterest(agentId, areaOfInterest){
    const logText = 'Agent ' + agentId + ' has entered the new area of interest ' + areaOfInterest;
    const timeText = getDateFormatted();

    var li = document.createElement("li");
    li.appendChild(document.createTextNode(timeText + logText));
    console.log(logText);

    aoiUlElement.prepend(li);
}

export async function logAgentExitedAreaOfInterest(agentId, areaOfInterest){
    const logText = 'Agent ' + agentId + ' has left the area of interest ' + areaOfInterest;
    const timeText = getDateFormatted();

    var li = document.createElement("li");
    li.appendChild(document.createTextNode(timeText + logText));
    console.log(logText);

    aoiUlElement.prepend(li);
}