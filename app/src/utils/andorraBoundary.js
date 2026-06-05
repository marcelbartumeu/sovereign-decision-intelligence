import L from 'leaflet';

export function addAndorraBoundary(map) {
  fetch('/andorra_boundary.geojson')
    .then(r => r.json())
    .then(data => {
      L.geoJSON(data, {
        style: {
          color:       '#ffffff',
          weight:      2,
          opacity:     0.55,
          fillColor:   'transparent',
          fillOpacity: 0,
          dashArray:   '5 7',
          lineCap:     'round',
        },
        interactive: false,
      }).addTo(map);
    })
    .catch(() => {});
}
