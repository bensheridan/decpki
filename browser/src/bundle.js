import { decode } from 'cbor-x';
import { encodeCbor } from './cbor-canonical.js';
import { verifyEd25519 } from './crypto.js';
import { BundleValidationError } from './errors.js';

const CURRENT_FORMAT_VERSION = 1;

function toUint8(v) {
  if (v instanceof Uint8Array) return v;
  if (v instanceof ArrayBuffer) return new Uint8Array(v);
  if (Array.isArray(v)) return new Uint8Array(v);
  return v;
}

export function decodeBundle(arrayBuffer) {
  const raw = new Uint8Array(arrayBuffer);
  const m = decode(raw);

  if (m.fmt_ver !== CURRENT_FORMAT_VERSION) {
    throw new BundleValidationError(
      'version',
      `Unknown bundle format version: ${m.fmt_ver} (expected ${CURRENT_FORMAT_VERSION})`
    );
  }

  const identities = (m.identities || []).map((entry) => ({
    record: {
      did: entry.did,
      publicKey: toUint8(entry.pubkey),
      issuedAt: entry.issued_at,
      issuedBy: entry.issued_by,
      validUntil: entry.valid_until ?? null,
      revokedAt: entry.revoked_at ?? null,
      metadata: entry.meta || {},
    },
    proof: {
      leafHash: toUint8(entry.proof.leaf),
      siblings: (entry.proof.siblings || []).map((s) => ({
        h: toUint8(s.h),
        s: s.s,
      })),
      root: toUint8(entry.proof.root),
    },
  }));

  const signatures = (m.signatures || []).map((sig) => ({
    validatorDid: sig.val_did,
    validatorPubkey: toUint8(sig.val_pk),
    signature: toUint8(sig.sig),
  }));

  return {
    fmtVer: m.fmt_ver,
    snapBlock: m.snap_block,
    snapRoot: toUint8(m.snap_root),
    issuedAt: m.issued_at,
    expiresAt: m.expires_at,
    threshold: m.threshold,
    valSet: m.val_set || [],
    identities,
    signatures,
  };
}

// Re-encode the canonical signing payload (same structure as Python's serialise_bundle_for_signing)
// Must match: cbor2.dumps(m, canonical=True) with signatures=[]
function buildSigningPayload(bundle) {
  const identitiesCbor = bundle.identities.map((entry) => ({
    did: entry.record.did,
    issued_at: entry.record.issuedAt,
    issued_by: entry.record.issuedBy,
    meta: entry.record.metadata,
    proof: {
      leaf: entry.proof.leafHash,
      root: entry.proof.root,
      siblings: entry.proof.siblings.map((s) => ({ h: s.h, s: s.s })),
    },
    pubkey: entry.record.publicKey,
    revoked_at: entry.record.revokedAt,
    valid_until: entry.record.validUntil,
  }));

  // Keys must be sorted canonically (CBOR canonical = lexicographic key order)
  const payload = {
    expires_at: bundle.expiresAt,
    fmt_ver: bundle.fmtVer,
    identities: identitiesCbor,
    issued_at: bundle.issuedAt,
    signatures: [],
    snap_block: bundle.snapBlock,
    snap_root: bundle.snapRoot,
    threshold: bundle.threshold,
    val_set: bundle.valSet,
  };

  return encodeCbor(payload);
}

export async function validateBundle(bundle) {
  if (bundle.fmtVer !== CURRENT_FORMAT_VERSION) {
    throw new BundleValidationError('version', `Unsupported format version: ${bundle.fmtVer}`);
  }

  const now = Math.floor(Date.now() / 1000);
  if (bundle.expiresAt <= now) {
    throw new BundleValidationError('expired', 'Bundle has expired');
  }

  const signingPayload = buildSigningPayload(bundle);

  let validSigCount = 0;
  for (const sig of bundle.signatures) {
    const ok = await verifyEd25519(sig.validatorPubkey, signingPayload, sig.signature);
    if (ok) validSigCount++;
  }

  if (validSigCount < bundle.threshold) {
    throw new BundleValidationError(
      'quorum',
      `Quorum failure: ${validSigCount} valid signatures, need ${bundle.threshold}`
    );
  }

  // Attach valid signature count for downstream use
  bundle._validSigCount = validSigCount;
  return bundle;
}
