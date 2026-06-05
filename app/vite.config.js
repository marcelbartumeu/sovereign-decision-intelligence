import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import fs from 'fs'

// Serve ../model/ GeoJSON files at /model/ for the Accessibility + Population panels
function serveModel() {
  const modelPath = path.resolve(__dirname, '../model')
  return {
    name: 'serve-model',
    configureServer(server) {
      server.middlewares.use('/model', (req, res, next) => {
        const pathname = (req.url === '/' ? '' : req.url).replace(/^\//, '').split('?')[0]
        const decoded  = decodeURIComponent(pathname)
        const file     = path.join(modelPath, decoded)
        if (!file.startsWith(modelPath) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
          return next()
        }
        res.setHeader('Content-Type', 'application/json')
        fs.createReadStream(file).pipe(res)
      })
    },
  }
}

// Serve parent Public folder at /Public so Scenario Visualization can load D MAP.png, etc.
function serveParentPublic() {
  const publicPath = path.resolve(__dirname, '../Public')
  return {
    name: 'serve-parent-public',
    configureServer(server) {
      server.middlewares.use('/Public', (req, res, next) => {
        const pathname = (req.url === '/' ? '' : req.url).replace(/^\//, '').split('?')[0]
        const decoded = decodeURIComponent(pathname)
        const file = path.join(publicPath, decoded)
        if (!file.startsWith(publicPath) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
          return next()
        }
        res.setHeader('Content-Type', getMime(path.extname(file)))
        fs.createReadStream(file).pipe(res)
      })
    },
  }
}

function getMime(ext) {
  const map = {
    '.html': 'text/html',
    '.js':   'application/javascript',
    '.mjs':  'application/javascript',
    '.css':  'text/css',
    '.json': 'application/json',
    '.png':  'image/png',
    '.jpg':  'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif':  'image/gif',
    '.webp': 'image/webp',
    '.svg':  'image/svg+xml',
    '.mp4':  'video/mp4',
    '.webm': 'video/webm',
    '.glb':  'model/gltf-binary',
    '.wasm': 'application/wasm',
  }
  return map[ext?.toLowerCase()] || 'application/octet-stream'
}

// Serve viz-abm-emotion-main/dist/ at /andorra/ — no separate server needed
function serveViz() {
  const vizDist = path.resolve(__dirname, 'viz-abm-emotion-main/dist')
  return {
    name: 'serve-viz',
    configureServer(server) {
      server.middlewares.use('/andorra', (req, res, next) => {
        const pathname = (req.url === '/' ? '/index.html' : req.url).split('?')[0]
        const decoded  = decodeURIComponent(pathname.replace(/^\//, ''))
        const file     = path.join(vizDist, decoded || 'index.html')
        if (!file.startsWith(vizDist) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
          // Fall back to index.html for SPA client-side routes
          const index = path.join(vizDist, 'index.html')
          if (fs.existsSync(index)) {
            res.setHeader('Content-Type', 'text/html')
            return fs.createReadStream(index).pipe(res)
          }
          return next()
        }
        res.setHeader('Content-Type', getMime(path.extname(file)))
        fs.createReadStream(file).pipe(res)
      })
    },
  }
}

// Serve transit-builder/dist/ at /transit-builder/ in dev
function serveTransitBuilder() {
  const distDir = path.resolve(__dirname, 'transit-builder/dist')
  return {
    name: 'serve-transit-builder',
    configureServer(server) {
      server.middlewares.use('/transit-builder', (req, res, next) => {
        const pathname = (!req.url || req.url === '/' ? '/index.html' : req.url).split('?')[0]
        const decoded  = decodeURIComponent(pathname.replace(/^\//, ''))
        const file     = path.join(distDir, decoded || 'index.html')
        if (!file.startsWith(distDir) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
          const index = path.join(distDir, 'index.html')
          if (fs.existsSync(index)) {
            res.setHeader('Content-Type', 'text/html')
            return fs.createReadStream(index).pipe(res)
          }
          return next()
        }
        res.setHeader('Content-Type', getMime(path.extname(file)))
        fs.createReadStream(file).pipe(res)
      })
    },
  }
}

// Serve vertex-earth-interactive/ at /earth/ so the globe iframe works in dev
function serveEarth() {
  const earthDir = path.resolve(__dirname, 'vertex-earth-interactive')
  return {
    name: 'serve-earth',
    configureServer(server) {
      server.middlewares.use('/earth', (req, res, next) => {
        const pathname = (!req.url || req.url === '/' ? '/index.html' : req.url).split('?')[0]
        const decoded  = decodeURIComponent(pathname.replace(/^\//, ''))
        const file     = path.join(earthDir, decoded || 'index.html')
        if (!file.startsWith(earthDir) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
          return next()
        }
        res.setHeader('Content-Type', getMime(path.extname(file)))
        fs.createReadStream(file).pipe(res)
      })
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [serveModel(), serveParentPublic(), serveViz(), serveEarth(), serveTransitBuilder(), react()],
  root: __dirname,
  publicDir: 'public',
  server: {
    fs: {
      allow: ['..'],
    },
  },
})
