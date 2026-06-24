import { createServer } from 'http';
import { readFileSync, existsSync } from 'fs';
import { join, extname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));
const DIST_DIR = join(__dirname, '..', 'dist');
const BUNDLE_PATH = process.env.BUNDLE_PATH || '/tmp/bundle.cbor';
const PORT = parseInt(process.env.PORT || '3000', 10);

const MIME = {
  '.html': 'text/html',
  '.js': 'application/javascript',
  '.mjs': 'application/javascript',
  '.cbor': 'application/cbor',
  '.json': 'application/json',
  '.css': 'text/css',
};

createServer((req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const pathname = url.pathname;

  // Serve bundle.cbor
  if (pathname === '/bundle.cbor') {
    if (!existsSync(BUNDLE_PATH)) {
      res.writeHead(404); res.end('Bundle not found. Generate one with: decpki bundle --out ' + BUNDLE_PATH);
      return;
    }
    const data = readFileSync(BUNDLE_PATH);
    res.writeHead(200, { 'Content-Type': 'application/cbor', 'Access-Control-Allow-Origin': '*' });
    res.end(data);
    return;
  }

  // Serve demo/index.html at root
  if (pathname === '/' || pathname === '/index.html') {
    const html = readFileSync(join(__dirname, 'index.html'));
    res.writeHead(200, { 'Content-Type': 'text/html' });
    res.end(html);
    return;
  }

  // Serve dist/ files (JS bundles, SW)
  const distFile = join(DIST_DIR, pathname);
  if (existsSync(distFile)) {
    const data = readFileSync(distFile);
    const ext = extname(pathname);
    res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' });
    res.end(data);
    return;
  }

  res.writeHead(404); res.end('Not found');
}).listen(PORT, () => {
  console.log(`DecPKI demo server at http://localhost:${PORT}`);
  console.log(`Bundle endpoint: /bundle.cbor → ${BUNDLE_PATH}`);
  console.log(`Set BUNDLE_PATH env var to override bundle location.`);
});
