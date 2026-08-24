"""Build a TrueType font from CRT oval modules + current RenderParams."""

from __future__ import annotations

import math
from io import BytesIO

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

from engine.glyphs import (
    BASELINE,
    BODY_TOP,
    GLYPH_CHARS,
    ROWS_TOTAL,
    get_glyph,
    glyph_width,
)
from engine.render import RenderParams

ELLIPSE_SEGMENTS = 28
FAMILY = "Compresso Parametric"
STYLE = "Regular"

# PostScript glyph names must be ASCII (POST format 2.0).
_PUNCT_NAMES: dict[str, str] = {
    ".": "period",
    ",": "comma",
    ":": "colon",
    ";": "semicolon",
    "!": "exclam",
    "?": "question",
    "/": "slash",
    "+": "plus",
    "-": "hyphen",
    "=": "equal",
}


def ps_glyph_name(ch: str) -> str:
    if ch in _PUNCT_NAMES:
        return _PUNCT_NAMES[ch]
    if ("A" <= ch <= "Z") or ("0" <= ch <= "9"):
        return ch
    return f"uni{ord(ch):04X}"


def _ellipse_points(cx: float, cy: float, rx: float, ry: float, n: int) -> list[tuple[float, float]]:
    """Clockwise ellipse in font space (y up)."""
    pts: list[tuple[float, float]] = []
    for i in range(n):
        a = 2.0 * math.pi * i / n
        pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    return pts


def _draw_ellipse(pen: TTGlyphPen, cx: float, cy: float, rx: float, ry: float) -> None:
    pts = _ellipse_points(cx, cy, rx, ry, ELLIPSE_SEGMENTS)
    pen.moveTo(pts[0])
    for p in pts[1:]:
        pen.lineTo(p)
    pen.closePath()


def _glyph_metrics(ch: str, p: RenderParams, scale: float) -> tuple[int, int, int, int, int]:
    """Return advance, xmin, ymin, xmax, ymax in font units."""
    cols = glyph_width(ch) * max(1, p.col_scale)
    advance = int(round((cols + p.letter_spacing) * p.step_x * scale))
    coords = get_glyph(ch, p.col_scale, p.row_scale)
    if not coords:
        return max(advance, 1), 0, 0, advance, 0
    min_c = min(c for c, _ in coords)
    max_c = max(c for c, _ in coords)
    min_r = min(r for _, r in coords)
    max_r = max(r for _, r in coords)
    rx = p.rx * scale
    ry = p.ry * scale
    xmin = int(math.floor(min_c * p.step_x * scale - rx))
    xmax = int(math.ceil(max_c * p.step_x * scale + rx))
    ymax = int(math.ceil((BASELINE - min_r) * p.step_y * scale + ry))
    ymin = int(math.floor((BASELINE - max_r) * p.step_y * scale - ry))
    return max(advance, 1), xmin, ymin, xmax, ymax


def build_ttf_bytes(p: RenderParams, *, family: str = FAMILY) -> bytes:
    """Compile all studio glyphs into a TTF binary with current oval params."""
    cap_span = max((BASELINE - BODY_TOP) * p.step_y, 1.0)
    upm = 1000
    scale = 750.0 / cap_span

    name_by_char = {ch: ps_glyph_name(ch) for ch in GLYPH_CHARS}
    glyph_order = [".notdef"] + [name_by_char[ch] for ch in GLYPH_CHARS]

    fb = FontBuilder(upm, isTTF=True)
    fb.setupGlyphOrder(glyph_order)

    char_map: dict[int, str] = {}
    for ch in GLYPH_CHARS:
        gname = name_by_char[ch]
        char_map[ord(ch)] = gname
        low = ch.lower()
        if low != ch and ord(low) not in char_map:
            char_map[ord(low)] = gname
    fb.setupCharacterMap(char_map)

    glyphs: dict = {}
    metrics: dict[str, tuple[int, int]] = {}
    all_ymin = 0
    all_ymax = 0

    pen = TTGlyphPen(None)
    pen.moveTo((50, 0))
    pen.lineTo((50, 700))
    pen.lineTo((450, 700))
    pen.lineTo((450, 0))
    pen.closePath()
    glyphs[".notdef"] = pen.glyph()
    metrics[".notdef"] = (500, 50)

    for ch in GLYPH_CHARS:
        gname = name_by_char[ch]
        pen = TTGlyphPen(None)
        coords = get_glyph(ch, p.col_scale, p.row_scale)
        rx = p.rx * scale
        ry = p.ry * scale
        for c, r in coords:
            cx = c * p.step_x * scale
            cy = (BASELINE - r) * p.step_y * scale
            _draw_ellipse(pen, cx, cy, rx, ry)
        glyphs[gname] = pen.glyph()
        advance, xmin, ymin, xmax, ymax = _glyph_metrics(ch, p, scale)
        metrics[gname] = (advance, xmin)
        all_ymin = min(all_ymin, ymin)
        all_ymax = max(all_ymax, ymax)

    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(metrics)

    ascender = int(math.ceil((BASELINE - 0) * p.step_y * scale + p.ry * scale))
    descender = int(
        math.floor((BASELINE - (ROWS_TOTAL - 1)) * p.step_y * scale - p.ry * scale)
    )
    ascender = max(ascender, all_ymax, 1)
    descender = min(descender, all_ymin, -1)

    fb.setupHorizontalHeader(ascent=ascender, descent=descender)
    fb.setupNameTable(
        {
            "familyName": family,
            "styleName": STYLE,
            "uniqueFontIdentifier": f"{family}-{STYLE}-CRT",
            "fullName": f"{family} {STYLE}",
            "psName": family.replace(" ", "") + "-" + STYLE,
            "version": "Version 1.000",
        }
    )
    fb.setupOS2(
        sTypoAscender=ascender,
        sTypoDescender=descender,
        sTypoLineGap=0,
        usWinAscent=ascender,
        usWinDescent=abs(descender),
        achVendID="CRT ",
    )
    fb.setupPost()

    buf = BytesIO()
    fb.save(buf)
    return buf.getvalue()
