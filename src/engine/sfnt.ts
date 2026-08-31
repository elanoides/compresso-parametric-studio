/**
 * sfnt surgery: build OpenType kerning tables and splice them into a font
 * binary produced by opentype.js, which writes no GPOS or kern of its own.
 *
 * Two tables are emitted for the same pairs:
 *   GPOS / `kern` feature — used by every modern text engine;
 *   legacy `kern` format 0 — used by older design applications.
 */

const HEAD_CHECKSUM_MAGIC = 0xb1b0afba;

class ByteWriter {
  private bytes: number[] = [];

  get length(): number {
    return this.bytes.length;
  }

  uint8(value: number): void {
    this.bytes.push(value & 0xff);
  }

  uint16(value: number): void {
    this.bytes.push((value >>> 8) & 0xff, value & 0xff);
  }

  int16(value: number): void {
    this.uint16(value < 0 ? value + 0x10000 : value);
  }

  uint32(value: number): void {
    this.bytes.push(
      (value >>> 24) & 0xff,
      (value >>> 16) & 0xff,
      (value >>> 8) & 0xff,
      value & 0xff,
    );
  }

  tag(value: string): void {
    for (let i = 0; i < 4; i += 1) {
      this.uint8(value.charCodeAt(i));
    }
  }

  raw(data: Uint8Array): void {
    for (const byte of data) {
      this.bytes.push(byte);
    }
  }

  toUint8Array(): Uint8Array {
    return new Uint8Array(this.bytes);
  }
}

/** One resolved kerning adjustment in font units. */
export interface KernPair {
  left: number;
  right: number;
  value: number;
}

function floorLog2(value: number): number {
  let result = 0;
  let n = value;
  while (n > 1) {
    n >>= 1;
    result += 1;
  }
  return result;
}

/**
 * GPOS with a single `kern` feature: DFLT script, one PairPos format-1 lookup.
 * Shapers fall back to DFLT when a script tag is absent, so Latin and Cyrillic
 * both pick this up.
 */
export function buildGposKernTable(pairs: readonly KernPair[]): Uint8Array | null {
  if (pairs.length === 0) {
    return null;
  }

  // Group by first glyph; coverage must be sorted by glyph id.
  const grouped = new Map<number, KernPair[]>();
  for (const pair of pairs) {
    const bucket = grouped.get(pair.left);
    if (bucket) {
      bucket.push(pair);
    } else {
      grouped.set(pair.left, [pair]);
    }
  }
  const firstGlyphs = [...grouped.keys()].sort((a, b) => a - b);
  for (const glyph of firstGlyphs) {
    grouped.get(glyph)!.sort((a, b) => a.right - b.right);
  }

  const pairSetCount = firstGlyphs.length;
  const subtableHeaderSize = 10 + 2 * pairSetCount;
  const coverageOffset = subtableHeaderSize;
  const coverageSize = 4 + 2 * pairSetCount;

  const pairSetOffsets: number[] = [];
  let cursor = coverageOffset + coverageSize;
  for (const glyph of firstGlyphs) {
    pairSetOffsets.push(cursor);
    cursor += 2 + 4 * grouped.get(glyph)!.length;
  }
  const subtable = new ByteWriter();
  subtable.uint16(1); // posFormat
  subtable.uint16(coverageOffset);
  subtable.uint16(0x0004); // valueFormat1: X_ADVANCE
  subtable.uint16(0x0000); // valueFormat2: none
  subtable.uint16(pairSetCount);
  for (const offset of pairSetOffsets) {
    subtable.uint16(offset);
  }
  subtable.uint16(1); // coverage format
  subtable.uint16(pairSetCount);
  for (const glyph of firstGlyphs) {
    subtable.uint16(glyph);
  }
  for (const glyph of firstGlyphs) {
    const bucket = grouped.get(glyph)!;
    subtable.uint16(bucket.length);
    for (const pair of bucket) {
      subtable.uint16(pair.right);
      subtable.int16(pair.value);
    }
  }

  const scriptListSize = 20;
  const featureListSize = 14;
  const headerSize = 10;
  const scriptListOffset = headerSize;
  const featureListOffset = scriptListOffset + scriptListSize;
  const lookupListOffset = featureListOffset + featureListSize;

  const out = new ByteWriter();
  out.uint16(1); // majorVersion
  out.uint16(0); // minorVersion
  out.uint16(scriptListOffset);
  out.uint16(featureListOffset);
  out.uint16(lookupListOffset);

  // ScriptList: one DFLT script pointing at a default LangSys.
  out.uint16(1);
  out.tag('DFLT');
  out.uint16(8); // script table offset from ScriptList start
  out.uint16(4); // defaultLangSys offset from script table start
  out.uint16(0); // langSysCount
  out.uint16(0); // lookupOrder
  out.uint16(0xffff); // requiredFeatureIndex
  out.uint16(1); // featureIndexCount
  out.uint16(0); // featureIndices[0]

  // FeatureList: one 'kern' feature using lookup 0.
  out.uint16(1);
  out.tag('kern');
  out.uint16(8); // feature table offset from FeatureList start
  out.uint16(0); // featureParams
  out.uint16(1); // lookupIndexCount
  out.uint16(0); // lookupListIndices[0]

  // LookupList: one pair-adjustment lookup.
  out.uint16(1);
  out.uint16(4); // lookup offset from LookupList start
  out.uint16(2); // lookupType: PairPos
  out.uint16(0); // lookupFlag
  out.uint16(1); // subTableCount
  out.uint16(8); // subtable offset from lookup start
  out.raw(subtable.toUint8Array());

  return out.toUint8Array();
}

/** Legacy horizontal `kern` table, format 0. */
export function buildLegacyKernTable(pairs: readonly KernPair[]): Uint8Array | null {
  if (pairs.length === 0) {
    return null;
  }
  const sorted = [...pairs].sort((a, b) => a.left - b.left || a.right - b.right);
  const nPairs = sorted.length;
  const power = 2 ** floorLog2(nPairs);

  const out = new ByteWriter();
  out.uint16(0); // table version
  out.uint16(1); // number of subtables
  out.uint16(0); // subtable version
  out.uint16(14 + 6 * nPairs); // subtable length
  out.uint16(0x0001); // coverage: horizontal kerning
  out.uint16(nPairs);
  out.uint16(power * 6); // searchRange
  out.uint16(floorLog2(nPairs)); // entrySelector
  out.uint16((nPairs - power) * 6); // rangeShift
  for (const pair of sorted) {
    out.uint16(pair.left);
    out.uint16(pair.right);
    out.int16(pair.value);
  }
  return out.toUint8Array();
}

function checksum(data: Uint8Array): number {
  let sum = 0;
  const padded = data.length + ((4 - (data.length % 4)) % 4);
  for (let i = 0; i < padded; i += 4) {
    const word =
      ((data[i] ?? 0) << 24) |
      ((data[i + 1] ?? 0) << 16) |
      ((data[i + 2] ?? 0) << 8) |
      (data[i + 3] ?? 0);
    sum = (sum + (word >>> 0)) >>> 0;
  }
  return sum >>> 0;
}

interface TableEntry {
  tag: string;
  data: Uint8Array;
}

function readTables(font: Uint8Array): { version: string; tables: TableEntry[] } {
  const view = new DataView(font.buffer, font.byteOffset, font.byteLength);
  const version = String.fromCharCode(font[0], font[1], font[2], font[3]);
  const numTables = view.getUint16(4);
  const tables: TableEntry[] = [];

  for (let i = 0; i < numTables; i += 1) {
    const recordOffset = 12 + i * 16;
    const tag = String.fromCharCode(
      font[recordOffset],
      font[recordOffset + 1],
      font[recordOffset + 2],
      font[recordOffset + 3],
    );
    const offset = view.getUint32(recordOffset + 8);
    const length = view.getUint32(recordOffset + 12);
    tables.push({ tag, data: font.subarray(offset, offset + length) });
  }

  return { version, tables };
}

/**
 * Rebuild a font binary with extra tables added (existing tags are replaced),
 * recomputing the table directory, per-table checksums and
 * `head.checkSumAdjustment`.
 */
export function injectTables(
  fontBinary: ArrayBuffer,
  extras: ReadonlyArray<{ tag: string; data: Uint8Array }>,
): ArrayBuffer {
  const source = new Uint8Array(fontBinary);
  const { version, tables } = readTables(source);

  const replaced = new Set(extras.map((entry) => entry.tag));
  const merged: TableEntry[] = tables
    .filter((entry) => !replaced.has(entry.tag))
    .map((entry) => ({ tag: entry.tag, data: new Uint8Array(entry.data) }));

  for (const extra of extras) {
    merged.push({ tag: extra.tag, data: extra.data });
  }
  merged.sort((a, b) => (a.tag < b.tag ? -1 : a.tag > b.tag ? 1 : 0));

  const head = merged.find((entry) => entry.tag === 'head');
  if (!head) {
    throw new Error('Шрифт без таблицы head — нечего пересобирать');
  }
  // Convention: the head checksum is computed with checkSumAdjustment zeroed.
  new DataView(head.data.buffer, head.data.byteOffset, head.data.byteLength).setUint32(
    8,
    0,
  );

  const numTables = merged.length;
  const power = 2 ** floorLog2(numTables);
  const directorySize = 12 + 16 * numTables;

  const offsets: number[] = [];
  let cursor = directorySize;
  for (const entry of merged) {
    offsets.push(cursor);
    cursor += entry.data.length;
    cursor += (4 - (cursor % 4)) % 4;
  }

  const out = new Uint8Array(cursor);
  const view = new DataView(out.buffer);

  for (let i = 0; i < 4; i += 1) {
    out[i] = version.charCodeAt(i);
  }
  view.setUint16(4, numTables);
  view.setUint16(6, power * 16);
  view.setUint16(8, floorLog2(numTables));
  view.setUint16(10, numTables * 16 - power * 16);

  merged.forEach((entry, i) => {
    const recordOffset = 12 + i * 16;
    for (let c = 0; c < 4; c += 1) {
      out[recordOffset + c] = entry.tag.charCodeAt(c);
    }
    view.setUint32(recordOffset + 4, checksum(entry.data));
    view.setUint32(recordOffset + 8, offsets[i]);
    view.setUint32(recordOffset + 12, entry.data.length);
    out.set(entry.data, offsets[i]);
  });

  const headIndex = merged.indexOf(head);
  const adjustment = (HEAD_CHECKSUM_MAGIC - checksum(out)) >>> 0;
  view.setUint32(offsets[headIndex] + 8, adjustment);

  return out.buffer;
}
