// Minimal canonical CBOR encoder (RFC 7049 §3.9)
// Canonical rules:
// 1. Integers: shortest encoding
// 2. Maps: sorted by canonical encoding of key (length first, then bytes)
// 3. No indefinite-length encoding
//
// Supports: null, boolean, integer (≥0), string, Uint8Array, Array, plain Object

const MAJOR_UINT = 0;
const MAJOR_BSTR = 2;
const MAJOR_TSTR = 3;
const MAJOR_ARRAY = 4;
const MAJOR_MAP = 5;
const MAJOR_SIMPLE = 7;

const SIMPLE_FALSE = 0xf4;
const SIMPLE_TRUE = 0xf5;
const SIMPLE_NULL = 0xf6;

function writeHead(major, value, buf) {
  const base = major << 5;
  if (value <= 23) {
    buf.push(base | value);
  } else if (value <= 0xff) {
    buf.push(base | 24, value);
  } else if (value <= 0xffff) {
    buf.push(base | 25, (value >> 8) & 0xff, value & 0xff);
  } else if (value <= 0xffffffff) {
    buf.push(base | 26, (value >> 24) & 0xff, (value >> 16) & 0xff, (value >> 8) & 0xff, value & 0xff);
  } else {
    // 8-byte uint (for timestamps > 2^32)
    buf.push(base | 27);
    // JS integers are safe up to 2^53; encode as BigInt for safety
    const hi = Math.floor(value / 0x100000000);
    const lo = value >>> 0;
    buf.push((hi >> 24) & 0xff, (hi >> 16) & 0xff, (hi >> 8) & 0xff, hi & 0xff,
             (lo >> 24) & 0xff, (lo >> 16) & 0xff, (lo >> 8) & 0xff, lo & 0xff);
  }
}

function encodeItem(value, buf) {
  if (value === null || value === undefined) {
    buf.push(SIMPLE_NULL);
    return;
  }
  if (value === true) { buf.push(SIMPLE_TRUE); return; }
  if (value === false) { buf.push(SIMPLE_FALSE); return; }

  if (typeof value === 'number') {
    if (Number.isInteger(value) && value >= 0) {
      writeHead(MAJOR_UINT, value, buf);
    } else {
      throw new Error(`Unsupported number in canonical CBOR: ${value}`);
    }
    return;
  }

  if (typeof value === 'string') {
    const bytes = new TextEncoder().encode(value);
    writeHead(MAJOR_TSTR, bytes.length, buf);
    for (const b of bytes) buf.push(b);
    return;
  }

  if (value instanceof Uint8Array || value instanceof ArrayBuffer) {
    const bytes = value instanceof ArrayBuffer ? new Uint8Array(value) : value;
    writeHead(MAJOR_BSTR, bytes.length, buf);
    for (const b of bytes) buf.push(b);
    return;
  }

  if (Array.isArray(value)) {
    writeHead(MAJOR_ARRAY, value.length, buf);
    for (const item of value) encodeItem(item, buf);
    return;
  }

  if (typeof value === 'object') {
    // Canonical map: sort keys by their encoded CBOR representation
    const entries = Object.entries(value);
    const encoded = entries.map(([k, v]) => {
      const kBuf = [];
      encodeItem(k, kBuf);
      return { kBytes: new Uint8Array(kBuf), v };
    });
    // Sort by encoded key: shorter first, then lexicographic
    encoded.sort((a, b) => {
      if (a.kBytes.length !== b.kBytes.length) return a.kBytes.length - b.kBytes.length;
      for (let i = 0; i < a.kBytes.length; i++) {
        if (a.kBytes[i] !== b.kBytes[i]) return a.kBytes[i] - b.kBytes[i];
      }
      return 0;
    });
    writeHead(MAJOR_MAP, encoded.length, buf);
    for (const { kBytes, v } of encoded) {
      for (const b of kBytes) buf.push(b);
      encodeItem(v, buf);
    }
    return;
  }

  throw new Error(`Unsupported type in canonical CBOR: ${typeof value}`);
}

export function encodeCbor(value) {
  const buf = [];
  encodeItem(value, buf);
  return new Uint8Array(buf);
}
