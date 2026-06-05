import { useEffect, useRef, useState, useCallback } from 'react';
import L from 'leaflet';
import MapMask from './MapMask';

const MAP_CENTER = [42.507, 1.522];
const MAP_ZOOM   = 15.4;
const TICK_MAX   = 44;
const ANIM_FPS   = 30;
const SPEEDS     = [1.5, 4, 10]; // steps per second

const EMOTION_COLOR = { green: '#4ade80', red: '#f87171', purple: '#c084fc' };

const AGENT_DATA = [
  {
    id: 'Carlos', label: 'Carlos', color: '#10b981', transport: 'foot',
    path: [
      [1.5222309,42.5056912],[1.5220892743766348,42.50563044682906],[1.5219705467255271,42.5055531023191],
      [1.5219535603607839,42.50570583008205],[1.521954102073004,42.505913790552235],
      [1.5219545953655484,42.506103162963726],[1.5219693325037198,42.50628940200635],
      [1.5221290007433967,42.50634738669582],[1.5221290007433967,42.50634738669582],
      [1.5221290007433967,42.50634738669582],[1.5221290007433967,42.50634738669582],
      [1.522275005710984,42.50638218658737],[1.5225005646673204,42.50643594795831],
      [1.5226465696349079,42.50647074784987],[1.5228346914200683,42.50651558617169],
      [1.5230181335588315,42.50655930911236],[1.5231641385264187,42.50659410900393],
      [1.5233897103079934,42.50664781636523],[1.5235357624030557,42.506682417712],
      [1.5237169695955772,42.50672514025973],[1.5239075828814799,42.5067698951113],
      [1.5240537043665476,42.506804202466235],[1.5242794397754365,42.50685721805318],
      [1.5244254456824116,42.50689201094305],[1.524599386232316,42.50693409522169],
      [1.5247966440071958,42.50698207736888],[1.5249844518619875,42.50702380154131],
      [1.525120020837656,42.507094038652035],[1.5252637231599062,42.50711232401991],
      [1.5254348407756606,42.50712696965275],[1.5256443040756174,42.50714489722013],
      [1.5258288426808426,42.50716069153007],[1.5260248849913287,42.50717747042036],
      [1.526174433159719,42.50719026996503],[1.5263383609596852,42.50720430023515],
      [1.526554863251141,42.50722292098987],[1.5266786745387912,42.507265725031736],
      [1.5265927527596919,42.50742857274575],[1.526533309251881,42.507561807585446],
      [1.5264939718385733,42.5076944922638],[1.5263879164010894,42.50788608489156],
      [1.526370480588641,42.50800306251903],[1.5265530335306219,42.508048120034665],
      [1.5267131937266107,42.50808131959679],[1.526942,42.5081145],
    ],
    emotions: Array(45).fill('green'),
    conversation: [
      { t: 7,  text: 'Hey, Elena? Is that you?' },
      { t: 9,  text: 'Just ran an errand. Coffee?' },
      { t: 11, text: 'Perfect, catch up!' },
      { t: 13, text: 'I still cannot believe this!' },
      { t: 15, text: 'So what have you been up to?' },
      { t: 17, text: 'No kidding! Where to?' },
      { t: 19, text: 'I knew you would end up somewhere cool.' },
      { t: 21, text: 'I picked up sketching during lockdown.' },
    ],
  },
  {
    id: 'Elena', label: 'Elena', color: '#60a5fa', transport: 'foot',
    path: [
      [1.5222509,42.5056962],[1.5221092743766347,42.50563544682906],[1.521990546725527,42.5055581023191],
      [1.5219735603607838,42.50571083008205],[1.521974102073004,42.505918790552236],
      [1.5219745953655484,42.50610816296373],[1.5219893325037197,42.506294402006354],
      [1.5221490007433967,42.50635238669582],[1.5221490007433967,42.50635238669582],
      [1.5221490007433967,42.50635238669582],[1.5221490007433967,42.50635238669582],
      [1.5222950057109839,42.506387186587375],[1.5225205646673203,42.50644094795831],
      [1.5226665696349078,42.50647574784987],[1.5228546914200682,42.50652058617169],
      [1.5230381335588314,42.50656430911236],[1.5231841385264187,42.50659910900393],
      [1.5234097103079933,42.50665281636523],[1.5235557624030556,42.506687417712],
      [1.5237369695955771,42.506730140259734],[1.5239275828814798,42.5067748951113],
      [1.5240737043665475,42.506809202466236],[1.5242994397754364,42.50686221805318],
      [1.5244454456824115,42.50689701094305],[1.5246193862323159,42.50693909522169],
      [1.5248166440071957,42.50698707736888],[1.5250044518619874,42.50702880154131],
      [1.525140020837656,42.507099038652036],[1.5252837231599061,42.50711732401991],
      [1.5254548407756605,42.507131969652754],[1.5256643040756173,42.50714989722013],
      [1.5258488426808425,42.50716569153007],[1.5260448849913286,42.50718247042036],
      [1.5261944331597188,42.50719526996503],[1.5263583609596851,42.507209300235154],
      [1.526574863251141,42.50722792098987],[1.5266986745387912,42.50727072503174],
      [1.5266127527596918,42.507433572745754],[1.5265533092518808,42.50756680758545],
      [1.5265139718385732,42.507699492263804],[1.5264079164010893,42.50789108489156],
      [1.526390480588641,42.50800806251903],[1.5265730335306218,42.50805312003467],
      [1.5267331937266106,42.50808631959679],[1.526962,42.5081195],
    ],
    emotions: Array(45).fill('green'),
    conversation: [
      { t: 8,  text: 'Carlos! It has been ages!' },
      { t: 10, text: 'I was about to grab one—great timing.' },
      { t: 12, text: 'Like 1995 again!' },
      { t: 14, text: 'Total nostalgia trip.' },
      { t: 16, text: 'A bit of this, a bit of that.' },
      { t: 18, text: 'Tokyo, actually. Six years.' },
      { t: 20, text: 'Flatterer. Still playing guitar?' },
      { t: 22, text: 'That suits you. Eye for details.' },
    ],
  },
  {
    id: 'Blue-2', label: 'Blue', color: '#3b82f6', transport: 'bicycle',
    path: [
      [1.522488400000001,42.5072953],[1.5218166829467878,42.50659512580978],
      [1.522131025480048,42.50662529125019],[1.5221532408360732,42.50665131738797],
      [1.5224433430797968,42.506350154468194],[1.5220551510453006,42.50629589772955],
      [1.5220088145105557,42.50679539698264],[1.5223681953764752,42.50751504737874],
      [1.5215142577552323,42.507259544836515],[1.5214702318134874,42.50660794280517],
      [1.5211692418418072,42.506902251010274],[1.5218939024090925,42.50749895841448],
      [1.5223526665259162,42.5071538162088],[1.521680949472703,42.50645364201858],
      [1.520904406982537,42.505941697753975],[1.5212206436995308,42.50619375752798],
      [1.5212015543518567,42.50610693472968],[1.5202768291933257,42.505820356897026],
      [1.5193315481483485,42.50560151576232],[1.518386385305042,42.505572434499264],
      [1.5187818645099025,42.506348773068666],[1.5196452862694816,42.50638389125264],
      [1.5201915146723342,42.506423014361964],[1.5193103810463802,42.50625261321935],
      [1.5187969133709387,42.506762808128094],[1.5181780780462732,42.50656202305266],
      [1.5177468002945302,42.50660504954339],[1.5177349999999998,42.5073403],
    ],
    emotions: [
      'red','red','red','red','red','green','green','green','green','green',
      'red','red','red','red','red','purple','purple','purple','purple','purple',
      'red','red','red','red','red','purple','purple','purple',
    ],
    conversation: [],
  },
  {
    id: 'Orange-2', label: 'Orange', color: '#f97316', transport: 'foot',
    path: [
      [1.5175130000000006,42.5052838],[1.5180499158694998,42.50547544231365],
      [1.5184592149292644,42.50593818776435],[1.5187846014567428,42.50651169637815],
      [1.5185301538457538,42.506607646228844],[1.5180196141110815,42.5061552620139],
      [1.517478680910062,42.5059851406761],[1.517940708725581,42.506248707002776],
      [1.518341621649009,42.5066665343783],[1.51881614265548,42.506848548228916],
      [1.5189496260819877,42.50635747481487],[1.5187661350652673,42.506334971037354],
      [1.5183918322278016,42.50577084956877],[1.5187918945485757,42.50547802301748],
      [1.51945644791568,42.50563043119118],[1.5201210021811113,42.505784281530495],
      [1.5207824588702668,42.50594833914495],[1.5212002809594058,42.5062048429088],
      [1.5211731101079926,42.506219634593684],[1.5208113926503488,42.50595928836767],
      [1.5212217943866844,42.506063225109536],[1.5217211758828055,42.5063621984422],
      [1.5223705577946014,42.506339981430514],[1.523032355082978,42.50649691327387],
      [1.5236901692361136,42.50667534825935],[1.524348625119069,42.50676474614767],
      [1.5244859000000006,42.506162999999994],
    ],
    emotions: [
      'red','red','red','red','red','green','green','green','green','green',
      'red','red','red','red','red','purple','purple','purple','purple','purple',
      'purple','purple','purple','purple','purple','green','green',
    ],
    conversation: [],
  },
  {
    id: 'Purple-3', label: 'Purple', color: '#a855f7', transport: 'foot',
    path: [
      [1.5233713000000002,42.5095871],[1.522825940122498,42.50945009618322],
      [1.5223646611109958,42.5092263924259],[1.522754080368233,42.50885902198246],
      [1.5232217181395404,42.5085457590296],[1.5237170165251834,42.50862844752739],
      [1.5237324534906531,42.50889196261688],[1.5238436403313074,42.508889108192676],
      [1.5236334932156552,42.50858802533124],[1.523145939813331,42.5083121228846],
      [1.5232119633388865,42.50789799495394],[1.52371361997741,42.507728286073196],
      [1.524117861575466,42.50744863884545],[1.5241005030374934,42.507599750369245],
      [1.5235969456095433,42.50778749206625],[1.5230417484367869,42.50771749367103],
      [1.5225418249678675,42.50752873548289],[1.5222717013672669,42.50706942098],
      [1.5218820342825203,42.50666324573968],[1.5218465017552754,42.5063120471119],
      [1.522395908718243,42.506411003494165],[1.5229434376904865,42.50654150555293],
      [1.5234910062485807,42.506671840907806],[1.5240389169824242,42.50680073007414],
      [1.5244604895041476,42.50655769075942],[1.5245425435153503,42.506265494819075],
      [1.524350318344578,42.506763407060824],[1.5238086721039805,42.50670181688364],
      [1.5234697802150543,42.50647444321216],[1.5237033401075273,42.50596232160608],
      [1.5239369000000003,42.5054502],
    ],
    emotions: [
      'red','red','red','red','red','red','red','red','red','red','red','red','red','red','red',
      'purple','purple','purple','purple','purple',
      'green','green','green','green','green','green','green','green','green','green','green',
    ],
    conversation: [],
  },
  {
    id: 'Red-2', label: 'Red', color: '#ef4444', transport: 'foot',
    path: [
      [1.5178826000000007,42.50637319999999],[1.5182315882401747,42.50659621834496],
      [1.5185805764803484,42.50681923668993],[1.5188032257310466,42.50683978198714],
      [1.5187804735678343,42.50642750464395],[1.518793008264201,42.506683160221925],
      [1.5188054283190957,42.50684127680268],[1.519167032572573,42.507041797811695],
      [1.5195363209017516,42.50722929742211],[1.5199152133359153,42.50739503126056],
      [1.5201201093659198,42.50757289851129],[1.519735601968,42.50772139216647],
      [1.5193646954346127,42.50790561777207],[1.5189917455011426,42.5080857241881],
      [1.5186187955676722,42.50826583060413],[1.5183263752064393,42.50803351720207],
      [1.5183306895580808,42.50765824420946],[1.518437770375122,42.50725816462663],
      [1.518413748807837,42.507347914956185],[1.518306667990796,42.50774799453901],
      [1.5183886951173893,42.508102425736006],[1.5186626666702447,42.50841295253174],
      [1.5185774290200327,42.50828580749639],[1.5189503789535028,42.50810570108036],
      [1.519323328886973,42.50792559466432],[1.5195722649866037,42.5079880528169],
      [1.5196446475583887,42.50839584042985],[1.5198942,42.50865760000001],
    ],
    emotions: [
      'green','green','green','green','green','red','red','red','red','red',
      'green','green','green','green','green','purple','purple','purple','purple','purple',
      'green','green','green','green','green','red','red','red',
    ],
    conversation: [],
  },
];

function toLatLng([lon, lat]) { return [lat, lon]; }

function interpPos(path, tick) {
  const max = path.length - 1;
  if (tick >= max) return toLatLng(path[max]);
  const i = Math.floor(tick);
  const f = tick - i;
  const [lon0, lat0] = path[i];
  const [lon1, lat1] = path[i + 1];
  return [lat0 + (lat1 - lat0) * f, lon0 + (lon1 - lon0) * f];
}

function currentEmotion(emotions, tick) {
  const i = Math.min(Math.floor(tick), emotions.length - 1);
  return emotions[Math.max(0, i)] || 'green';
}

function makeIcon(typeColor, emColor, label) {
  return L.divIcon({
    html: `<div style="position:relative;pointer-events:none">
      <div class="agm-pulse" style="
        width:20px;height:20px;border-radius:50%;
        position:absolute;transform:translate(-50%,-50%);
        background:${emColor}22;animation:agm-pulse 1.8s ease-out infinite;
      "></div>
      <div class="agm-inner" style="
        width:13px;height:13px;border-radius:50%;
        background:${emColor};
        border:2.5px solid ${typeColor};
        box-shadow:0 0 10px ${emColor}bb,0 0 4px ${typeColor}99;
        position:absolute;transform:translate(-50%,-50%);
      "></div>
      <span class="agm-lbl" style="
        position:absolute;left:8px;top:-15px;
        font-family:'IBM Plex Mono',monospace;font-size:9px;font-weight:700;
        color:${typeColor};white-space:nowrap;
        text-shadow:0 0 6px #000,0 1px 3px #000;
        letter-spacing:.04em;
      ">${label}</span>
    </div>`,
    className: '',
    iconSize: [0, 0],
    iconAnchor: [0, 0],
  });
}

// Inject keyframe animation once
if (typeof document !== 'undefined' && !document.getElementById('agm-style')) {
  const s = document.createElement('style');
  s.id = 'agm-style';
  s.textContent = `
    @keyframes agm-pulse {
      0%   { transform:translate(-50%,-50%) scale(1);   opacity:.7; }
      70%  { transform:translate(-50%,-50%) scale(2.8); opacity:0; }
      100% { transform:translate(-50%,-50%) scale(1);   opacity:0; }
    }
    .leaflet-tooltip.agm-conv {
      background:rgba(10,10,15,.88) !important;
      border:1px solid #374151 !important;
      border-radius:6px !important;
      padding:4px 8px !important;
      font-family:'IBM Plex Mono',monospace !important;
      font-size:10px !important;
      color:#e5e7eb !important;
      box-shadow:0 4px 12px rgba(0,0,0,.6) !important;
      pointer-events:none !important;
      white-space:nowrap !important;
    }
    .leaflet-tooltip.agm-conv::before { display:none !important; }
  `;
  document.head.appendChild(s);
}

const BTN = {
  fontFamily: "'IBM Plex Mono',monospace",
  fontSize: '0.7rem',
  padding: '4px 10px',
  borderRadius: 4,
  cursor: 'pointer',
  border: '1px solid var(--bdr, #2a2a2a)',
  background: 'transparent',
  color: 'var(--muted, #9ca3af)',
  transition: 'color .15s,background .15s',
};

export default function AgentMapView() {
  const mapRef      = useRef(null);
  const instanceRef = useRef(null);
  const markersRef  = useRef({});
  const trailsRef   = useRef({});
  const convTipsRef = useRef({}); // id -> active tooltip
  const tickRef     = useRef(0);
  const intervalRef = useRef(null);

  const [playing,      setPlaying]      = useState(false);
  const [displayTick,  setDisplayTick]  = useState(0);
  const [speedIdx,     setSpeedIdx]     = useState(1);
  const [convLines,    setConvLines]    = useState({}); // id -> current text

  // ── Init map ────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!mapRef.current || instanceRef.current) return;

    const map = L.map(mapRef.current, {
      center: MAP_CENTER, zoom: MAP_ZOOM,
      zoomControl: false, attributionControl: false,
      scrollWheelZoom: false, doubleClickZoom: false,
      touchZoom: false, boxZoom: false,
      dragging: false, keyboard: false,
    });
    instanceRef.current = map;

    L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      { maxZoom: 18 }
    ).addTo(map);
    L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
      { maxZoom: 18, opacity: 0.7 }
    ).addTo(map);

    AGENT_DATA.forEach(agent => {
      const { id, color, path, emotions } = agent;

      // Faint ghost route
      L.polyline(path.map(toLatLng), {
        color, weight: 1.5, opacity: 0.15, dashArray: '3 8', smoothFactor: 1,
      }).addTo(map);

      // Growing trail
      const trail = L.polyline([toLatLng(path[0])], {
        color, weight: 3.5, opacity: 0.85, smoothFactor: 1,
      }).addTo(map);
      trailsRef.current[id] = trail;

      // Moving marker
      const em0 = emotions[0] || 'green';
      const marker = L.marker(toLatLng(path[0]), {
        icon: makeIcon(color, EMOTION_COLOR[em0], agent.label),
        zIndexOffset: 1000,
      }).addTo(map);
      markersRef.current[id] = marker;
    });

    map.setMinZoom(MAP_ZOOM);
    map.setMaxZoom(MAP_ZOOM);

    // Auto-start after tiles settle
    const autoTimer = setTimeout(() => setPlaying(true), 800);

    return () => {
      clearTimeout(autoTimer);
      map.remove();
      instanceRef.current = null;
    };
  }, []);

  // ── Update all agents to a given tick ──────────────────────────────────────
  const updateFrame = useCallback((tick) => {
    const newConv = {};
    AGENT_DATA.forEach(agent => {
      const { id, color, path, emotions, conversation } = agent;
      const clampedTick = Math.min(tick, path.length - 1);
      const pos   = interpPos(path, clampedTick);
      const em    = currentEmotion(emotions, clampedTick);
      const emColor = EMOTION_COLOR[em];

      // Update marker position + emotion glow
      const marker = markersRef.current[id];
      if (marker) {
        marker.setLatLng(pos);
        const el = marker.getElement();
        if (el) {
          const inner = el.querySelector('.agm-inner');
          if (inner) {
            inner.style.background   = emColor;
            inner.style.boxShadow    = `0 0 10px ${emColor}bb, 0 0 4px ${color}99`;
          }
          const pulse = el.querySelector('.agm-pulse');
          if (pulse) pulse.style.background = emColor + '22';
        }
      }

      // Update trail
      const trail = trailsRef.current[id];
      if (trail) {
        const maxI = Math.min(Math.floor(clampedTick), path.length - 1);
        const pts  = path.slice(0, maxI + 1).map(toLatLng);
        if (clampedTick < path.length - 1) pts.push(pos);
        trail.setLatLngs(pts);
      }

      // Conversation lines (within 1.5 steps of trigger)
      if (conversation.length) {
        const active = conversation.find(c => Math.abs(c.t - tick) < 1.5);
        if (active) newConv[id] = active.text;
      }
    });
    setConvLines(newConv);
  }, []);

  // ── Animation tick ─────────────────────────────────────────────────────────
  const speedIdxRef = useRef(speedIdx);
  useEffect(() => { speedIdxRef.current = speedIdx; }, [speedIdx]);

  const stepAnim = useCallback(() => {
    const tpf = SPEEDS[speedIdxRef.current] / ANIM_FPS;
    tickRef.current = Math.min(tickRef.current + tpf, TICK_MAX);
    const tick = tickRef.current;
    updateFrame(tick);
    setDisplayTick(Math.round(tick * 4) / 4);
    if (tick >= TICK_MAX) {
      clearInterval(intervalRef.current);
      setPlaying(false);
    }
  }, [updateFrame]);

  useEffect(() => {
    if (playing) {
      intervalRef.current = setInterval(stepAnim, 1000 / ANIM_FPS);
    } else {
      clearInterval(intervalRef.current);
    }
    return () => clearInterval(intervalRef.current);
  }, [playing, stepAnim]);

  // ── Controls ────────────────────────────────────────────────────────────────
  const reset = useCallback(() => {
    clearInterval(intervalRef.current);
    setPlaying(false);
    tickRef.current = 0;
    setDisplayTick(0);
    setConvLines({});
    updateFrame(0);
  }, [updateFrame]);

  const togglePlay = useCallback(() => {
    if (tickRef.current >= TICK_MAX) {
      tickRef.current = 0;
      setDisplayTick(0);
      setConvLines({});
      updateFrame(0);
    }
    setPlaying(p => !p);
  }, [updateFrame]);

  const handleScrub = useCallback((e) => {
    const tick = Number(e.target.value);
    tickRef.current = tick;
    setDisplayTick(tick);
    updateFrame(tick);
  }, [updateFrame]);

  // ── Render ──────────────────────────────────────────────────────────────────
  const activeSpeakers = Object.entries(convLines);

  return (
    <div style={{ position: 'relative', height: '100%' }}>

      {/* Toolbar */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 48, zIndex: 10,
        display: 'flex', gap: '0.4rem', flexWrap: 'nowrap', overflow: 'hidden',
        padding: '0 1rem', alignItems: 'center',
        background: 'var(--bg)', borderBottom: '1px solid var(--bdr)',
      }}>
        {AGENT_DATA.map(a => (
          <span key={a.id} style={{
            fontSize: '0.7rem', color: a.color,
            padding: '2px 8px', borderRadius: 4,
            border: `1px solid ${a.color}44`, background: `${a.color}12`,
            flexShrink: 0,
          }}>{a.label}</span>
        ))}
        <span style={{ marginLeft: 'auto', fontSize: '0.68rem', color: 'var(--muted)', letterSpacing: '.06em', flexShrink: 0 }}>
          STEP {Math.floor(displayTick)}/{TICK_MAX}
        </span>
      </div>

      {/* Map */}
      <div ref={mapRef} style={{
        position: 'absolute', top: 48,
        bottom: activeSpeakers.length > 0 ? 140 : 76,
        left: 0, right: 0, background: '#0d0d0d',
        transition: 'bottom .25s ease',
      }} />
      <MapMask mapInstance={instanceRef} />

      {/* Conversation overlay */}
      {activeSpeakers.length > 0 && (
        <div style={{
          position: 'absolute', bottom: 76, left: 0, right: 0,
          padding: '6px 1rem', zIndex: 10,
          background: 'rgba(0,0,0,0.65)',
          borderTop: '1px solid #1f2937',
          display: 'flex', flexDirection: 'column', gap: '4px',
        }}>
          {activeSpeakers.map(([id, text]) => {
            const agent = AGENT_DATA.find(a => a.id === id);
            return (
              <div key={id} style={{ display: 'flex', gap: '8px', alignItems: 'baseline' }}>
                <span style={{
                  fontFamily: "'IBM Plex Mono',monospace", fontSize: '0.7rem',
                  color: agent?.color, fontWeight: 700, flexShrink: 0,
                }}>{agent?.label}</span>
                <span style={{
                  fontFamily: "'IBM Plex Mono',monospace", fontSize: '0.7rem',
                  color: '#d1d5db', lineHeight: 1.4,
                }}>{text}</span>
              </div>
            );
          })}
        </div>
      )}

      {/* Controls bar */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: 76, zIndex: 10,
        display: 'flex', flexDirection: 'column', gap: '6px',
        padding: '6px 1rem 8px',
        background: 'var(--bg)', borderTop: '1px solid var(--bdr)',
      }}>
        {/* Scrubber row */}
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: '0.62rem', color: 'var(--muted)', width: 28 }}>
            {String(Math.floor(displayTick)).padStart(2, '0')}
          </span>
          <input
            type="range" min={0} max={TICK_MAX} step={0.25}
            value={displayTick}
            onChange={handleScrub}
            style={{ flex: 1, accentColor: '#4ade80', cursor: 'pointer' }}
          />
          <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: '0.62rem', color: 'var(--muted)', width: 28, textAlign: 'right' }}>
            {TICK_MAX}
          </span>
        </div>

        {/* Button row */}
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
          {/* Reset */}
          <button onClick={reset} style={BTN} title="Reset">↺</button>

          {/* Play / Pause */}
          <button onClick={togglePlay} style={{
            ...BTN,
            color: playing ? '#f87171' : '#4ade80',
            border: `1px solid ${playing ? '#f87171' : '#4ade80'}55`,
            background: playing ? '#f8717112' : '#4ade8012',
            minWidth: 36,
          }}>
            {playing ? '⏸' : '▶'}
          </button>

          {/* Speed */}
          <div style={{ display: 'flex', gap: '3px', marginLeft: 4 }}>
            {['1×', '2×', '3×'].map((label, i) => (
              <button key={label} onClick={() => setSpeedIdx(i)} style={{
                ...BTN,
                color:      speedIdx === i ? '#e5e7eb' : 'var(--muted)',
                background: speedIdx === i ? '#374151' : 'transparent',
                border:     speedIdx === i ? '1px solid #4b5563' : '1px solid var(--bdr, #2a2a2a)',
              }}>{label}</button>
            ))}
          </div>

          {/* Spacer */}
          <div style={{ flex: 1 }} />

          {/* Emotion legend */}
          {Object.entries(EMOTION_COLOR).map(([em, c]) => (
            <span key={em} style={{
              display: 'flex', gap: '5px', alignItems: 'center',
              fontFamily: "'IBM Plex Mono',monospace", fontSize: '0.65rem', color: c,
            }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: c, display: 'inline-block', flexShrink: 0 }} />
              {em}
            </span>
          ))}
        </div>
      </div>

    </div>
  );
}
