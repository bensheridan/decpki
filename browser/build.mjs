import * as esbuild from 'esbuild';
import { copyFileSync } from 'fs';

const sharedOpts = {
  bundle: true,
  minify: true,
  sourcemap: false,
  target: ['chrome113', 'firefox129', 'safari17'],
};

// ESM client library
await esbuild.build({
  ...sharedOpts,
  entryPoints: ['src/index.js'],
  outfile: 'dist/decpki-client.mjs',
  format: 'esm',
  platform: 'browser',
});

// IIFE client library (for script tag / demo)
await esbuild.build({
  ...sharedOpts,
  entryPoints: ['src/index.js'],
  outfile: 'dist/decpki-client.iife.js',
  format: 'iife',
  globalName: 'DecPKILib',
  platform: 'browser',
});

// Service Worker — must be IIFE, cannot be ESM in all target browsers
await esbuild.build({
  ...sharedOpts,
  entryPoints: ['sw/decpki-sw.js'],
  outfile: 'dist/decpki-sw.js',
  format: 'iife',
  platform: 'browser',
});

console.log('Build complete: dist/decpki-client.mjs, dist/decpki-client.iife.js, dist/decpki-sw.js');
