// Configure @noble/ed25519 to use Node.js crypto for SHA-512 (required in Node.js 18)
import { createHash } from 'crypto';
import * as ed from '@noble/ed25519';

ed.etc.sha512Sync = (...msgs) => {
  const h = createHash('sha512');
  for (const msg of msgs) h.update(msg);
  return h.digest();
};
