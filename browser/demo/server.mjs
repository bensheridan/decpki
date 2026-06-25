import { createServer, request as httpRequest } from 'http';
import { readFileSync, existsSync } from 'fs';
import { join, extname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));
const DIST_DIR = join(__dirname, '..', 'dist');
const SRC_DIR = join(__dirname, '..', 'src');
const BUNDLE_PATH = process.env.BUNDLE_PATH || '/tmp/bundle.cbor';
const PORT = parseInt(process.env.PORT || '3000', 10);
const BFF_PORT = parseInt(process.env.BFF_PORT || '8000', 10);

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

  // Proxy /enrolment/* and /login/* to the BFF
  if (pathname.startsWith('/enrolment') || pathname.startsWith('/login')) {
    const options = {
      hostname: '127.0.0.1',
      port: BFF_PORT,
      path: req.url,
      method: req.method,
      headers: { ...req.headers, host: `127.0.0.1:${BFF_PORT}` },
    };
    const proxy = httpRequest(options, (bffRes) => {
      res.writeHead(bffRes.statusCode, bffRes.headers);
      bffRes.pipe(res);
    });
    proxy.on('error', () => {
      res.writeHead(502, { 'Content-Type': 'text/plain' });
      res.end(`BFF unreachable — start it with: cd bff && uvicorn main:app --port ${BFF_PORT}`);
    });
    req.pipe(proxy);
    return;
  }

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

  // Serve demo HTML pages
  if (pathname === '/' || pathname === '/index.html') {
    const html = readFileSync(join(__dirname, 'index.html'));
    res.writeHead(200, { 'Content-Type': 'text/html' });
    res.end(html);
    return;
  }
  if (pathname === '/register.html') {
    const html = readFileSync(join(__dirname, 'register.html'));
    res.writeHead(200, { 'Content-Type': 'text/html' });
    res.end(html);
    return;
  }
  if (pathname === '/login.html') {
    const html = readFileSync(join(__dirname, 'login.html'));
    res.writeHead(200, { 'Content-Type': 'text/html' });
    res.end(html);
    return;
  }

  // Serve src/ files (for ESM demo import of registration.js)
  const srcFile = join(SRC_DIR, pathname.replace(/^\/src\//, ''));
  if (pathname.startsWith('/src/') && existsSync(srcFile)) {
    const data = readFileSync(srcFile);
    const ext = extname(pathname);
    res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' });
    res.end(data);
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
  console.log(`Registration demo: http://localhost:${PORT}/register.html`);
  console.log(`Login demo: http://localhost:${PORT}/login.html`);
  console.log(`BFF proxy: /enrolment/* /login/* → http://localhost:${BFF_PORT} (set BFF_PORT to override)`);
});
