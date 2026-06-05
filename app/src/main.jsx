import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import PaperDashboard from './PaperDashboard.jsx'
import ProjectorView from './ProjectorView.jsx'
import './index.css'
import 'leaflet/dist/leaflet.css'

const params = new URLSearchParams(window.location.search)
const usePaperDashboard = params.get('paper') === '1'
const useProjector      = params.has('projector')

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    {usePaperDashboard ? <PaperDashboard />
     : useProjector    ? <ProjectorView />
     :                   <App />}
  </React.StrictMode>,
)
