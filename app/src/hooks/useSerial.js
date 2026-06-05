import { useState, useRef, useCallback } from 'react';

/**
 * useSerial — Web Serial API bridge for the Andorra physical controller.
 *
 * Callbacks (all optional):
 *   onYearChange(year)              year ∈ [2010, 2049]
 *   onTabChange(tabId)              e.g. "social"
 *   onOverlayChange(scenario, state) scenario name + boolean
 *   onMapLayerChange(layerId)       e.g. "growth" — driven by ENC1 rotation
 *   onSimulationToggle()            ENC1 button press
 *   onAgentHover(index)             ENC2 rotation — agent index 0-9
 *   onAgentSelect(index)            ENC2 button press — confirms hovered agent
 *
 * Arduino protocol handled:
 *   {"type":"year",        "value":2035}
 *   {"type":"tab",         "value":"social"}
 *   {"type":"toggle",      "scenario":"overgrowth", "state":true}
 *   {"type":"encoder",     "id":1, "direction":"CW", "position":4}
 *   {"type":"encoder",     "id":2, "direction":"CW", "position":3}
 *   {"type":"encoder_btn", "id":1}
 *   {"type":"encoder_btn", "id":2}
 *   {"type":"zoom",        "value":"Parish"}   — reserved, no UI action yet
 *   {"type":"status",      "value":"ready"}    — keep-alive, ignored
 */

// Must match LAYERS order in MapVisualization.jsx
const MAP_LAYERS = ['base', 'agents', 'growth', 'tourism', 'accessibility', 'population'];

export function useSerial(
  onYearChange,
  onTabChange,
  onOverlayChange,
  onMapLayerChange,
  onSimulationToggle,
  onAgentHover,
  onAgentSelect,
) {
  const [connected, setConnected] = useState(false);
  const [status,    setStatus]    = useState('Disconnected');
  const portRef                   = useRef(null);
  const readerRef                 = useRef(null);

  // Track encoder positions so we can derive layer / agent index from absolute pos
  const enc1PosRef = useRef(0);
  const enc2PosRef = useRef(0);
  // Tracks the ENC1 position received on connect. null = not connected yet.
  // While the encoder sits at that position (even across repeated messages), we
  // ignore it so the Arduino's resting position never overrides the 'base' default.
  // Once the encoder actually moves away from the initial position, we clear this
  // guard and process all future messages normally.
  const enc1InitPosRef = useRef(null);
  const enc1MovedRef   = useRef(false);

  // ── Message dispatcher ──────────────────────────────────────────────────────

  const handleMessage = useCallback((msg) => {
    switch (msg.type) {

      case 'year': {
        const year = parseInt(msg.value, 10);
        if (!Number.isNaN(year) && year >= 2010 && year <= 2049) {
          onYearChange?.(year);
        }
        break;
      }

      case 'tab': {
        if (typeof msg.value === 'string') onTabChange?.(msg.value);
        break;
      }

      case 'toggle': {
        if (typeof msg.scenario === 'string') {
          onOverlayChange?.(msg.scenario, Boolean(msg.state));
        }
        break;
      }

      case 'encoder': {
        const pos = parseInt(msg.position, 10);
        if (Number.isNaN(pos)) break;

        if (msg.id === 1) {
          // ENC1 → cycle map layers
          enc1PosRef.current = pos;

          if (enc1InitPosRef.current === null) {
            // First message on this connect: record the physical resting position.
            // Don't dispatch a layer change — keeps 'base' as the startup default.
            enc1InitPosRef.current = pos;
            break;
          }
          if (!enc1MovedRef.current) {
            if (pos === enc1InitPosRef.current) {
              // Encoder is still at its initial position (repeated startup message).
              break;
            }
            // Encoder has moved away from initial position — unlock all future messages.
            enc1MovedRef.current = true;
          }

          const idx = ((pos % MAP_LAYERS.length) + MAP_LAYERS.length) % MAP_LAYERS.length;
          onMapLayerChange?.(MAP_LAYERS[idx]);
        } else if (msg.id === 2) {
          // ENC2 → hover agents; pass raw position, consumer handles agent-count wrapping
          enc2PosRef.current = pos;
          onAgentHover?.(pos);
          onMapLayerChange?.('agents');
        }
        break;
      }

      case 'encoder_btn': {
        if (msg.id === 1) {
          // ENC1 push → toggle simulation (bus animation)
          onSimulationToggle?.();
        } else if (msg.id === 2) {
          // ENC2 push → select currently hovered agent + ensure agents view is active
          onAgentSelect?.(enc2PosRef.current);
          onMapLayerChange?.('agents');
        }
        break;
      }

      case 'zoom':
      case 'status':
        break;   // reserved / keep-alive

      default:
        break;
    }
  }, [onYearChange, onTabChange, onOverlayChange, onMapLayerChange,
      onSimulationToggle, onAgentHover, onAgentSelect]);

  // ── Connect ────────────────────────────────────────────────────────────────

  const connect = useCallback(async () => {
    if (!('serial' in navigator)) {
      setStatus('Unsupported');
      alert('Web Serial API not supported. Use Chrome or Edge.');
      return;
    }
    try {
      const port = await navigator.serial.requestPort();
      await port.open({ baudRate: 115200 });
      portRef.current = port;
      enc1InitPosRef.current = null;  // reset guards on each new connection
      enc1MovedRef.current   = false;
      setConnected(true);
      setStatus('Connected');

      const decoder = new TextDecoder();
      let buffer = '';
      const reader = port.readable.getReader();
      readerRef.current = reader;

      try {
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';
          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed) continue;
            try { handleMessage(JSON.parse(trimmed)); } catch (_) {}
          }
        }
      } finally {
        reader.releaseLock();
        readerRef.current = null;
      }
    } catch (err) {
      setConnected(false);
      setStatus('Disconnected');
      portRef.current = null;
      readerRef.current = null;
      if (err.name !== 'NotFoundError') alert('Failed to connect: ' + err.message);
    }
  }, [handleMessage]);

  // ── Disconnect ─────────────────────────────────────────────────────────────

  const disconnect = useCallback(async () => {
    try {
      readerRef.current?.cancel();
      await portRef.current?.close();
    } catch (_) {}
    portRef.current   = null;
    readerRef.current = null;
    setConnected(false);
    setStatus('Disconnected');
  }, []);

  const toggle = useCallback(() => {
    if (connected) disconnect(); else connect();
  }, [connected, connect, disconnect]);

  return { connected, status, toggle };
}
