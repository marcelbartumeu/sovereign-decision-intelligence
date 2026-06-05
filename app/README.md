# Andorra V1.4 – React Dashboard

React version of the Andorra scenario dashboard (replaces the single-page `Dashboard.HTML` with a component-based app).

## Run

```bash
npm install
npm run dev
```

Open the URL shown (e.g. http://localhost:5173). Scenario data is loaded from `public/js/scenarioData.js` (copied from `../js/scenarioData.js`).

## Build

```bash
npm run build
npm run preview   # optional: serve dist/
```

Output is in `dist/`. Deploy `dist/` to your server. For scenario images/videos (e.g. `/Public/...`), ensure your server serves the same `Public` assets as the original HTML dashboard.

## Features

- **Scenario & year sliders** – Historical (2010–2024) and future scenarios (2024–2035)
- **Tabs** – Main, Economic Matrix, Social Systems, Environmental Grid, Infrastructure
- **KPI cards** – Charts (line, area, bar, radar, doughnut) and overlay comparison of multiple scenarios
- **Scenario visualization** – Year-based images/video (paths under `/Public/`)
- **Arduino** – Web Serial connect/disconnect and button/slider messages to sync scenario and year

---
Original template: minimal React + Vite setup with HMR.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Babel](https://babeljs.io/) (or [oxc](https://oxc.rs) when used in [rolldown-vite](https://vite.dev/guide/rolldown)) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.
