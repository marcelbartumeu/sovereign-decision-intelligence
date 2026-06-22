// networkRenderer.js — minimal WebGL2 engine for the social network tab.
//
// 90,000 nodes are drawn as GL_POINTS and 627k edges as indexed GL_LINES that
// reference the same position buffer, so dragging a node is a single 8-byte
// bufferSubData and every connected edge follows automatically. Hit-testing
// uses GPU picking (nodes re-rendered with id-encoded colors into an
// offscreen framebuffer, 1px readback under the cursor).

// Shared "breathing" transform — MUST be identical in NODE_VS and EDGE_VS so an
// edge endpoint and its node move together. Two effects: (1) a slow global breath
// that scales the layout around its centre, and (2) a tiny per-node clip-space
// shimmer (zoom-invariant) phased by position so neighbours drift coherently,
// giving the mesh an organic, living quiver. u_anim=0 freezes everything (used
// for prefers-reduced-motion). Returns world-space pos; writes a clip offset.
const BREATHE_GLSL = `
uniform float u_time;
uniform float u_anim;
vec2 breathe(vec2 p, out vec2 clipOffset) {
  // Global breath: scale around the VIEW CENTRE (u_center), so it's a gentle
  // in-place pulse at any zoom rather than a swing around the world origin.
  float s = 1.0 + u_anim * 0.012 * sin(u_time * 0.85);
  vec2 w = u_center + (p - u_center) * s;
  // Per-node shimmer in clip space (zoom-invariant), phased by position so
  // neighbours drift coherently — the organic, living quiver.
  float ph = p.x * 0.0130 + p.y * 0.0170;
  clipOffset = u_anim * 0.0034 * vec2(sin(u_time * 0.90 + ph),
                                      sin(u_time * 0.72 + ph * 1.3));
  return w;
}`;

const NODE_VS = `#version 300 es
precision highp float;
in vec2 a_pos;
in vec3 a_color;
uniform vec2 u_center;
uniform vec2 u_scale;
uniform float u_size;
out vec3 v_color;
${BREATHE_GLSL}
void main() {
  vec2 off;
  vec2 w = breathe(a_pos, off);
  gl_Position = vec4((w - u_center) * u_scale + off, 0.0, 1.0);
  gl_PointSize = u_size;
  v_color = a_color;
}`;

const NODE_FS = `#version 300 es
precision highp float;
in vec3 v_color;
uniform float u_alpha;
out vec4 outColor;
void main() {
  vec2 c = gl_PointCoord * 2.0 - 1.0;
  float d = dot(c, c);
  if (d > 1.0) discard;
  outColor = vec4(v_color, u_alpha * (1.0 - smoothstep(0.55, 1.0, d)));
}`;

const PICK_FS = `#version 300 es
precision highp float;
in vec3 v_color;
out vec4 outColor;
void main() {
  vec2 c = gl_PointCoord * 2.0 - 1.0;
  if (dot(c, c) > 1.0) discard;
  outColor = vec4(v_color, 1.0);
}`;

const EDGE_VS = `#version 300 es
precision highp float;
in vec2 a_pos;
uniform vec2 u_center;
uniform vec2 u_scale;
${BREATHE_GLSL}
void main() {
  vec2 off;
  vec2 w = breathe(a_pos, off);
  gl_Position = vec4((w - u_center) * u_scale + off, 0.0, 1.0);
}`;

const EDGE_FS = `#version 300 es
precision highp float;
uniform vec4 u_color;
out vec4 outColor;
void main() { outColor = u_color; }`;

// Opaque vertical gradient drawn as a fullscreen triangle (no attributes — the
// 3 verts come from gl_VertexID). This is the canvas background; it must be
// OPAQUE so the additive edge mesh has a solid base to blend onto (a transparent
// clear makes low-alpha edges composite away when zoomed out). Colors match the
// CSS --bg-gradient: linear-gradient(180deg, #000 0%, #1D1D22 100%).
const BG_VS = `#version 300 es
precision highp float;
out float v_t;
void main() {
  vec2 p = vec2((gl_VertexID == 1) ? 3.0 : -1.0,
                (gl_VertexID == 2) ? 3.0 : -1.0);
  v_t = (1.0 - p.y) * 0.5;   // 0 at top of screen, 1 at bottom
  gl_Position = vec4(p, 0.0, 1.0);
}`;

const BG_FS = `#version 300 es
precision highp float;
in float v_t;
out vec4 outColor;
void main() {
  vec3 c0 = vec3(0.0);                       // #000000 (top)
  vec3 c1 = vec3(0.1137, 0.1137, 0.1333);    // #1D1D22 (bottom)
  float t = clamp(v_t, 0.0, 1.0);
  outColor = vec4(mix(c0, c1, t), 1.0);
}`;

function compileProgram(gl, vsSrc, fsSrc) {
  const make = (type, src) => {
    const sh = gl.createShader(type);
    gl.shaderSource(sh, src);
    gl.compileShader(sh);
    if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
      throw new Error(`Shader compile failed: ${gl.getShaderInfoLog(sh)}`);
    }
    return sh;
  };
  const prog = gl.createProgram();
  gl.attachShader(prog, make(gl.VERTEX_SHADER, vsSrc));
  gl.attachShader(prog, make(gl.FRAGMENT_SHADER, fsSrc));
  gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
    throw new Error(`Program link failed: ${gl.getProgramInfoLog(prog)}`);
  }
  return prog;
}

export class NetworkRenderer {
  constructor(canvas) {
    this.canvas = canvas;
    const gl = canvas.getContext('webgl2', {
      antialias: false, alpha: false, depth: false, stencil: false,
      powerPreference: 'high-performance',
    });
    if (!gl) throw new Error('WebGL2 is not supported in this browser');
    this.gl = gl;

    this.nodeProg = compileProgram(gl, NODE_VS, NODE_FS);
    this.pickProg = compileProgram(gl, NODE_VS, PICK_FS);
    this.edgeProg = compileProgram(gl, EDGE_VS, EDGE_FS);
    this.bgProg = compileProgram(gl, BG_VS, BG_FS);
    this.uniforms = {};
    for (const [key, prog] of [['node', this.nodeProg], ['pick', this.pickProg], ['edge', this.edgeProg]]) {
      this.uniforms[key] = {
        center: gl.getUniformLocation(prog, 'u_center'),
        scale: gl.getUniformLocation(prog, 'u_scale'),
        size: gl.getUniformLocation(prog, 'u_size'),
        alpha: gl.getUniformLocation(prog, 'u_alpha'),
        color: gl.getUniformLocation(prog, 'u_color'),
        time: gl.getUniformLocation(prog, 'u_time'),
        anim: gl.getUniformLocation(prog, 'u_anim'),
      };
    }

    // Breathing animation state
    this.time = 0;
    this.animating = false;
    this.animRaf = 0;
    this.animStart = 0;
    this.reducedMotion = typeof window !== 'undefined'
      && window.matchMedia
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // Camera: world center + zoom in CSS px per world unit
    this.center = [0, 0];
    this.zoom = 0.3;
    this.fitZoom = 0.3;
    this.cssW = 1;
    this.cssH = 1;
    this.dpr = Math.min(window.devicePixelRatio || 1, 2);

    this.n = 0;
    this.positions = null;       // Float32Array, shared with the component
    this.layers = [];            // {key, vao, count, color:[r,g,b], alpha, visible}
    this.hovered = -1;
    this.selected = -1;
    this.neighborCount = 0;
    this.highlightCount = 0;

    this.posBuf = gl.createBuffer();
    this.colorBuf = gl.createBuffer();
    this.pickColorBuf = gl.createBuffer();
    this.highlightEbo = gl.createBuffer();
    this.neighborBuf = gl.createBuffer();   // positions of selection neighbors
    this.markerBuf = gl.createBuffer();     // [hovered xy, selected xy]

    this.bgVao = gl.createVertexArray();
    this.nodeVao = gl.createVertexArray();
    this.pickVao = gl.createVertexArray();
    this.highlightVao = gl.createVertexArray();
    this.neighborVao = gl.createVertexArray();
    this.markerVao = gl.createVertexArray();

    // Offscreen picking target
    this.pickFbo = gl.createFramebuffer();
    this.pickTex = gl.createTexture();
    this.pickDirty = true;
    this.renderQueued = false;
    this.destroyed = false;

    gl.disable(gl.DEPTH_TEST);
    gl.enable(gl.BLEND);
  }

  setData({ positions, colors, layers }) {
    const gl = this.gl;
    this.n = positions.length / 2;
    this.positions = positions;

    gl.bindBuffer(gl.ARRAY_BUFFER, this.posBuf);
    gl.bufferData(gl.ARRAY_BUFFER, positions, gl.DYNAMIC_DRAW);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.colorBuf);
    gl.bufferData(gl.ARRAY_BUFFER, colors, gl.STATIC_DRAW);

    // id + 1 encoded in RGB so 0 = background
    const pickColors = new Uint8Array(this.n * 3);
    for (let i = 0; i < this.n; i++) {
      const id = i + 1;
      pickColors[i * 3] = id & 0xff;
      pickColors[i * 3 + 1] = (id >> 8) & 0xff;
      pickColors[i * 3 + 2] = (id >> 16) & 0xff;
    }
    gl.bindBuffer(gl.ARRAY_BUFFER, this.pickColorBuf);
    gl.bufferData(gl.ARRAY_BUFFER, pickColors, gl.STATIC_DRAW);

    const bindPos = (prog) => {
      const loc = gl.getAttribLocation(prog, 'a_pos');
      gl.bindBuffer(gl.ARRAY_BUFFER, this.posBuf);
      gl.enableVertexAttribArray(loc);
      gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
      return gl.getAttribLocation(prog, 'a_color');
    };

    gl.bindVertexArray(this.nodeVao);
    let colorLoc = bindPos(this.nodeProg);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.colorBuf);
    gl.enableVertexAttribArray(colorLoc);
    gl.vertexAttribPointer(colorLoc, 3, gl.UNSIGNED_BYTE, true, 0, 0);

    gl.bindVertexArray(this.pickVao);
    colorLoc = bindPos(this.pickProg);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.pickColorBuf);
    gl.enableVertexAttribArray(colorLoc);
    gl.vertexAttribPointer(colorLoc, 3, gl.UNSIGNED_BYTE, true, 0, 0);

    this.layers = layers.map((layer) => {
      const vao = gl.createVertexArray();
      gl.bindVertexArray(vao);
      bindPos(this.edgeProg);
      const ebo = gl.createBuffer();
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ebo);
      gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, layer.indices, gl.STATIC_DRAW);
      return { key: layer.key, vao, count: layer.indices.length, color: layer.color, alpha: layer.alpha, visible: true };
    });

    // Highlight edges of the selected node (dynamic subset, same position buffer)
    gl.bindVertexArray(this.highlightVao);
    bindPos(this.edgeProg);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.highlightEbo);

    // Neighbor + hover/selection markers: small dynamic position buffers,
    // a_color left as a constant generic attribute (set at draw time)
    gl.bindVertexArray(this.neighborVao);
    let loc = gl.getAttribLocation(this.nodeProg, 'a_pos');
    gl.bindBuffer(gl.ARRAY_BUFFER, this.neighborBuf);
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);

    gl.bindVertexArray(this.markerVao);
    loc = gl.getAttribLocation(this.nodeProg, 'a_pos');
    gl.bindBuffer(gl.ARRAY_BUFFER, this.markerBuf);
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    gl.bufferData(gl.ARRAY_BUFFER, 16, gl.DYNAMIC_DRAW);

    gl.bindVertexArray(null);
    this.pickDirty = true;
  }

  resize() {
    const { canvas } = this;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    if (w === 0 || h === 0) return;
    this.cssW = w;
    this.cssH = h;
    const dw = Math.round(w * this.dpr);
    const dh = Math.round(h * this.dpr);
    if (canvas.width !== dw || canvas.height !== dh) {
      canvas.width = dw;
      canvas.height = dh;
      const gl = this.gl;
      gl.bindTexture(gl.TEXTURE_2D, this.pickTex);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, dw, dh, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
      gl.bindFramebuffer(gl.FRAMEBUFFER, this.pickFbo);
      gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, this.pickTex, 0);
      gl.bindFramebuffer(gl.FRAMEBUFFER, null);
      this.pickDirty = true;
    }
  }

  fitView(worldExtent = 1000, padding = 1.08) {
    this.center = [0, 0];
    this.fitZoom = Math.min(this.cssW, this.cssH) / (2 * worldExtent * padding);
    // Start a touch zoomed-in for a tighter composition; fitZoom stays the true
    // fit so the zoom-out floor (fitZoom * 0.4 in zoomAt) is unaffected.
    this.zoom = this.fitZoom * 1.3;
    this.requestRender();
  }

  // ── Camera ──────────────────────────────────────────────────────────────

  screenToWorld(sx, sy) {
    return [
      this.center[0] + (sx - this.cssW / 2) / this.zoom,
      this.center[1] + (sy - this.cssH / 2) / this.zoom,
    ];
  }

  panBy(dx, dy) {
    this.center[0] -= dx / this.zoom;
    this.center[1] -= dy / this.zoom;
    this.requestRender();
  }

  zoomAt(sx, sy, factor) {
    const [wx, wy] = this.screenToWorld(sx, sy);
    this.zoom = Math.min(Math.max(this.zoom * factor, this.fitZoom * 0.4), 500);
    this.center[0] = wx - (sx - this.cssW / 2) / this.zoom;
    this.center[1] = wy - (sy - this.cssH / 2) / this.zoom;
    this.requestRender();
  }

  nodeSize() {
    return Math.min(Math.max(0.9 + 1.1 * Math.sqrt(this.zoom), 1.3), 18);
  }

  // ── State updates ───────────────────────────────────────────────────────

  setLayerVisible(key, visible) {
    const layer = this.layers.find((l) => l.key === key);
    if (layer) layer.visible = visible;
    this.requestRender();
  }

  setHover(id) {
    if (id === this.hovered) return;
    this.hovered = id;
    this.syncMarkers();
    this.requestRender();
  }

  /** Select a node: edgeIndices = flat Uint32 [src,dst,...], neighborIds = node ids. */
  setSelection(id, edgeIndices, neighborIds) {
    const gl = this.gl;
    this.selected = id;
    this.neighborIds = neighborIds || [];
    this.highlightCount = edgeIndices ? edgeIndices.length : 0;
    if (this.highlightCount > 0) {
      gl.bindVertexArray(this.highlightVao);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.highlightEbo);
      gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, edgeIndices, gl.DYNAMIC_DRAW);
      gl.bindVertexArray(null);
    }
    this.syncNeighbors();
    this.syncMarkers();
    this.requestRender();
  }

  syncNeighbors() {
    const gl = this.gl;
    const ids = this.selected >= 0 ? this.neighborIds : [];
    this.neighborCount = ids.length;
    if (ids.length === 0) return;
    const buf = new Float32Array(ids.length * 2);
    for (let i = 0; i < ids.length; i++) {
      buf[i * 2] = this.positions[ids[i] * 2];
      buf[i * 2 + 1] = this.positions[ids[i] * 2 + 1];
    }
    gl.bindBuffer(gl.ARRAY_BUFFER, this.neighborBuf);
    gl.bufferData(gl.ARRAY_BUFFER, buf, gl.DYNAMIC_DRAW);
  }

  syncMarkers() {
    const gl = this.gl;
    const buf = new Float32Array(4);
    if (this.hovered >= 0) {
      buf[0] = this.positions[this.hovered * 2];
      buf[1] = this.positions[this.hovered * 2 + 1];
    }
    if (this.selected >= 0) {
      buf[2] = this.positions[this.selected * 2];
      buf[3] = this.positions[this.selected * 2 + 1];
    }
    gl.bindBuffer(gl.ARRAY_BUFFER, this.markerBuf);
    gl.bufferData(gl.ARRAY_BUFFER, buf, gl.DYNAMIC_DRAW);
  }

  updateNodePosition(id, wx, wy) {
    const gl = this.gl;
    this.positions[id * 2] = wx;
    this.positions[id * 2 + 1] = wy;
    gl.bindBuffer(gl.ARRAY_BUFFER, this.posBuf);
    gl.bufferSubData(gl.ARRAY_BUFFER, id * 8, this.positions, id * 2, 2);
    if (id === this.selected || id === this.hovered) this.syncMarkers();
    if (this.selected >= 0 && this.neighborIds.includes(id)) this.syncNeighbors();
    this.requestRender();
  }

  // ── Picking ─────────────────────────────────────────────────────────────

  pick(sx, sy) {
    if (this.n === 0) return -1;
    const gl = this.gl;
    gl.bindFramebuffer(gl.FRAMEBUFFER, this.pickFbo);
    if (this.pickDirty) {
      gl.viewport(0, 0, this.canvas.width, this.canvas.height);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.disable(gl.BLEND);
      gl.useProgram(this.pickProg);
      this.setCamera('pick');
      this.setAnim('pick');   // pick buffer breathes in sync with the visible nodes
      // Oversized points so small nodes are easy to grab
      gl.uniform1f(this.uniforms.pick.size, Math.max(this.nodeSize() * 1.8, 12) * this.dpr);
      gl.bindVertexArray(this.pickVao);
      gl.drawArrays(gl.POINTS, 0, this.n);
      gl.bindVertexArray(null);
      gl.enable(gl.BLEND);
      this.pickDirty = false;
    }
    const px = Math.min(Math.max(Math.round(sx * this.dpr), 0), this.canvas.width - 1);
    const py = Math.min(Math.max(this.canvas.height - 1 - Math.round(sy * this.dpr), 0), this.canvas.height - 1);
    const out = new Uint8Array(4);
    gl.readPixels(px, py, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, out);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    return out[0] + (out[1] << 8) + (out[2] << 16) - 1;
  }

  // ── Drawing ─────────────────────────────────────────────────────────────

  setCamera(progKey) {
    const u = this.uniforms[progKey];
    this.gl.uniform2f(u.center, this.center[0], this.center[1]);
    this.gl.uniform2f(u.scale, (2 * this.zoom) / this.cssW, (-2 * this.zoom) / this.cssH);
  }

  requestRender() {
    this.pickDirty = true;
    // While the breathing loop runs it redraws every frame, so a one-off frame
    // is only needed when animation is off (reduced motion / paused).
    if (this.animating || this.renderQueued || this.destroyed) return;
    this.renderQueued = true;
    requestAnimationFrame(() => {
      this.renderQueued = false;
      if (!this.destroyed) this.draw();
    });
  }

  // ── Breathing animation ───────────────────────────────────────────────────

  startAnimation() {
    if (this.animating || this.destroyed || this.reducedMotion) return;
    this.animating = true;
    this.animStart = performance.now();
    const tick = (now) => {
      if (!this.animating || this.destroyed) return;
      this.time = (now - this.animStart) / 1000;
      this.pickDirty = true;          // positions move every frame
      this.draw();
      this.animRaf = requestAnimationFrame(tick);
    };
    this.animRaf = requestAnimationFrame(tick);
  }

  stopAnimation() {
    this.animating = false;
    if (this.animRaf) cancelAnimationFrame(this.animRaf);
    this.animRaf = 0;
  }

  setAnim(progKey) {
    const u = this.uniforms[progKey];
    this.gl.uniform1f(u.time, this.time);
    this.gl.uniform1f(u.anim, this.reducedMotion ? 0.0 : 1.0);
  }

  // Opaque gradient fill covering the whole canvas; blend off so it overwrites.
  drawBackground() {
    const gl = this.gl;
    gl.disable(gl.BLEND);
    gl.useProgram(this.bgProg);
    gl.bindVertexArray(this.bgVao);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    gl.bindVertexArray(null);
    gl.enable(gl.BLEND);
  }

  draw() {
    const gl = this.gl;
    if (this.n === 0) return;
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    this.drawBackground(); // opaque vertical gradient base — matches the dashboard --bg-gradient

    const dim = this.selected >= 0 ? 0.22 : 1.0;
    const size = this.nodeSize() * this.dpr;
    // Zoomed out, hundreds of additive lines overlap per pixel and the dense
    // core saturates to white — attenuate edge alpha until ~6x fit zoom
    const edgeAtt = Math.min(1, Math.max(0.12, this.zoom / (this.fitZoom * 6)));
    // Glow pulse synced to the geometric breath: the mesh brightens on the
    // "inhale". Phase matches the shader's sin(u_time * 0.85). Kept subtle so the
    // additive mesh doesn't saturate to white.
    const breath = this.animating ? Math.sin(this.time * 0.85) : 0;
    const glow = 1.0 + 0.06 * breath;

    // Edges: additive blending for the glowing-mesh look
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE);
    gl.useProgram(this.edgeProg);
    this.setCamera('edge');
    this.setAnim('edge');
    for (const layer of this.layers) {
      if (!layer.visible) continue;
      const [r, g, b] = layer.color;
      gl.uniform4f(this.uniforms.edge.color, r, g, b, layer.alpha * dim * edgeAtt * glow);
      gl.bindVertexArray(layer.vao);
      gl.drawElements(gl.LINES, layer.count, gl.UNSIGNED_INT, 0);
    }

    // Selected node's edges, bright on top
    if (this.selected >= 0 && this.highlightCount > 0) {
      gl.uniform4f(this.uniforms.edge.color, 1, 1, 1, 0.5);
      gl.bindVertexArray(this.highlightVao);
      gl.drawElements(gl.LINES, this.highlightCount, gl.UNSIGNED_INT, 0);
    }

    // Nodes: normal alpha blending on top of the mesh
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    gl.useProgram(this.nodeProg);
    this.setCamera('node');
    this.setAnim('node');
    gl.uniform1f(this.uniforms.node.size, size);
    gl.uniform1f(this.uniforms.node.alpha, (this.selected >= 0 ? 0.3 : 0.78) * (1.0 + 0.03 * breath));
    gl.bindVertexArray(this.nodeVao);
    gl.drawArrays(gl.POINTS, 0, this.n);

    const colorLoc = gl.getAttribLocation(this.nodeProg, 'a_color');
    if (this.selected >= 0 && this.neighborCount > 0) {
      gl.bindVertexArray(this.neighborVao);
      gl.vertexAttrib3f(colorLoc, 1, 1, 1);
      gl.uniform1f(this.uniforms.node.size, Math.max(size * 1.3, 5 * this.dpr));
      gl.uniform1f(this.uniforms.node.alpha, 0.95);
      gl.drawArrays(gl.POINTS, 0, this.neighborCount);
    }

    gl.bindVertexArray(this.markerVao);
    gl.vertexAttrib3f(colorLoc, 1, 1, 1);
    if (this.hovered >= 0) {
      gl.uniform1f(this.uniforms.node.size, Math.max(size * 1.6, 7 * this.dpr));
      gl.uniform1f(this.uniforms.node.alpha, 0.95);
      gl.drawArrays(gl.POINTS, 0, 1);
    }
    if (this.selected >= 0) {
      gl.uniform1f(this.uniforms.node.size, Math.max(size * 2.0, 9 * this.dpr));
      gl.uniform1f(this.uniforms.node.alpha, 1.0);
      gl.drawArrays(gl.POINTS, 1, 1);
    }
    gl.bindVertexArray(null);
  }

  destroy() {
    this.destroyed = true;
    this.stopAnimation();
    const ext = this.gl.getExtension('WEBGL_lose_context');
    if (ext) ext.loseContext();
  }
}
