"""Import Compresso / source_font.ttf → modular CRT glyph matrices.

Recovers the design-tool lattice (5×20 Cap-Height body, plus accent/descender
zones) by testing whether each module *center* lies inside the glyph outline.
That matches the TYPE TOOL mesh: thin 1-module stems, not anti-aliased blobs.

Grid:
  rows 0..3   accents (above cap height)
  rows 4..23  Cap-Height body (20 rows)
  rows 24..27 descenders (below baseline)

Regenerate:  py -m engine.importer
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.pointInsidePen import PointInsidePen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FONT = ROOT / "source_font.ttf"
OUT_PATH = Path(__file__).resolve().parent / "glyphs_data.py"

ROWS_TOTAL = 28
BODY_TOP = 4
BASELINE = 23
CAP_HEIGHT_ROWS = BASELINE - BODY_TOP + 1  # 20
DESC_TOP = 24

CHARSET: list[str] = (
    [chr(c) for c in range(ord("A"), ord("Z") + 1)]
    + list("АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ")
    + list("0123456789")
    + list(".,:;!?/+-=")
)

_ACCENT_CHARS = frozenset("ЁЙ")
_DESC_CHARS = frozenset("ДЦЩ")

# Fallback 5×20 bodies when Compresso has no glyph (J, /).
_FALLBACK_BODY: dict[str, list[str]] = {
    "J": [
        "....#",
        "....#",
        "....#",
        "....#",
        "....#",
        "....#",
        "....#",
        "....#",
        "....#",
        "....#",
        "....#",
        "....#",
        "....#",
        "....#",
        "....#",
        "....#",
        "#...#",
        "#...#",
        "#...#",
        "#####",
    ],
    "/": [
        "....#",
        "....#",
        "...#.",
        "...#.",
        "...#.",
        "..#..",
        "..#..",
        "..#..",
        ".#...",
        ".#...",
        ".#...",
        "#....",
        "#....",
        "#....",
        "#....",
        "#....",
        "#....",
        "#....",
        "#....",
        "#....",
    ],
}


def _body_bitmap_to_coords(rows: list[str]) -> list[tuple[int, int]]:
    coords: list[tuple[int, int]] = []
    for r, line in enumerate(rows):
        for c, ch in enumerate(line):
            if ch == "#":
                coords.append((c, BODY_TOP + r))
    return coords


def _cols_for_advance(advance: float, standard: float = 629.0) -> int:
    if advance <= 0:
        return 5
    ratio = advance / standard
    if ratio >= 1.35:
        return 7
    if ratio >= 1.12:
        return 6
    return 5


def _point_inside(glyph_set, name: str, x: float, y: float) -> bool:
    """True if (x, y) in font units is inside the glyph."""
    pen = PointInsidePen(glyph_set, (x, y))
    glyph_set[name].draw(pen)
    return bool(pen.getResult())


def sample_glyph_modules(
    tt: TTFont,
    ch: str,
    *,
    cols: int,
    cap: float,
    y_max_accent: float,
    y_min_desc: float,
) -> list[tuple[int, int]]:
    """Sample ON modules by testing cell centers against the outline."""
    cmap = tt.getBestCmap()
    name = cmap.get(ord(ch))
    if not name:
        return []
    gs = tt.getGlyphSet()
    advance = float(tt["hmtx"][name][0])
    # Horizontal span: use ink bbox if available, else advance
    pen = BoundsPen(gs)
    gs[name].draw(pen)
    if pen.bounds:
        x_min, y_min_g, x_max, y_max_g = pen.bounds
    else:
        x_min, x_max = 0.0, advance
        y_min_g, y_max_g = 0.0, cap

    # Design lattice: map cols across ink, not advance (side bearing is not a module).
    x0 = float(x_min)
    x1 = float(x_max) if x_max > x_min else max(advance, 1.0)
    cell_w = (x1 - x0) / cols

    coords: list[tuple[int, int]] = []

    for row in range(ROWS_TOTAL):
        if row < BODY_TOP:
            # Accents: only probe if glyph reaches above cap
            if y_max_g <= cap + 1:
                continue
            span = max(y_max_accent - cap, 1.0)
            # row 0 = top of accent zone, row BODY_TOP-1 = just above cap
            t = (BODY_TOP - row - 0.5) / BODY_TOP
            font_y = cap + t * span
        elif row <= BASELINE:
            # Body: row BODY_TOP → just under cap, row BASELINE → just above 0
            body_i = row - BODY_TOP  # 0..19
            font_y = cap * (1.0 - (body_i + 0.5) / CAP_HEIGHT_ROWS)
        else:
            if y_min_g >= -1:
                # no real descender ink — still allow explicit zone for Д/Ц/Щ later
                continue
            span = max(0.0 - y_min_desc, 1.0)
            t = (row - BASELINE - 0.5) / max(ROWS_TOTAL - 1 - BASELINE, 1)
            font_y = 0.0 - t * span

        for col in range(cols):
            font_x = x0 + (col + 0.5) * cell_w
            if _point_inside(gs, name, font_x, font_y):
                coords.append((col, row))

    return coords


def _enforce_zones(ch: str, coords: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for c, r in coords:
        if r < BODY_TOP and ch not in _ACCENT_CHARS:
            continue
        if r > BASELINE and ch not in _DESC_CHARS:
            continue
        out.append((c, r))

    if ch in _DESC_CHARS:
        by_row: dict[int, list[int]] = {}
        for c, r in out:
            by_row.setdefault(r, []).append(c)
        base_cols = by_row.get(BASELINE) or by_row.get(BASELINE - 1) or []
        if base_cols:
            right = max(base_cols)
            left = min(base_cols)
            if ch == "Д":
                for r in (DESC_TOP, DESC_TOP + 1):
                    out.append((left, r))
                    out.append((right, r))
            else:
                for r in (DESC_TOP, DESC_TOP + 1):
                    out.append((right, r))
    return out


def extract_all(font_path: Path | None = None) -> dict[str, list[tuple[int, int]]]:
    path = Path(font_path) if font_path else DEFAULT_FONT
    if not path.is_file():
        raise FileNotFoundError(f"Font not found: {path}")

    tt = TTFont(str(path))
    cmap = tt.getBestCmap()
    os2 = tt["OS/2"]
    cap = float(getattr(os2, "sCapHeight", None) or 875)
    gs = tt.getGlyphSet()

    y_max = cap
    y_min = 0.0
    for ch in CHARSET:
        name = cmap.get(ord(ch))
        if not name:
            continue
        g = tt["glyf"][name]
        if getattr(g, "numberOfContours", 0) == 0:
            continue
        pen = BoundsPen(gs)
        gs[name].draw(pen)
        if pen.bounds:
            y_min = min(y_min, pen.bounds[1])
            y_max = max(y_max, pen.bounds[3])

    y_max_accent = max(y_max, cap + 50)
    y_min_desc = min(y_min, -50)

    glyphs: dict[str, list[tuple[int, int]]] = {" ": []}
    standard_adv = 629.0

    for ch in CHARSET:
        name = cmap.get(ord(ch))
        if not name or getattr(tt["glyf"][name], "numberOfContours", 0) == 0:
            if ch in _FALLBACK_BODY:
                glyphs[ch] = _body_bitmap_to_coords(_FALLBACK_BODY[ch])
            else:
                glyphs[ch] = []
            continue

        advance = float(tt["hmtx"][name][0])
        cols = _cols_for_advance(advance, standard_adv)
        if ch in ".,:;!":
            cols = min(cols, 3)

        coords = sample_glyph_modules(
            tt,
            ch,
            cols=cols,
            cap=cap,
            y_max_accent=y_max_accent,
            y_min_desc=y_min_desc,
        )
        coords = _enforce_zones(ch, coords)
        glyphs[ch] = sorted(set(coords), key=lambda t: (t[1], t[0]))

    return glyphs


def write_glyphs_data(
    glyphs: dict[str, list[tuple[int, int]]], out: Path | None = None
) -> Path:
    path = out or OUT_PATH
    lines = [
        '"""Auto-generated CRT glyph matrices from source_font.ttf (Compresso).',
        "",
        "Module centers tested against glyph outlines (TYPE TOOL 5×20 lattice).",
        "Regenerate:  py -m engine.importer",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "GLYPHS: dict[str, list[tuple[int, int]]] = {",
    ]
    for ch in [" "] + CHARSET:
        pts = glyphs.get(ch, [])
        if ch == " ":
            lines.append('    " ": [],')
            continue
        inner = ", ".join(f"({c}, {r})" for c, r in pts)
        lines.append(f"    {ch!r}: [{inner}],")
    lines.append("}")
    lines.append("")
    lines.append("GLYPH_WIDTHS: dict[str, int] = {")
    for ch in [" "] + CHARSET:
        pts = glyphs.get(ch, [])
        if ch == " ":
            lines.append('    " ": 5,')
            continue
        w = (max((c for c, _ in pts), default=-1) + 1) if pts else 5
        lines.append(f"    {ch!r}: {max(w, 1)},")
    lines.append("}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def import_source_font(
    font_path: Path | str | None = None, out: Path | str | None = None
) -> Path:
    glyphs = extract_all(Path(font_path) if font_path else None)
    return write_glyphs_data(glyphs, Path(out) if out else None)


def _ascii(ch: str, pts: list[tuple[int, int]]) -> str:
    if not pts:
        return "(empty)"
    w = max(c for c, _ in pts) + 1
    rows = []
    for r in range(ROWS_TOTAL):
        line = "".join("#" if (c, r) in set(pts) else "." for c in range(w))
        rows.append(f"{r:2d}|{line}|")
    return "\n".join(rows)


if __name__ == "__main__":
    target = DEFAULT_FONT
    if not target.is_file():
        raise SystemExit(f"Place source_font.ttf in project root ({ROOT})")
    data = extract_all(target)
    out = write_glyphs_data(data)
    print(f"Wrote {out} · {len(data)} keys")
    for sample in ("A", "H", "O", "Б", "Д", "Ё", "Й", "Н", "П", "Ц", "Щ", "Ж"):
        pts = data.get(sample, [])
        print(f"\n=== {sample!r} pts={len(pts)} ===")
        print(_ascii(sample, pts))
