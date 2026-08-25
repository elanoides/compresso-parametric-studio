"""Export helpers: TTF font binary and glyph JSON snapshot."""

from __future__ import annotations

import json
import math
from io import BytesIO

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

from engine.geometry import RenderParams
from engine.glyphs import (
    BASELINE,
    BODY_TOP,
    GLYPH_CHARS,
    GLYPHS,
    ROWS_TOTAL,
    get_glyph,
    glyph_width,
)

ELLIPSE_SEGMENTS = 28
FAMILY = "Compresso Parametric"
DEFAULT_STYLE = "Regular"

STYLE_NAMES: tuple[str, ...] = (
    "Regular",
    "Light",
    "Medium",
    "Bold",
    "Black",
    "Condensed",
    "Expanded",
    "Italic",
)

# OpenType weight / width so Windows does not collapse styles into one face.
_WEIGHT_BY_TOKEN: dict[str, int] = {
    "thin": 100,
    "extralight": 200,
    "ultralight": 200,
    "light": 300,
    "regular": 400,
    "normal": 400,
    "book": 400,
    "medium": 500,
    "semibold": 600,
    "demibold": 600,
    "bold": 700,
    "extrabold": 800,
    "ultrabold": 800,
    "black": 900,
    "heavy": 900,
}

_WIDTH_BY_TOKEN: dict[str, int] = {
    "ultracondensed": 1,
    "extracondensed": 2,
    "condensed": 3,
    "narrow": 3,
    "semicondensed": 4,
    "normal": 5,
    "regular": 5,
    "semiexpanded": 6,
    "expanded": 7,
    "wide": 7,
    "extraexpanded": 8,
    "ultraexpanded": 9,
}

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
    """PostScript-safe glyph name (ASCII only for POST table)."""
    if ch in _PUNCT_NAMES:
        return _PUNCT_NAMES[ch]
    if ("A" <= ch <= "Z") or ("0" <= ch <= "9"):
        return ch
    return f"uni{ord(ch):04X}"


def style_slug(style: str) -> str:
    """Filesystem-safe style token for download filenames."""
    raw = (style or DEFAULT_STYLE).strip() or DEFAULT_STYLE
    slug = "".join(c if c.isalnum() else "-" for c in raw).strip("-")
    return slug or "Regular"


def _style_tokens(style: str) -> set[str]:
    cleaned = "".join(c.lower() if c.isalnum() else " " for c in style)
    return {tok for tok in cleaned.split() if tok}


def resolve_style_metrics(style: str) -> tuple[int, int, int]:
    """Return ``(usWeightClass, usWidthClass, fsSelection)`` for a style name."""
    tokens = _style_tokens(style)
    weight = 400
    for tok, value in _WEIGHT_BY_TOKEN.items():
        if tok in tokens:
            weight = value
            break
    width = 5
    for tok, value in _WIDTH_BY_TOKEN.items():
        if tok in tokens:
            width = value
            break

    # fsSelection bits: 0 italic, 5 bold, 6 regular
    fs_selection = 0
    if "italic" in tokens or "oblique" in tokens:
        fs_selection |= 0x01
    if weight >= 700:
        fs_selection |= 0x20
    elif "italic" not in tokens and "oblique" not in tokens:
        fs_selection |= 0x40
    return weight, width, fs_selection


def _ellipse_points(
    cx: float, cy: float, rx: float, ry: float, n: int
) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    for i in range(n):
        a = 2.0 * math.pi * i / n
        pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    return pts


def _draw_ellipse(pen: TTGlyphPen, cx: float, cy: float, rx: float, ry: float) -> None:
    pts = _ellipse_points(cx, cy, rx, ry, ELLIPSE_SEGMENTS)
    pen.moveTo(pts[0])
    for point in pts[1:]:
        pen.lineTo(point)
    pen.closePath()


def _kern_delta_fu(delta_cols: float, p: RenderParams, scale: float) -> int:
    """Convert studio kerning (column units) to font units."""
    return int(round(float(delta_cols) * p.step_x * scale))


def _build_kern_fea(
    p: RenderParams,
    name_by_char: dict[str, str],
    scale: float,
) -> str | None:
    """Build OpenType ``kern`` feature source, or ``None`` if no pairs."""
    lines: list[str] = []
    for pair, delta_cols in p.kerning_pairs:
        if len(pair) != 2:
            continue
        left, right = pair[0], pair[1]
        if left not in name_by_char or right not in name_by_char:
            continue
        value = _kern_delta_fu(delta_cols, p, scale)
        if value == 0:
            continue
        lines.append(f"  pos {name_by_char[left]} {name_by_char[right]} {value};")
    if not lines:
        return None
    body = "\n".join(lines)
    return (
        "languagesystem DFLT dflt;\n"
        "languagesystem latn dflt;\n"
        "languagesystem cyrl dflt;\n"
        "feature kern {\n"
        f"{body}\n"
        "} kern;\n"
    )


def _glyph_metrics(
    ch: str, p: RenderParams, scale: float
) -> tuple[int, int, int, int, int]:
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


def build_ttf_bytes(
    p: RenderParams,
    *,
    family: str = FAMILY,
    style: str = DEFAULT_STYLE,
) -> bytes:
    """Compile all studio glyphs into a TTF binary with current oval params."""
    style_name = (style or DEFAULT_STYLE).strip() or DEFAULT_STYLE
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

    ps_safe = "".join(c for c in style_name if c.isalnum()) or "Regular"
    weight, width, fs_selection = resolve_style_metrics(style_name)
    fb.setupHorizontalHeader(ascent=ascender, descent=descender)
    fb.setupNameTable(
        {
            "familyName": family,
            "styleName": style_name,
            "uniqueFontIdentifier": f"{family}-{style_name}",
            "fullName": f"{family} {style_name}",
            "psName": family.replace(" ", "") + "-" + ps_safe,
            "version": "Version 1.000",
            "typographicFamily": family,
            "typographicSubfamily": style_name,
        }
    )
    fb.setupOS2(
        sTypoAscender=ascender,
        sTypoDescender=descender,
        sTypoLineGap=0,
        usWinAscent=ascender,
        usWinDescent=abs(descender),
        usWeightClass=weight,
        usWidthClass=width,
        fsSelection=fs_selection,
        achVendID="CMPS",
    )
    fb.setupPost()

    mac_style = 0
    if fs_selection & 0x20:
        mac_style |= 0x01  # bold
    if fs_selection & 0x01:
        mac_style |= 0x02  # italic
    fb.font["head"].macStyle = mac_style

    kern_fea = _build_kern_fea(p, name_by_char, scale)
    if kern_fea:
        fb.addOpenTypeFeatures(kern_fea)

    buf = BytesIO()
    fb.save(buf)
    return buf.getvalue()


def build_glyphs_json(
    p: RenderParams,
    *,
    family: str = FAMILY,
    style: str = DEFAULT_STYLE,
) -> str:
    """Export current glyph matrices, kerning and render params as JSON."""
    payload = {
        "family": family,
        "style": style or DEFAULT_STYLE,
        "params": {
            "rx": p.rx,
            "ry": p.ry,
            "stroke_width": p.stroke_width,
            "fill_opacity": p.fill_opacity,
            "step_x": p.step_x,
            "step_y": p.step_y,
            "letter_spacing": p.letter_spacing,
            "col_scale": p.col_scale,
            "row_scale": p.row_scale,
        },
        "kerning": {pair: delta for pair, delta in p.kerning_pairs},
        "glyphs": {
            ch: {"width": glyph_width(ch), "modules": GLYPHS.get(ch, [])}
            for ch in GLYPH_CHARS
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
