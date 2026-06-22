import { Component } from 'react';

// Isolates map (Mapbox/WebGL) failures so a rendering-context error degrades to a
// themed "signal lost" panel instead of blanking the whole console. The reorg
// removed the original boundary; this restores that safety with an on-brand fallback.
export default class MapErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error) {
    // eslint-disable-next-line no-console
    console.error('Map view failed:', error);
  }

  render() {
    if (this.state.failed) {
      return (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: '0.6rem',
          background: 'var(--bg-gradient)',
        }}>
          <div style={{
            fontFamily: 'var(--mono)', fontSize: 14, fontWeight: 600,
            letterSpacing: '0.22em', textTransform: 'uppercase', color: 'var(--alert)',
          }}>
            ◈ Signal Lost
          </div>
          <div style={{
            fontFamily: 'var(--mono)', fontSize: 11, letterSpacing: '0.12em',
            color: 'var(--lbl)', textTransform: 'uppercase',
          }}>
            Recon feed unavailable — rendering context offline
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
