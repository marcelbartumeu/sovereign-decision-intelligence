const HEXAGON_STYLE = {
    "color": "orange",
    "weight": 2,
    "fillOpacity": 0.1
};
const ROUTE_STYLE = {
    "color": "blue",
    "weight": 4,
    "opacity": 0.3
};
const AOI_STYLE = {
    "weight": 2,
    "fillOpacity": 0.2
};

let agentHexagons = {};
let agentRoute = {};

let mapDivElement = document.getElementById('osm-map');
let map;


export function initializeMap(initialMapConfig){
    // Create Leaflet map on map element.
    map = L.map(mapDivElement, {center:[0, 0], zoom: 16, preferCanvas: true});

    // Add OSM tile layer to the Leaflet map.
    L.tileLayer('http://{s}.tile.osm.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    map.fitBounds([
        [initialMapConfig.lower_lat, initialMapConfig.lower_long],
        [initialMapConfig.upper_lat, initialMapConfig.upper_long]
    ]);
}

export function plotH3Hexagons(agentId, geoJSONHexagons){
    if (agentId in agentHexagons){
        agentHexagons[agentId].remove();
    }

    let h3Features = []
    for (const polyCoordinates of geoJSONHexagons){
        h3Features.push(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": polyCoordinates
                }
            }
        )
    }
    agentHexagons[agentId] = L.geoJSON(h3Features, {
        style: HEXAGON_STYLE
    }).addTo(map);
}

export function plotRoute(agentId, routeCoordinates){
    if (agentId in agentRoute){
        agentRoute[agentId].remove();
    }

    agentRoute[agentId] = L.geoJSON({
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": routeCoordinates
        }
    }, {
        style: ROUTE_STYLE
    }).addTo(map);
}

export function plotAgent(agentId, target, agentInfo, stopped_color){
    const agentType = agentInfo.type;
    const agentInitialEmotion = agentInfo.emotion;

    /*var circle = L.circleMarker(target, {
        radius: 3.5,
        color: agentType,
        fillOpacity: 0.9,
    }).addTo(map).bindPopup('Agent ID: ' + agentId);*/

    var circle_base = L.circle(target, {
        radius: 18,
        color: agentType,
        fillOpacity: 1,
    }).addTo(map).bindPopup('Agent ID: ' + agentId);
    
    var circle_emotion = L.circle(circle_base.getBounds().getNorthEast(), {
        radius: 4,
        color: agentInitialEmotion,
        fillOpacity: 0.9,
    }).addTo(map);

    var circle_transport = L.circle(circle_base.getBounds().getNorthWest(), {
        radius: 4,
        color: stopped_color,
        fillOpacity: 0.9,
    }).addTo(map);

    return [circle_base, circle_emotion, circle_transport]
}

export function plotAreasOfInterest(aoiConfig){
    for (const aoi of aoiConfig){
        if (aoi.hasOwnProperty('circle')){
            L.circle(aoi.circle.center, 
                Object.assign({}, 
                {
                    radius: aoi.circle.radius,
                    color: aoi.color
                }, AOI_STYLE)
            ).addTo(map);
        } else if (aoi.hasOwnProperty('polygon')){
            L.polygon([
                aoi.polygon.upper_left_coordinate,
                aoi.polygon.upper_right_coordinate,
                aoi.polygon.bottom_right_coordinate,
                aoi.polygon.bottom_left_coordinate,
                aoi.polygon.upper_left_coordinate,
            ], Object.assign({}, 
                {
                    color: aoi.color
                }, AOI_STYLE)
            ).addTo(map);
        }
    }
}

export function changeEmotionColor(emotionCircle, emotionColor){
    emotionCircle.setStyle({color: emotionColor})
}

export function changeTransportColor(transportCircle, transportColor){
    transportCircle.setStyle({color: transportColor})
}