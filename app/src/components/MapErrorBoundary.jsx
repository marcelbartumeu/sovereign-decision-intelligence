import { Component } from 'react';

export default class MapErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { crashed: false };
  }

  static getDerivedStateFromError() {
    return { crashed: true };
  }

  componentDidCatch(err) {
    console.error('[MapErrorBoundary]', err);
  }

  reset() {
    this.setState({ crashed: false });
  }

  render() {
    if (this.state.crashed) {
      return (
        <div style={{
          position: 'absolute', inset: 0, background: '#0d0d0d',
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 12,
        }}>
          <span style={{ color: '#9ca3af', fontSize: 13, fontFamily: 'IBM Plex Mono, monospace' }}>
            Map reloading…
          </span>
          <button
            onClick={() => this.reset()}
            style={{
              background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.15)',
              color: '#e5e7eb', borderRadius: 6, padding: '6px 18px',
              fontSize: 12, cursor: 'pointer', fontFamily: 'IBM Plex Mono, monospace',
            }}
          >
            Reload map
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
