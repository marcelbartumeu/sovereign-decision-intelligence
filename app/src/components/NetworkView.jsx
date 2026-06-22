import { useCallback, useEffect, useRef, useState } from 'react';
import { NetworkRenderer } from '../utils/networkRenderer';

// Social network of the full synthetic population: 90k agents, 586k ties
// (4 layers: household, workplace, school, community).
// Rendered with a custom WebGL2 engine (utils/networkRenderer.js); layout is
// precomputed by data/scripts/build_network_viz.py into /public/network/.

// alpha is tuned so each layer's on-screen "ink" roughly tracks its edge count
// (community has 5× school's edges but short, tightly-collapsed edges, so it
// needs higher opacity to read as the densest layer rather than the faintest).
// color = edge RGB (kept dimmer than the legend dots so the additive mesh stays
// calm); alpha tuned so each layer's on-screen ink roughly tracks its edge count.
const LAYERS = [
  { key: 'household', label: 'Household', dot: '#C8801F', color: [0.78, 0.49, 0.05], alpha: 0.10 },
  { key: 'workplace', label: 'Workplace', dot: '#3A78C2', color: [0.14, 0.42, 0.74], alpha: 0.07 },
  { key: 'school', label: 'School', dot: '#3C9E5A', color: [0.15, 0.56, 0.30], alpha: 0.07 },
  { key: 'community', label: 'Community', dot: '#8E9099', color: [0.58, 0.60, 0.66], alpha: 0.10 },
];

// Echo the scenario palette (chartUtils.js / GrowthMapView.jsx) so the network
// reads as part of the same visual system. The four named nationalities take
// the four scenario hues; "Other" (the residual catch-all) gets a neutral slate.
const NATIONALITY_COLORS = {
  Andorran: '#294daf',   // Continuity blue
  Spanish: '#bd0638',    // Overgrowth crimson
  Portuguese: '#076f37', // Degrowth green
  French: '#eab308',     // Density gold
  Other: '#8E9099',      // neutral slate
};

const pretty = (s) => s ? s.replaceAll('_', ' ').replace(/^./, (c) => c.toUpperCase()) : '';

// The DrL layout comes out roughly axis-aligned; we present it rotated for a
// more dynamic composition. Rotation is around the origin, which is the layout
// centroid (build_network_viz.py centers positions at 0,0 before exporting).
const VIEW_ROTATION = -Math.PI / 4; // -45°

function rotatePositions(pos, angle) {
  const cos = Math.cos(angle);
  const sin = Math.sin(angle);
  for (let i = 0; i < pos.length; i += 2) {
    const x = pos[i];
    const y = pos[i + 1];
    pos[i] = x * cos - y * sin;
    pos[i + 1] = x * sin + y * cos;
  }
}

// Data is cached at module level so re-entering the tab (or the user having
// dragged nodes around) survives unmounts without refetching ~6 MB.
let dataPromise = null;

async function fetchBin(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
  return res.arrayBuffer();
}

function loadNetworkData() {
  if (!dataPromise) {
    dataPromise = (async () => {
      const [meta, pos, household, workplace, school, community, attrs] = await Promise.all([
        fetch('/network/meta.json').then((r) => {
          if (!r.ok) throw new Error(`meta.json: HTTP ${r.status}`);
          return r.json();
        }),
        fetchBin('/network/positions.bin'),
        fetchBin('/network/edges_household.bin'),
        fetchBin('/network/edges_workplace.bin'),
        fetchBin('/network/edges_school.bin'),
        fetchBin('/network/edges_community.bin'),
        fetchBin('/network/attrs.bin'),
      ]);
      const n = meta.n_agents;
      const attrBytes = new Uint8Array(attrs);
      const positions = new Float32Array(pos);
      rotatePositions(positions, VIEW_ROTATION);
      const data = {
        meta,
        n,
        positions,
        edges: {
          household: new Uint32Array(household),
          workplace: new Uint32Array(workplace),
          school: new Uint32Array(school),
          community: new Uint32Array(community),
        },
        age: attrBytes.subarray(0, n),
        nationality: attrBytes.subarray(n, 2 * n),
        income: attrBytes.subarray(2 * n, 3 * n),
        employment: attrBytes.subarray(3 * n, 4 * n),
        household: attrBytes.subarray(4 * n, 5 * n),
      };
      // Node colors by nationality, in the system accent palette
      const colors = new Uint8Array(n * 3);
      const palette = meta.nationalities.map((name) => {
        const hex = NATIONALITY_COLORS[name] || '#64D2FF';
        return [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16)];
      });
      for (let i = 0; i < n; i++) {
        const [r, g, b] = palette[data.nationality[i]];
        colors[i * 3] = r;
        colors[i * 3 + 1] = g;
        colors[i * 3 + 2] = b;
      }
      data.colors = colors;
      return data;
    })();
    dataPromise.catch(() => { dataPromise = null; }); // allow retry after failure
  }
  return dataPromise;
}

function agentInfo(data, id) {
  const { meta } = data;
  return {
    id,
    label: `POP-${String(id).padStart(5, '0')}`,
    age: data.age[id],
    nationality: meta.nationalities[data.nationality[id]],
    income: pretty(meta.incomes[data.income[id]]),
    employment: pretty(meta.employments[data.employment[id]]),
    household: pretty(meta.households[data.household[id]]),
  };
}

// Edges + neighbors of one agent, scanned per layer (~630k uint32 compares, <5ms)
function collectTies(data, id) {
  const edgeIdx = [];
  const neighbors = new Set();
  const ties = {};
  for (const { key } of LAYERS) {
    const arr = data.edges[key];
    let count = 0;
    for (let i = 0; i < arr.length; i += 2) {
      const a = arr[i], b = arr[i + 1];
      if (a === id || b === id) {
        count++;
        edgeIdx.push(a, b);
        neighbors.add(a === id ? b : a);
      }
    }
    ties[key] = count;
  }
  return { ties, edgeIndices: new Uint32Array(edgeIdx), neighborIds: [...neighbors] };
}

export default function NetworkView() {
  const wrapRef = useRef(null);
  const canvasRef = useRef(null);
  const rendererRef = useRef(null);
  const dataRef = useRef(null);
  const dragRef = useRef(null);     // {mode:'pan'|'node', id, startX, startY, lastX, lastY, moved}
  const hoverRaf = useRef(0);

  const [status, setStatus] = useState('loading'); // loading | ready | error
  const [error, setError] = useState(null);
  const [visible, setVisible] = useState({ household: true, workplace: true, school: true, community: true });
  const [hovered, setHovered] = useState(null);    // {info, x, y}
  const [selected, setSelected] = useState(null);  // {info, ties, degree}

  // ── Init: load data, create renderer, attach observers ───────────────────
  useEffect(() => {
    let cancelled = false;
    let renderer = null;
    let observer = null;

    loadNetworkData()
      .then((data) => {
        if (cancelled) return;
        dataRef.current = data;
        renderer = new NetworkRenderer(canvasRef.current);
        rendererRef.current = renderer;
        renderer.setData({
          positions: data.positions,
          colors: data.colors,
          layers: LAYERS.map((l) => ({ key: l.key, indices: data.edges[l.key], color: l.color, alpha: l.alpha })),
        });
        renderer.resize();
        renderer.fitView();
        renderer.startAnimation();   // gentle "breathing" idle motion
        observer = new ResizeObserver(() => {
          renderer.resize();
          renderer.requestRender();
        });
        observer.observe(wrapRef.current);
        setStatus('ready');
      })
      .catch((err) => {
        if (cancelled) return;
        console.error('Network view failed to initialise:', err);
        setError(err.message);
        setStatus('error');
      });

    return () => {
      cancelled = true;
      observer?.disconnect();
      renderer?.destroy();
      rendererRef.current = null;
    };
  }, []);

  // ── Interactions ──────────────────────────────────────────────────────────
  const localXY = (e) => {
    const rect = canvasRef.current.getBoundingClientRect();
    return [e.clientX - rect.left, e.clientY - rect.top];
  };

  const onPointerDown = useCallback((e) => {
    const renderer = rendererRef.current;
    if (!renderer || e.button !== 0) return;
    const [x, y] = localXY(e);
    const id = renderer.pick(x, y);
    dragRef.current = {
      mode: id >= 0 ? 'node' : 'pan',
      id, startX: x, startY: y, lastX: x, lastY: y, moved: false,
    };
    canvasRef.current.setPointerCapture(e.pointerId);
  }, []);

  const onPointerMove = useCallback((e) => {
    const renderer = rendererRef.current;
    if (!renderer) return;
    const [x, y] = localXY(e);
    const drag = dragRef.current;

    if (drag) {
      if (Math.abs(x - drag.startX) > 3 || Math.abs(y - drag.startY) > 3) drag.moved = true;
      if (drag.mode === 'pan') {
        renderer.panBy(x - drag.lastX, y - drag.lastY);
      } else {
        const [wx, wy] = renderer.screenToWorld(x, y);
        renderer.updateNodePosition(drag.id, wx, wy);
        setHovered((h) => (h && h.info.id === drag.id ? { ...h, x, y } : h));
      }
      drag.lastX = x;
      drag.lastY = y;
      return;
    }

    // Hover picking, throttled to one per frame
    if (hoverRaf.current) return;
    hoverRaf.current = requestAnimationFrame(() => {
      hoverRaf.current = 0;
      const r = rendererRef.current;
      const data = dataRef.current;
      if (!r || !data) return;
      const id = r.pick(x, y);
      r.setHover(id);
      canvasRef.current.style.cursor = id >= 0 ? 'grab' : 'default';
      setHovered(id >= 0 ? { info: agentInfo(data, id), x, y } : null);
    });
  }, []);

  const onPointerUp = useCallback((e) => {
    const renderer = rendererRef.current;
    const data = dataRef.current;
    const drag = dragRef.current;
    dragRef.current = null;
    if (!renderer || !data || !drag) return;
    canvasRef.current.releasePointerCapture(e.pointerId);
    if (drag.moved) return;

    // Plain click: select / deselect
    if (drag.id >= 0) {
      const { ties, edgeIndices, neighborIds } = collectTies(data, drag.id);
      renderer.setSelection(drag.id, edgeIndices, neighborIds);
      setSelected({ info: agentInfo(data, drag.id), ties, degree: neighborIds.length });
    } else {
      renderer.setSelection(-1, null, []);
      setSelected(null);
    }
  }, []);

  const onPointerLeave = useCallback(() => {
    rendererRef.current?.setHover(-1);
    setHovered(null);
  }, []);

  // A cancelled pointer (system gesture, device change) must not leave a stuck drag
  const onPointerCancel = useCallback(() => {
    dragRef.current = null;
    rendererRef.current?.setHover(-1);
    setHovered(null);
  }, []);

  // Wheel zoom needs a non-passive listener to preventDefault page scroll
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || status !== 'ready') return;
    const onWheel = (e) => {
      e.preventDefault();
      const rect = canvas.getBoundingClientRect();
      rendererRef.current?.zoomAt(
        e.clientX - rect.left, e.clientY - rect.top,
        Math.exp(-e.deltaY * 0.002),
      );
    };
    canvas.addEventListener('wheel', onWheel, { passive: false });
    return () => canvas.removeEventListener('wheel', onWheel);
  }, [status]);

  const toggleLayer = (key) => {
    setVisible((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      rendererRef.current?.setLayerVisible(key, next[key]);
      return next;
    });
  };

  const clearSelection = () => {
    rendererRef.current?.setSelection(-1, null, []);
    setSelected(null);
  };

  const resetView = () => {
    rendererRef.current?.fitView();
  };

  const meta = dataRef.current?.meta;
  const edgesShown = meta
    ? LAYERS.reduce((sum, l) => sum + (visible[l.key] ? meta.edges[l.key] : 0), 0)
    : 0;

  // ── UI ────────────────────────────────────────────────────────────────────
  const card = {
    background: 'var(--glass-strong)',
    border: '1px solid var(--glass-bdr)',
    borderRadius: 'var(--r-lg)',
    boxShadow: 'var(--glass-shadow), var(--glass-hi)',
    backdropFilter: 'var(--glass-blur)',
    WebkitBackdropFilter: 'var(--glass-blur)',
  };

  return (
    <div ref={wrapRef} style={{ position: 'absolute', inset: 0, overflow: 'hidden', background: 'var(--bg-gradient)', backgroundAttachment: 'fixed' }}>
      <canvas
        ref={canvasRef}
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', display: 'block', touchAction: 'none' }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerLeave}
        onPointerCancel={onPointerCancel}
      />
      {/* Subtle ambient glow, same recipe as the agent-graph cards */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'radial-gradient(circle at 20% 10%, rgba(63,224,230,.05) 0, transparent 40%), radial-gradient(circle at 80% 90%, rgba(217,177,90,.04) 0, transparent 45%)',
      }} />
      {/* Cinematic scanning sweep */}
      <div className="scan-sweep" />
      {/* Feed identity tag */}
      <div style={{
        position: 'absolute', top: '1rem', left: '50%', transform: 'translateX(-50%)',
        fontFamily: 'var(--mono)', fontSize: 9.5, letterSpacing: '0.2em', textTransform: 'uppercase',
        color: 'var(--cyan)', padding: '3px 10px', border: '1px solid var(--cyan-line)',
        borderRadius: 3, background: 'rgba(4,6,10,0.5)', pointerEvents: 'none', textShadow: '0 1px 4px #000',
      }}>
        ◳ SIGINT · RELATIONAL GRAPH · 90,000 NODES
      </div>

      {status === 'loading' && (
        <div style={{
          position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: '0.5rem',
        }}>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 13, fontWeight: 600, letterSpacing: '0.16em', textTransform: 'uppercase', color: 'var(--cyan)' }}>
            ▸ Establishing relational graph<span className="caret">_</span>
          </div>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 11, letterSpacing: '0.1em', color: 'var(--lbl)' }}>
            90,000 agents · 586,021 social ties
          </div>
        </div>
      )}

      {status === 'error' && (
        <div style={{
          position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: '0.5rem',
        }}>
          <div style={{ fontFamily: 'var(--font-title)', fontSize: 14, fontWeight: 600, color: 'var(--sys-red)' }}>
            Could not load the network
          </div>
          <div style={{ fontSize: 11, color: 'var(--lbl)' }}>{error}</div>
        </div>
      )}

      {status === 'ready' && (
        <>
          {/* ── Control panel ── */}
          <div style={{ ...card, position: 'absolute', top: '1rem', left: '1rem', padding: '1rem 1.1rem', width: 248 }}>
            <div style={{ fontFamily: 'var(--font-title)', fontSize: 13, fontWeight: 600, letterSpacing: '-0.01em', color: 'var(--active)', marginBottom: 2 }}>
              Social Network
            </div>
            <div style={{ fontSize: 11, color: 'var(--lbl)', marginBottom: '0.75rem', fontFeatureSettings: "'tnum'", fontVariantNumeric: 'tabular-nums' }}>
              {meta.n_agents.toLocaleString('en-US')} agents · {edgesShown.toLocaleString('en-US')} ties shown
            </div>

            <div style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--lbl)', fontWeight: 500, marginBottom: 6 }}>
              Tie layers
            </div>
            <div className="overlay-layer-badges" style={{ marginBottom: '0.9rem' }}>
              {LAYERS.map((l) => (
                <button
                  key={l.key}
                  type="button"
                  className={`overlay-layer-badge ${visible[l.key] ? 'active' : 'inactive'}`}
                  onClick={() => toggleLayer(l.key)}
                >
                  <span className="dot" style={{ background: l.dot }} />
                  {l.label}
                </button>
              ))}
            </div>

            <div style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--lbl)', fontWeight: 500, marginBottom: 6 }}>
              Agents by nationality
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 12px', marginBottom: '0.9rem' }}>
              {meta.nationalities.map((name) => (
                <span key={name} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--text2)' }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: NATIONALITY_COLORS[name], flexShrink: 0 }} />
                  {name}
                </span>
              ))}
            </div>

            <button
              type="button"
              onClick={resetView}
              style={{
                padding: '4px 12px', borderRadius: 980, border: '0.5px solid var(--bdr2)',
                background: 'rgba(255,255,255,0.07)', color: 'var(--text2)', cursor: 'pointer',
                fontFamily: 'var(--font)', fontSize: 11, transition: 'all 0.15s var(--ease)',
              }}
            >
              Reset view
            </button>
          </div>

          {/* ── Hint line ── */}
          <div style={{ position: 'absolute', left: '1rem', bottom: '0.85rem', fontSize: 10.5, color: 'var(--lbl)', pointerEvents: 'none' }}>
            Scroll to zoom · Drag to pan · Drag a node to move it · Click an agent to inspect
          </div>

          {/* ── Selected agent card ── */}
          {selected && (
            <div style={{ ...card, position: 'absolute', top: '1rem', right: '1rem', padding: '1.1rem 1.2rem', width: 264 }}>
              <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 2 }}>
                <div style={{ fontFamily: 'var(--font-title)', fontSize: 13, fontWeight: 600, letterSpacing: '-0.01em', color: 'var(--active)' }}>
                  {selected.info.label}
                </div>
                <button
                  type="button"
                  onClick={clearSelection}
                  style={{ background: 'none', border: 'none', color: 'var(--lbl)', cursor: 'pointer', fontSize: 12, fontFamily: 'var(--font)', padding: 0 }}
                >
                  ✕
                </button>
              </div>
              <div style={{ fontSize: 11, color: 'var(--text2)', marginBottom: '0.85rem' }}>
                {selected.info.nationality}, {selected.info.age} · {selected.degree} connection{selected.degree === 1 ? '' : 's'}
              </div>

              <dl className="agent-meta" style={{ marginBottom: '0.85rem' }}>
                <div><dt>Income</dt><dd>{selected.info.income}</dd></div>
                <div><dt>Employment</dt><dd>{selected.info.employment}</dd></div>
                <div style={{ gridColumn: '1 / -1' }}><dt>Household</dt><dd>{selected.info.household}</dd></div>
              </dl>

              <div style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--lbl)', fontWeight: 500, marginBottom: 6 }}>
                Ties
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {LAYERS.map((l) => (
                  <span key={l.key} className="chip" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: l.dot, flexShrink: 0 }} />
                    {l.label} {selected.ties[l.key]}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* ── Hover tooltip ── */}
          {hovered && (!selected || hovered.info.id !== selected.info.id) && (
            <div style={{
              ...card,
              position: 'absolute',
              left: Math.min(hovered.x + 14, (wrapRef.current?.clientWidth ?? 600) - 190),
              top: Math.min(hovered.y + 14, (wrapRef.current?.clientHeight ?? 400) - 60),
              padding: '0.5rem 0.7rem',
              pointerEvents: 'none',
              maxWidth: 180,
            }}>
              <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--text)', fontFeatureSettings: "'tnum'" }}>
                {hovered.info.label}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text2)' }}>
                {hovered.info.nationality}, {hovered.info.age} · {hovered.info.income} income
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
