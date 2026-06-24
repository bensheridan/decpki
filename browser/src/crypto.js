import * as noble from '@noble/ed25519';

// Feature-detect native Web Crypto Ed25519 support (Chrome 113+, Safari 17+, Firefox 129+)
let _nativeEd25519 = null;
export async function detectEd25519Support() {
  if (_nativeEd25519 !== null) return _nativeEd25519;
  try {
    const key = new Uint8Array(32);
    await crypto.subtle.importKey('raw', key, { name: 'Ed25519' }, false, ['verify']);
    _nativeEd25519 = true;
  } catch {
    _nativeEd25519 = false;
  }
  return _nativeEd25519;
}

export async function verifyEd25519(publicKeyBytes, message, signatureBytes) {
  const native = await detectEd25519Support();
  if (native) {
    const key = await crypto.subtle.importKey(
      'raw',
      publicKeyBytes,
      { name: 'Ed25519' },
      false,
      ['verify']
    );
    return crypto.subtle.verify({ name: 'Ed25519' }, key, signatureBytes, message);
  }
  // Noble fallback
  return noble.verify(signatureBytes, message, publicKeyBytes);
}

export async function sha256(data) {
  const buf = await crypto.subtle.digest('SHA-256', data);
  return new Uint8Array(buf);
}

export async function hashLeaf(leafBytes) {
  const prefix = new Uint8Array([0x00]);
  const combined = new Uint8Array(1 + leafBytes.length);
  combined.set(prefix, 0);
  combined.set(leafBytes, 1);
  return sha256(combined);
}

export async function hashNode(left, right) {
  const combined = new Uint8Array(1 + left.length + right.length);
  combined[0] = 0x01;
  combined.set(left, 1);
  combined.set(right, 1 + left.length);
  return sha256(combined);
}

// Verify Merkle proof using a pre-computed leaf hash (covers the case where
// re-serializing the leaf is not feasible due to CBOR encoding divergence).
// The leaf hash must come from a trusted source (e.g. covered by validator signatures).
export async function verifyMerkleProofFromHash(leafHash, siblings, rootBytes) {
  let current = leafHash instanceof Uint8Array ? leafHash : new Uint8Array(leafHash);
  for (const { h, s } of siblings) {
    const sibling = h instanceof Uint8Array ? h : new Uint8Array(h);
    current = s === 'left'
      ? await hashNode(sibling, current)
      : await hashNode(current, sibling);
  }
  if (current.length !== rootBytes.length) return false;
  for (let i = 0; i < current.length; i++) {
    if (current[i] !== rootBytes[i]) return false;
  }
  return true;
}

export async function verifyMerkleProof(leafBytes, siblings, rootBytes) {
  let current = await hashLeaf(leafBytes);
  for (const { h, s } of siblings) {
    const sibling = h instanceof Uint8Array ? h : new Uint8Array(h);
    current = s === 'left'
      ? await hashNode(sibling, current)
      : await hashNode(current, sibling);
  }
  if (current.length !== rootBytes.length) return false;
  for (let i = 0; i < current.length; i++) {
    if (current[i] !== rootBytes[i]) return false;
  }
  return true;
}
