import * as THREE from "three";
import { OrbitControls } from "jsm/controls/OrbitControls.js";
import getStarfield from "./src/getStarfield.js";

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(45, innerWidth / innerHeight, 0.1, 1000);
camera.position.set(0, 0, 4);
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(innerWidth, innerHeight);
renderer.setPixelRatio(window.devicePixelRatio);
document.body.appendChild(renderer.domElement);

const orbitCtrl = new OrbitControls(camera, renderer.domElement);
orbitCtrl.enableDamping = true;

const raycaster = new THREE.Raycaster();
const pointerPos = new THREE.Vector2();
const globeUV = new THREE.Vector2();
let pointerActive = false; // suppress the cursor glow until the user actually moves
let activeLocation = null; // currently-searched place (drives the on-globe label)
const _wp = new THREE.Vector3();
const YAXIS = new THREE.Vector3(0, 1, 0);
const warp = document.getElementById('warp');
let fly = null; // active fly-to-location animation state
const placeLabel       = document.getElementById('place-label');
const placeLabelName   = document.getElementById('place-label-name');
const placeLabelCoords = document.getElementById('place-label-coords');

function fmtCoords(lat, lon) {
  const ns = lat >= 0 ? 'N' : 'S';
  const ew = lon >= 0 ? 'E' : 'W';
  return `${Math.abs(lat).toFixed(2)}° ${ns}  ·  ${Math.abs(lon).toFixed(2)}° ${ew}`;
}

const textureLoader = new THREE.TextureLoader();
// Reveal the globe only once the night-lights + land-mask textures are ready,
// so it never flashes as a solid sphere on first load.
let texReady = 0;
const onTex = () => { if (++texReady >= 2 && typeof points !== 'undefined') points.visible = true; };
const starSprite = textureLoader.load("./src/circle.png");
const elevMap   = textureLoader.load("./src/01_earthbump1k.jpg");
const alphaMap  = textureLoader.load("./src/02_earthspec1k.jpg", onTex);
const lightsMap = textureLoader.load("./src/03_earthlights1k.jpg", onTex);

// Three.js IcosahedronGeometry UV: azimuth = atan2(-z,-x), lon=0° sits at x=-1.
// Correct lat/lon → 3D: x=-cos(lat)cos(lon), y=sin(lat), z=-cos(lat)sin(lon)
function latLonTo3D(lat, lon) {
  const lr = lat * Math.PI / 180;
  const lo = lon * Math.PI / 180;
  return new THREE.Vector3(
    -Math.cos(lr) * Math.cos(lo),
     Math.sin(lr),
    -Math.cos(lr) * Math.sin(lo)
  );
}

// Andorra: lat 42.5°N, lon 1.6°E
const ANDORRA_UV  = new THREE.Vector2(0.504, 0.264); // V = 0.5 - lat/180
const ANDORRA_3D  = latLonTo3D(42.5, 1.6);

const globeGroup = new THREE.Group();
globeGroup.position.y = -0.32; // sit the globe a little lower on screen
scene.add(globeGroup);

const geo = new THREE.IcosahedronGeometry(1, 16);
const mat = new THREE.MeshBasicMaterial({
  color: 0x2a4a63,
  wireframe: true,
  transparent: true,
  opacity: 0.07
 });
const globe = new THREE.Mesh(geo, mat);
globeGroup.add(globe);

const detail = 120;
const pointsGeo = new THREE.IcosahedronGeometry(1, detail);

const vertexShader = `
  uniform float size;
  uniform sampler2D elevTexture;
  uniform vec2 mouseUV;

  varying vec2 vUv;
  varying float vVisible;
  varying float vDist;

  void main() {
    vUv = uv;
    vec4 mvPosition = modelViewMatrix * vec4( position, 1.0 );
    float elv = texture2D(elevTexture, vUv).r;
    vec3 vNormal = normalMatrix * normal;
    vVisible = step(0.0, dot( -normalize(mvPosition.xyz), normalize(vNormal)));
    mvPosition.z += 0.35 * elv;

    float dist = distance(mouseUV, vUv);
    float zDisp = 0.0;
    float thresh = 0.04;
    if (dist < thresh) {
      zDisp = (thresh - dist) * 4.0;
    }
    vDist = dist;
    mvPosition.z += zDisp;

    gl_PointSize = size;
    gl_Position = projectionMatrix * mvPosition;
  }
`;
const fragmentShader = `
  uniform sampler2D lightsTexture;
  uniform sampler2D alphaTexture;

  varying vec2 vUv;
  varying float vVisible;
  varying float vDist;

  void main() {
    if (floor(vVisible + 0.1) == 0.0) discard;

    // Land mask keeps the dotted-continents shape (oceans transparent)
    float land   = 1.0 - texture2D(alphaTexture, vUv).r;
    // Night-time city lights
    float lights = texture2D(lightsTexture, vUv).r;
    float city   = smoothstep(0.07, 0.55, lights);

    vec3 base = vec3(0.12, 0.16, 0.23);   // faint cool landmass
    vec3 glow = vec3(1.00, 0.80, 0.42);   // warm city light
    vec3 color = base + glow * city * 1.4;
    float alpha = clamp(land + city * 0.45, 0.0, 1.0); // cities pop a little brighter

    // Cool cyan interaction glow under the cursor
    float thresh = 0.045;
    if (vDist < thresh) {
      float h = (thresh - vDist) / thresh;
      color = mix(color, vec3(0.55, 0.86, 1.0), h * 0.9);
      alpha = max(alpha, h * 0.85);
    }
    gl_FragColor = vec4(color, alpha);
  }
`;
const uniforms = {
  size: { type: "f", value: 3.7 },
  lightsTexture: { type: "t", value: lightsMap },
  elevTexture: { type: "t", value: elevMap },
  alphaTexture: { type: "t", value: alphaMap },
  mouseUV: { type: "v2", value: new THREE.Vector2(0.0, 0.0) },
};
const pointsMat = new THREE.ShaderMaterial({
  uniforms: uniforms,
  vertexShader,
  fragmentShader,
  transparent: true
});

const points = new THREE.Points(pointsGeo, pointsMat);
points.visible = false; // shown once textures load (see onTex)
globeGroup.add(points);
if (texReady >= 2) points.visible = true; // textures already cached

// Andorra ring marker — pulsing ring + dot, child of globeGroup so it rotates with the globe
const andorraRingGeo = new THREE.RingGeometry(0.022, 0.034, 32);
const andorraRingMat = new THREE.MeshBasicMaterial({ color: 0xff3333, side: THREE.DoubleSide, transparent: true, opacity: 0.9 });
const andorraRing = new THREE.Mesh(andorraRingGeo, andorraRingMat);
andorraRing.position.copy(ANDORRA_3D.clone().multiplyScalar(1.04));
andorraRing.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), ANDORRA_3D);
globeGroup.add(andorraRing);

const andorraDotGeo = new THREE.CircleGeometry(0.011, 16);
const andorraDotMat = new THREE.MeshBasicMaterial({ color: 0xff6666, side: THREE.DoubleSide });
const andorraDot = new THREE.Mesh(andorraDotGeo, andorraDotMat);
andorraDot.position.copy(ANDORRA_3D.clone().multiplyScalar(1.04));
andorraDot.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), ANDORRA_3D);
globeGroup.add(andorraDot);

// Hidden until the user searches for Andorra
andorraRing.visible = false;
andorraDot.visible  = false;

const hemiLight = new THREE.HemisphereLight(0xffffff, 0x080820, 3);
scene.add(hemiLight);

const stars = getStarfield({ numStars:4500, sprite: starSprite });
scene.add(stars);

function handleRaycast() {
  if (!pointerActive) { uniforms.mouseUV.value.set(-2, -2); return; }
  raycaster.setFromCamera(pointerPos, camera);
  const intersects = raycaster.intersectObjects([globe], false);
  if (intersects.length > 0) {
    globeUV.copy(intersects[0].uv);
  }
  uniforms.mouseUV.value = globeUV;
}

// ── Intro tween: globe settles in (scale + halo + spin easing to steady) ──────
const INTRO_MS = 2200;
const introStart = performance.now();
const easeOutCubic   = (t) => 1 - Math.pow(1 - t, 3);
const easeInOutCubic = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

// ── Fly-to-location: rotate the target to face us, dolly the camera in, fade out ──
function updateFly() {
  const k     = Math.min(1, (performance.now() - fly.t0) / fly.dur);
  const eRot  = easeInOutCubic(Math.min(1, k / 0.5));   // face the target during the first half
  const eZoom = k * k;                                  // accelerate inward
  const eFade = Math.max(0, (k - 0.35) / 0.65);         // darken after 35%

  globeGroup.rotation.y = fly.rot0 + (fly.rot1 - fly.rot0) * eRot;

  const aw  = fly.localPt.clone().applyAxisAngle(YAXIS, globeGroup.rotation.y).add(globeGroup.position);
  const dir = aw.clone().normalize();
  camera.position.copy(dir.multiplyScalar(aw.length() + (3.4 - 2.3 * eZoom)));
  camera.lookAt(aw);

  if (warp) warp.style.opacity = Math.min(1, eFade).toFixed(3);
  if (placeLabel) placeLabel.classList.remove('show');

  if (k >= 1 && !fly.done) {
    fly.done = true;
    window.parent.postMessage({ action: 'enterAndorra' }, '*');
  }
}

function animate() {
  requestAnimationFrame(animate);

  if (fly) { updateFly(); renderer.render(scene, camera); return; }

  const e = easeOutCubic(Math.min(1, (performance.now() - introStart) / INTRO_MS));
  globeGroup.scale.setScalar(0.84 + 0.16 * e);
  globeGroup.rotation.y += 0.0016 + 0.026 * (1 - e); // fast at first, eases to steady drift

  handleRaycast();
  orbitCtrl.update();

  // Pulse the Andorra ring
  const t = Date.now() / 1000;
  const pulse = 1.0 + 0.18 * Math.sin(t * 3.5);
  andorraRing.scale.setScalar(pulse);
  andorraRingMat.opacity = 0.55 + 0.4 * Math.sin(t * 3.5);

  // On-globe place label — follows the marker, hidden when it rotates to the far side
  if (placeLabel) {
    if (activeLocation && andorraRing.visible) {
      andorraRing.getWorldPosition(_wp);
      const toCam  = camera.position.clone().sub(_wp).normalize();
      const facing = _wp.clone().normalize().dot(toCam) > 0.12;
      if (facing) {
        const p = _wp.clone().project(camera);
        placeLabel.style.left = ((p.x * 0.5 + 0.5) * window.innerWidth) + 'px';
        placeLabel.style.top  = ((-p.y * 0.5 + 0.5) * window.innerHeight) + 'px';
        placeLabel.classList.add('show');
      } else {
        placeLabel.classList.remove('show');
      }
    } else {
      placeLabel.classList.remove('show');
    }
  }

  renderer.render(scene, camera);
};
animate();

let hoveringAndorra = false;

window.addEventListener('mousemove', (evt) => {
  pointerActive = true;
  pointerPos.set(
    (evt.clientX / window.innerWidth) * 2 - 1,
    -(evt.clientY / window.innerHeight) * 2 + 1
  );
  // Detect hover over Andorra for cursor change
  raycaster.setFromCamera(pointerPos, camera);
  const hits = raycaster.intersectObjects([globe], false);
  if (hits.length > 0) {
    const uv = hits[0].uv;
    const d  = Math.sqrt((uv.x - ANDORRA_UV.x) ** 2 + (uv.y - ANDORRA_UV.y) ** 2);
    hoveringAndorra = d < 0.04;
  } else {
    hoveringAndorra = false;
  }
  renderer.domElement.style.cursor = hoveringAndorra ? 'pointer' : 'default';
});

window.addEventListener('click', () => {
  if (hoveringAndorra) enterSimulation();
});

// ── Location database ────────────────────────────────────────────────────────

const LOCATIONS = [
  { name: 'andorra',      display: 'Andorra',           lat:  42.51,  lon:   1.52  },
  { name: 'amsterdam',    display: 'Amsterdam, NL',     lat:  52.37,  lon:   4.90  },
  { name: 'athens',       display: 'Athens, GR',        lat:  37.98,  lon:  23.73  },
  { name: 'barcelona',    display: 'Barcelona, ES',     lat:  41.39,  lon:   2.15  },
  { name: 'beijing',      display: 'Beijing, CN',       lat:  39.91,  lon: 116.39  },
  { name: 'berlin',       display: 'Berlin, DE',        lat:  52.52,  lon:  13.40  },
  { name: 'boston',       display: 'Boston, US',        lat:  42.36,  lon: -71.06  },
  { name: 'brussels',     display: 'Brussels, BE',      lat:  50.85,  lon:   4.35  },
  { name: 'buenos aires', display: 'Buenos Aires, AR',  lat: -34.60,  lon: -58.38  },
  { name: 'cairo',        display: 'Cairo, EG',         lat:  30.04,  lon:  31.24  },
  { name: 'cape town',    display: 'Cape Town, ZA',     lat: -33.93,  lon:  18.42  },
  { name: 'chicago',      display: 'Chicago, US',       lat:  41.88,  lon: -87.63  },
  { name: 'dubai',        display: 'Dubai, AE',         lat:  25.20,  lon:  55.27  },
  { name: 'dublin',       display: 'Dublin, IE',        lat:  53.33,  lon:  -6.25  },
  { name: 'hong kong',    display: 'Hong Kong, HK',     lat:  22.32,  lon: 114.17  },
  { name: 'istanbul',     display: 'Istanbul, TR',      lat:  41.01,  lon:  28.95  },
  { name: 'jakarta',      display: 'Jakarta, ID',       lat:  -6.21,  lon: 106.85  },
  { name: 'johannesburg', display: 'Johannesburg, ZA',  lat: -26.20,  lon:  28.04  },
  { name: 'lagos',        display: 'Lagos, NG',         lat:   6.45,  lon:   3.39  },
  { name: 'lima',         display: 'Lima, PE',          lat: -12.05,  lon: -77.04  },
  { name: 'lisbon',       display: 'Lisbon, PT',        lat:  38.72,  lon:  -9.14  },
  { name: 'london',       display: 'London, UK',        lat:  51.51,  lon:  -0.13  },
  { name: 'los angeles',  display: 'Los Angeles, US',   lat:  34.05,  lon: -118.24 },
  { name: 'madrid',       display: 'Madrid, ES',        lat:  40.42,  lon:  -3.70  },
  { name: 'mexico city',  display: 'Mexico City, MX',   lat:  19.43,  lon: -99.13  },
  { name: 'miami',        display: 'Miami, US',         lat:  25.77,  lon: -80.19  },
  { name: 'milan',        display: 'Milan, IT',         lat:  45.46,  lon:   9.19  },
  { name: 'montreal',     display: 'Montreal, CA',      lat:  45.50,  lon: -73.57  },
  { name: 'moscow',       display: 'Moscow, RU',        lat:  55.75,  lon:  37.62  },
  { name: 'mumbai',       display: 'Mumbai, IN',        lat:  19.08,  lon:  72.88  },
  { name: 'nairobi',      display: 'Nairobi, KE',       lat:  -1.29,  lon:  36.82  },
  { name: 'new york',     display: 'New York, US',      lat:  40.71,  lon: -74.01  },
  { name: 'oslo',         display: 'Oslo, NO',          lat:  59.91,  lon:  10.75  },
  { name: 'paris',        display: 'Paris, FR',         lat:  48.86,  lon:   2.35  },
  { name: 'prague',       display: 'Prague, CZ',        lat:  50.08,  lon:  14.44  },
  { name: 'rome',         display: 'Rome, IT',          lat:  41.90,  lon:  12.50  },
  { name: 'san francisco',display: 'San Francisco, US', lat:  37.77,  lon: -122.42 },
  { name: 'santiago',     display: 'Santiago, CL',      lat: -33.46,  lon: -70.65  },
  { name: 'sao paulo',    display: 'São Paulo, BR',     lat: -23.55,  lon: -46.63  },
  { name: 'seoul',        display: 'Seoul, KR',         lat:  37.57,  lon: 126.98  },
  { name: 'shanghai',     display: 'Shanghai, CN',      lat:  31.23,  lon: 121.47  },
  { name: 'singapore',    display: 'Singapore',         lat:   1.35,  lon: 103.82  },
  { name: 'stockholm',    display: 'Stockholm, SE',     lat:  59.33,  lon:  18.07  },
  { name: 'sydney',       display: 'Sydney, AU',        lat: -33.87,  lon: 151.21  },
  { name: 'tokyo',        display: 'Tokyo, JP',         lat:  35.68,  lon: 139.69  },
  { name: 'toronto',      display: 'Toronto, CA',       lat:  43.65,  lon: -79.38  },
  { name: 'vienna',       display: 'Vienna, AT',        lat:  48.21,  lon:  16.37  },
  { name: 'warsaw',       display: 'Warsaw, PL',        lat:  52.23,  lon:  21.01  },
  { name: 'washington',   display: 'Washington DC, US', lat:  38.91,  lon: -77.04  },
  { name: 'zurich',       display: 'Zurich, CH',        lat:  47.38,  lon:   8.54  },
];

function placeMarker(lat, lon) {
  const pos = latLonTo3D(lat, lon);
  const offset = pos.clone().multiplyScalar(1.04);
  const quat   = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 0, 1), pos);
  andorraRing.position.copy(offset);
  andorraRing.quaternion.copy(quat);
  andorraDot.position.copy(offset);
  andorraDot.quaternion.copy(quat);
}

// ── Search bar ───────────────────────────────────────────────────────────────

function enterSimulation() {
  if (fly) return; // already flying in
  const loc = activeLocation || { lat: 42.5, lon: 1.6 }; // default to Andorra
  const p = latLonTo3D(loc.lat, loc.lon);                // unit direction, local space
  const rot0 = globeGroup.rotation.y;
  let rot1 = Math.atan2(-p.x, p.z);                      // brings the target to face the camera
  while (rot1 - rot0 >  Math.PI) rot1 -= Math.PI * 2;    // shortest path
  while (rot1 - rot0 < -Math.PI) rot1 += Math.PI * 2;
  fly = { t0: performance.now(), dur: 1600, rot0, rot1, localPt: p.multiplyScalar(1.04), done: false };
  orbitCtrl.enabled = false;
}

const searchInput      = document.getElementById('search-input');
const searchSuggestion = document.getElementById('search-suggestion');
const suggestionName   = document.getElementById('suggestion-name');

searchInput.addEventListener('input', () => {
  const val = searchInput.value.trim().toLowerCase();
  const match = val.length > 0
    ? LOCATIONS.find(loc => loc.name.startsWith(val))
    : null;

  activeLocation = match || null;

  if (match) {
    suggestionName.textContent  = match.display;
    searchSuggestion.style.display = 'block';
    placeMarker(match.lat, match.lon);
    andorraRing.visible = true;
    andorraDot.visible  = true;
    if (placeLabelName)   placeLabelName.textContent   = match.display;        // on-globe label
    if (placeLabelCoords) placeLabelCoords.textContent = fmtCoords(match.lat, match.lon);
  } else {
    searchSuggestion.style.display = 'none';
    andorraRing.visible = false;
    andorraDot.visible  = false;
  }
});

searchInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && activeLocation) enterSimulation();
});

document.getElementById('suggestion-item').addEventListener('click', () => {
  if (activeLocation) enterSimulation();
});

window.addEventListener('resize', function () {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
}, false);

// https://discourse.threejs.org/t/earth-point-vertex-elevation/62689