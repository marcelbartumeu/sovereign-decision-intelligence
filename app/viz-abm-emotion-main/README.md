# h-ABM Urban Simulation Dashboard

This project is a web-based dashboard for visualizing h-ABM (human Agent-Based Model) simulations in an urban context. It features a map view for spatial data visualization and a dedicated visualization view for emotional states and other metrics.

## Features

- Interactive map view with DeckGL and Mapbox GL JS
- Real-time KPI visualization
- Emotional state visualization with Three.js
- Responsive design
- Interactive sliders for emotion control

## Prerequisites

- Node.js (v16.20.2 or higher)
- npm (v8.19.4 or higher)
- A Mapbox API token

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd hABM-table
```

2. Install dependencies:
```bash
npm install
```

3. Create a `.env` file in the root directory and add your Mapbox token:
```
VITE_MAPBOX_TOKEN=your_mapbox_token_here
```

4. Start the development server:
```bash
npm run dev
```

## Project Structure

```
src/
  ├── components/         # Reusable components
  │   └── HABMSentiments.tsx
  ├── pages/             # Page components
  │   ├── MapView.tsx
  │   └── VisualizationView.tsx
  ├── styles/            # Global styles
  ├── App.tsx           # Main application component
  └── main.tsx         # Application entry point
```

## Usage

The application consists of two main views:

1. **Map View**: Displays a map with agent locations and various KPIs
   - Visualizes agent positions using DeckGL
   - Shows real-time metrics in an overlay

2. **Visualization View**: Contains three sections
   - Data Analysis panel
   - Two Emotional State visualizations
   - Interactive controls for each visualization

## Development

To start the development server:

```bash
npm run dev
```

To build for production:

```bash
npm run build
```

## License

MIT
