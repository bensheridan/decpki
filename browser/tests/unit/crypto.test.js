import { describe, it, expect } from 'vitest';
import { sha256, hashLeaf, hashNode, verifyMerkleProof } from '../../src/crypto.js';

describe('sha256', () => {
  it('produces a 32-byte result', async () => {
    const result = await sha256(new Uint8Array([1, 2, 3]));
    expect(result).toBeInstanceOf(Uint8Array);
    expect(result.length).toBe(32);
  });

  it('is deterministic', async () => {
    const a = await sha256(new Uint8Array([0xff]));
    const b = await sha256(new Uint8Array([0xff]));
    expect(a).toEqual(b);
  });
});

describe('hashLeaf', () => {
  it('prepends 0x00 before hashing', async () => {
    const data = new Uint8Array([0xab, 0xcd]);
    const direct = await sha256(new Uint8Array([0x00, 0xab, 0xcd]));
    const result = await hashLeaf(data);
    expect(result).toEqual(direct);
  });
});

describe('hashNode', () => {
  it('prepends 0x01 and concatenates left+right', async () => {
    const left = new Uint8Array([0x01]);
    const right = new Uint8Array([0x02]);
    const direct = await sha256(new Uint8Array([0x01, 0x01, 0x02]));
    const result = await hashNode(left, right);
    expect(result).toEqual(direct);
  });
});

describe('verifyMerkleProof', () => {
  it('returns true for a valid single-leaf proof (empty siblings)', async () => {
    const leafData = new TextEncoder().encode('hello');
    const leafHash = await hashLeaf(leafData);
    // A single-leaf tree: root == leafHash, no siblings
    expect(await verifyMerkleProof(leafData, [], leafHash)).toBe(true);
  });

  it('returns true for a two-leaf proof', async () => {
    const leaf0 = new TextEncoder().encode('leaf0');
    const leaf1 = new TextEncoder().encode('leaf1');
    const h0 = await hashLeaf(leaf0);
    const h1 = await hashLeaf(leaf1);
    const root = await hashNode(h0, h1);

    // Proof for leaf0: sibling is h1 on the right
    expect(await verifyMerkleProof(leaf0, [{ h: h1, s: 'right' }], root)).toBe(true);
    // Proof for leaf1: sibling is h0 on the left
    expect(await verifyMerkleProof(leaf1, [{ h: h0, s: 'left' }], root)).toBe(true);
  });

  it('returns false when sibling hash is tampered', async () => {
    const leaf0 = new TextEncoder().encode('leaf0');
    const leaf1 = new TextEncoder().encode('leaf1');
    const h0 = await hashLeaf(leaf0);
    const h1 = await hashLeaf(leaf1);
    const root = await hashNode(h0, h1);

    const tampered = new Uint8Array(h1);
    tampered[0] ^= 0xff;
    expect(await verifyMerkleProof(leaf0, [{ h: tampered, s: 'right' }], root)).toBe(false);
  });

  it('returns false when root does not match', async () => {
    const leaf = new TextEncoder().encode('test');
    const wrongRoot = new Uint8Array(32).fill(0xaa);
    expect(await verifyMerkleProof(leaf, [], wrongRoot)).toBe(false);
  });
});
