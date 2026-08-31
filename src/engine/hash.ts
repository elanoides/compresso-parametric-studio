/**
 * Synchronous SHA-256 used as the deterministic noise source for jitter,
 * scanline shift and randomized module-font assignment.
 *
 * Web Crypto is async, so it cannot be used inside the render loop. The digest
 * is fed UTF-8 bytes, which keeps Cyrillic salts (glyph characters) meaningful
 * instead of collapsing them.
 */

const K = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4,
  0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe,
  0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f,
  0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
  0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc,
  0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
  0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116,
  0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7,
  0xc67178f2,
]);

const encoder = new TextEncoder();

// Reused across calls: the render loop hashes thousands of times per frame.
const w = new Uint32Array(64);
const h = new Uint32Array(8);
const digestOut = new Uint32Array(8);

function rotr(x: number, n: number): number {
  return (x >>> n) | (x << (32 - n));
}

/** SHA-256 of `bytes`, returned as eight big-endian 32-bit words. */
function sha256Words(bytes: Uint8Array): Uint32Array {
  h[0] = 0x6a09e667;
  h[1] = 0xbb67ae85;
  h[2] = 0x3c6ef372;
  h[3] = 0xa54ff53a;
  h[4] = 0x510e527f;
  h[5] = 0x9b05688c;
  h[6] = 0x1f83d9ab;
  h[7] = 0x5be0cd19;

  const byteLength = bytes.length;
  const bitLengthHi = Math.floor((byteLength / 0x20000000) | 0);
  const bitLengthLo = (byteLength << 3) >>> 0;
  // Padded length: message + 0x80 marker + 8 length bytes, rounded up to 64.
  const totalLength = (Math.floor((byteLength + 8) / 64) + 1) << 6;

  for (let blockStart = 0; blockStart < totalLength; blockStart += 64) {
    for (let i = 0; i < 16; i += 1) {
      const base = blockStart + i * 4;
      let word = 0;
      for (let b = 0; b < 4; b += 1) {
        const index = base + b;
        let byte = 0;
        if (index < byteLength) {
          byte = bytes[index];
        } else if (index === byteLength) {
          byte = 0x80;
        } else if (index === totalLength - 8) {
          byte = (bitLengthHi >>> 24) & 0xff;
        } else if (index === totalLength - 7) {
          byte = (bitLengthHi >>> 16) & 0xff;
        } else if (index === totalLength - 6) {
          byte = (bitLengthHi >>> 8) & 0xff;
        } else if (index === totalLength - 5) {
          byte = bitLengthHi & 0xff;
        } else if (index === totalLength - 4) {
          byte = (bitLengthLo >>> 24) & 0xff;
        } else if (index === totalLength - 3) {
          byte = (bitLengthLo >>> 16) & 0xff;
        } else if (index === totalLength - 2) {
          byte = (bitLengthLo >>> 8) & 0xff;
        } else if (index === totalLength - 1) {
          byte = bitLengthLo & 0xff;
        }
        word = ((word << 8) | byte) >>> 0;
      }
      w[i] = word;
    }

    for (let i = 16; i < 64; i += 1) {
      const s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >>> 3);
      const s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >>> 10);
      w[i] = (w[i - 16] + s0 + w[i - 7] + s1) >>> 0;
    }

    let a = h[0];
    let b = h[1];
    let c = h[2];
    let d = h[3];
    let e = h[4];
    let f = h[5];
    let g = h[6];
    let hh = h[7];

    for (let i = 0; i < 64; i += 1) {
      const S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
      const chVal = (e & f) ^ (~e & g);
      const temp1 = (hh + S1 + chVal + K[i] + w[i]) >>> 0;
      const S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
      const majVal = (a & b) ^ (a & c) ^ (b & c);
      const temp2 = (S0 + majVal) >>> 0;

      hh = g;
      g = f;
      f = e;
      e = (d + temp1) >>> 0;
      d = c;
      c = b;
      b = a;
      a = (temp1 + temp2) >>> 0;
    }

    h[0] = (h[0] + a) >>> 0;
    h[1] = (h[1] + b) >>> 0;
    h[2] = (h[2] + c) >>> 0;
    h[3] = (h[3] + d) >>> 0;
    h[4] = (h[4] + e) >>> 0;
    h[5] = (h[5] + f) >>> 0;
    h[6] = (h[6] + g) >>> 0;
    h[7] = (h[7] + hh) >>> 0;
  }

  digestOut.set(h);
  return digestOut;
}

/**
 * Renders one seed component the same way Python's `str()` does, so seeds
 * produce the same noise as the original engine: whole floats keep `.0`.
 */
function formatFloatPart(value: number): string {
  return Number.isInteger(value) ? `${value}.0` : String(value);
}

export type SeedPart = string | number;

function joinMaterial(seed: number, parts: readonly SeedPart[]): string {
  let material = String(Math.trunc(seed));
  for (const part of parts) {
    material += '|';
    material += typeof part === 'number' ? formatFloatPart(part) : part;
  }
  return material;
}

/** Deterministic value in `[-1, 1]` from a seed plus arbitrary parts. */
export function stableUnit(seed: number, ...parts: readonly SeedPart[]): number {
  const words = sha256Words(encoder.encode(joinMaterial(seed, parts)));
  // First 8 digest bytes mapped to [0, 1), then to [-1, 1].
  const unit = words[0] / 0x100000000 + words[1] / 0x10000000000000000;
  return unit * 2 - 1;
}

/** Deterministic index in `[0, n)` from a seed plus a salt string. */
export function stableIndex(seed: number, salt: string, n: number): number {
  if (n <= 0) {
    return 0;
  }
  const words = sha256Words(encoder.encode(`${Math.trunc(seed)}|${salt}`));
  return words[0] % n;
}

/** Integer row/column seed component (no `.0` suffix, matching Python `int`). */
export function intPart(value: number): SeedPart {
  return String(Math.trunc(value));
}
