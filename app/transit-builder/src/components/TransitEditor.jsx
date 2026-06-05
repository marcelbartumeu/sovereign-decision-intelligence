import { useState, useCallback } from 'react'
import './TransitEditor.css'

const LINE_COLORS = [
  '#0A84FF', // blue
  '#FF453A', // red
  '#30D158', // green
  '#FFD60A', // yellow
  '#BF5AF2', // purple
  '#FF9F0A', // orange
  '#64D2FF', // cyan
  '#FF375F', // pink
]

const TRANSPORT_MEDIA = [
  { id: 'bus',   label: 'Bus' },
  { id: 'tram',  label: 'Tram' },
  { id: 'metro', label: 'Metro' },
  { id: 'rail',  label: 'Rail' },
]

let lineCounter = 0
const nextLineId = () => `line-${++lineCounter}`

export default function TransitEditor({
  visible,
  editing,
  onToggleEdit,
  lines,
  setLines,
  activeLineId,
  setActiveLineId,
  onRunEdit,
}) {
  const [collapsed, setCollapsed] = useState(false)

  const addLine = useCallback(() => {
    const id = nextLineId()
    const usedColors = new Set(lines.map(l => l.color))
    const color = LINE_COLORS.find(c => !usedColors.has(c)) ?? LINE_COLORS[lines.length % LINE_COLORS.length]
    const newLine = {
      id,
      name: `Line ${lines.length + 1}`,
      color,
      medium: 'bus',
      frequency: 10,
      stops: [],
    }
    setLines([...lines, newLine])
    setActiveLineId(id)
  }, [lines, setLines, setActiveLineId])

  const updateLine = useCallback((id, patch) => {
    setLines(lines.map(l => (l.id === id ? { ...l, ...patch } : l)))
  }, [lines, setLines])

  const deleteLine = useCallback((id) => {
    const next = lines.filter(l => l.id !== id)
    setLines(next)
    if (activeLineId === id) {
      setActiveLineId(next.length ? next[next.length - 1].id : null)
    }
  }, [lines, setLines, activeLineId, setActiveLineId])

  const removeStop = useCallback((lineId, stopId) => {
    setLines(lines.map(l =>
      l.id === lineId ? { ...l, stops: l.stops.filter(s => s.id !== stopId) } : l
    ))
  }, [lines, setLines])

  if (!visible) return null

  return (
    <div className={`transit-editor ${collapsed ? 'collapsed' : ''}`}>
      {/* Pencil tab that protrudes from the white panel */}
      <button
        className={`transit-pencil ${editing ? 'active' : ''}`}
        onClick={() => {
          if (collapsed) setCollapsed(false)
          onToggleEdit()
        }}
        title={editing ? 'Exit edit mode' : 'Edit transit lines'}
      >
        <span className="transit-pencil-icon">✏️</span>
      </button>

      <button
        className="transit-collapse"
        onClick={() => setCollapsed(c => !c)}
        title={collapsed ? 'Expand' : 'Collapse'}
      >
        {collapsed ? '‹' : '›'}
      </button>

      {!collapsed && (
        <div className="transit-panel">
          <div className="transit-header">
            <div className="transit-title">Transit Editor</div>
            <div className="transit-subtitle">
              {editing
                ? 'Click on the map to add stops'
                : 'Press ✏️ to start editing'}
            </div>
          </div>

          <div className="transit-lines">
            {lines.length === 0 && (
              <div className="transit-empty">No lines yet. Add one to begin.</div>
            )}
            {lines.map(line => {
              const isActive = line.id === activeLineId
              return (
                <div
                  key={line.id}
                  className={`transit-line-card ${isActive ? 'active' : ''}`}
                  onClick={() => setActiveLineId(line.id)}
                >
                  <div className="transit-line-row">
                    <span
                      className="transit-line-dot"
                      style={{ background: line.color, boxShadow: `0 0 10px ${line.color}66` }}
                    />
                    <input
                      className="transit-line-name"
                      value={line.name}
                      onChange={e => updateLine(line.id, { name: e.target.value })}
                      onClick={e => e.stopPropagation()}
                    />
                    <button
                      className="transit-line-delete"
                      onClick={e => { e.stopPropagation(); deleteLine(line.id) }}
                      title="Delete line"
                    >
                      ×
                    </button>
                  </div>

                  <div className="transit-color-row">
                    {LINE_COLORS.map(c => (
                      <button
                        key={c}
                        className={`transit-color-swatch ${line.color === c ? 'selected' : ''}`}
                        style={{ background: c }}
                        onClick={e => { e.stopPropagation(); updateLine(line.id, { color: c }) }}
                      />
                    ))}
                  </div>

                  <div className="transit-meta-row">
                    <select
                      className="transit-select"
                      value={line.medium}
                      onChange={e => updateLine(line.id, { medium: e.target.value })}
                      onClick={e => e.stopPropagation()}
                    >
                      {TRANSPORT_MEDIA.map(m => (
                        <option key={m.id} value={m.id}>{m.label}</option>
                      ))}
                    </select>
                    <div className="transit-freq">
                      <input
                        type="number"
                        min="1"
                        max="120"
                        value={line.frequency}
                        onChange={e => updateLine(line.id, { frequency: Number(e.target.value) || 1 })}
                        onClick={e => e.stopPropagation()}
                      />
                      <span>min</span>
                    </div>
                  </div>

                  <div className="transit-stops-info">
                    {line.stops.length} stop{line.stops.length === 1 ? '' : 's'}
                    {line.stops.length > 0 && (
                      <button
                        className="transit-clear-stops"
                        onClick={e => {
                          e.stopPropagation()
                          line.stops.forEach(s => removeStop(line.id, s.id))
                        }}
                      >
                        clear
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>

          <button className="transit-add-line" onClick={addLine}>
            + Add Line
          </button>

          <button
            className="transit-run-edit"
            onClick={onRunEdit}
            disabled={lines.every(l => l.stops.length === 0)}
          >
            ▶ Run Edit
          </button>
        </div>
      )}
    </div>
  )
}
