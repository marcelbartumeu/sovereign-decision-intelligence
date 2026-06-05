import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import styled from 'styled-components';
import MapView from './pages/MapView';
import Map3DView from './pages/Map3DView';
import VisualizationView from './pages/VisualizationView';
import DualVisualizationView from './pages/DualVisualizationView';
import KPIDashboard from './pages/KPIDashboard';
import MapDashboard from './pages/MapDashboard';
import AgentAnalyticsView from './pages/AgentAnalyticsView';
import { SharedStateProvider } from './services/SharedStateContext';
import { Component, ErrorInfo, ReactNode } from 'react';

const MainContainer = styled.div`
  height: 100vh;
`;

class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(_: Error) {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Error caught by boundary:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '20px', textAlign: 'center' }}>
          <h2>Something went wrong.</h2>
          <button onClick={() => this.setState({ hasError: false })}>Try again</button>
        </div>
      );
    }

    return this.props.children;
  }
}

function App() {
  return (
    <ErrorBoundary>
      <SharedStateProvider>
        <Router basename={import.meta.env.BASE_URL}>
          <MainContainer>
            <Routes>
              <Route path="/" element={<Navigate to="/kpi" replace />} />
              <Route path="/kpi" element={<KPIDashboard />} />
              <Route path="/map-dashboard" element={<MapDashboard />} />
              <Route path="/map" element={<MapView />} />
              <Route path="/map3d" element={<Map3DView />} />
              <Route path="/visualization" element={<VisualizationView />} />
              <Route path="/visualization/dual" element={<DualVisualizationView />} />
              <Route path="/agent-analytics" element={<AgentAnalyticsView />} />
            </Routes>
          </MainContainer>
        </Router>
      </SharedStateProvider>
    </ErrorBoundary>
  );
}

export default App;
