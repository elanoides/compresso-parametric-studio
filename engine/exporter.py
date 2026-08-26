"""Export helpers: TTF font binary and glyph JSON snapshot."""

from __future__ import annotations

import json
import math
from io import BytesIO

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

from engine.geometry import RenderParams, deform_offset_x, render_glyph_svg, render_text_svg, slant_tan
from engine.glyphs import (
    BASELINE,
    BODY_TOP,
    GLYPH_CHARS,
    GLYPHS,
    ROWS_TOTAL,
    get_glyph,
    glyph_width,
)
from engine.presets import safe_folder_name

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


def normalize_style_name(style: str | None) -> str:
    """User-facing style name written into the font; never silently swap the label."""
    name = (style or "").strip()
    return name or DEFAULT_STYLE


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
    for left_name, right_name, value in _iter_kern_values(p, name_by_char, scale):
        lines.append(f"  pos {left_name} {right_name} {value};")
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


def _iter_kern_values(
    p: RenderParams,
    name_by_char: dict[str, str],
    scale: float,
) -> list[tuple[str, str, int]]:
    """Resolved glyph-name kerning triples in font units."""
    out: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str]] = set()
    for pair, delta_cols in p.kerning_pairs:
        if len(pair) != 2:
            continue
        left, right = pair[0], pair[1]
        if left not in name_by_char or right not in name_by_char:
            continue
        value = _kern_delta_fu(delta_cols, p, scale)
        if value == 0:
            continue
        key = (name_by_char[left], name_by_char[right])
        if key in seen:
            continue
        seen.add(key)
        out.append((key[0], key[1], value))
    return out


def _add_legacy_kern_table(
    font,
    p: RenderParams,
    name_by_char: dict[str, str],
    scale: float,
) -> int:
    """Write a classic ``kern`` table for apps that ignore GPOS."""
    from fontTools.ttLib import newTable
    from fontTools.ttLib.tables._k_e_r_n import KernTable_format_0

    pairs = {
        (left, right): value
        for left, right, value in _iter_kern_values(p, name_by_char, scale)
    }
    if not pairs:
        return 0
    subtable = KernTable_format_0()
    subtable.format = 0
    subtable.coverage = 1  # horizontal
    subtable.kernTable = pairs
    kern = newTable("kern")
    kern.version = 0
    kern.kernTables = [subtable]
    font["kern"] = kern
    return len(pairs)


def _glyph_metrics(
    ch: str, p: RenderParams, scale: float
) -> tuple[int, int, int, int, int]:
    """Return advance, xmin, ymin, xmax, ymax in font units."""
    cols = glyph_width(ch) * max(1, p.col_scale)
    advance = int(round((cols + p.letter_spacing) * p.step_x * scale))
    coords = get_glyph(ch, p.col_scale, p.row_scale)
    if not coords:
        return max(advance, 1), 0, 0, advance, 0

    rx = p.rx * scale
    ry = p.ry * scale
    xs: list[float] = []
    ys: list[float] = []
    for c, r in coords:
        cx, cy = _transformed_font_xy(c, r, p, scale, salt=ch)
        xs.extend((cx - rx, cx + rx))
        ys.extend((cy - ry, cy + ry))

    xmin = int(math.floor(min(xs)))
    xmax = int(math.ceil(max(xs)))
    ymin = int(math.floor(min(ys)))
    ymax = int(math.ceil(max(ys)))
    advance = max(advance, xmax + int(math.ceil(rx)), 1)
    return advance, xmin, ymin, xmax, ymax


def _transformed_font_xy(
    c: int, r: int, p: RenderParams, scale: float, *, salt: str
) -> tuple[float, float]:
    """Module center in font units (y up from baseline) with deformations."""
    cx = c * p.step_x * scale
    cy = (BASELINE - r) * p.step_y * scale
    dx = cy * slant_tan(p)
    jitter_only = RenderParams(
        slant_angle=0.0,
        jitter_x=p.jitter_x,
        row_jitter=p.row_jitter,
        seed=p.seed,
    )
    dx += (
        deform_offset_x(
            col=float(c),
            row=int(r),
            cy=0.0,
            y_baseline=0.0,
            p=jitter_only,
            salt=salt,
        )
        * scale
    )
    return cx + dx, cy


def build_ttf_bytes(
    p: RenderParams,
    *,
    family: str = FAMILY,
    style: str = DEFAULT_STYLE,
) -> bytes:
    """Compile all studio glyphs into a TTF binary with current oval params."""
    style_name = normalize_style_name(style)
    family_name = (family or FAMILY).strip() or FAMILY
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
            cx, cy = _transformed_font_xy(c, r, p, scale, salt=ch)
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

    # Keep the user-authored style string everywhere. For non-RIBBI faces,
    # also uniquify the Windows family so styles do not collapse onto Regular.
    ribbi = {"regular", "bold", "italic", "bolditalic"}
    style_key = "".join(ch.lower() for ch in style_name if ch.isalnum())
    if style_key in ribbi:
        win_family = family_name
    else:
        win_family = f"{family_name} {style_name}"
    win_style = style_name

    ps_safe = "".join(c for c in f"{family_name}-{style_name}" if c.isalnum()) or "Font"
    weight, width, fs_selection = resolve_style_metrics(style_name)
    fb.setupHorizontalHeader(ascent=ascender, descent=descender)
    fb.setupNameTable(
        {
            "familyName": win_family,
            "styleName": win_style,
            "uniqueFontIdentifier": f"{family_name}-{style_name}",
            "fullName": f"{family_name} {style_name}",
            "psName": ps_safe[:63],
            "version": "Version 1.000",
            "typographicFamily": family_name,
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
    _add_legacy_kern_table(fb.font, p, name_by_char, scale)

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
    style_name = normalize_style_name(style)
    payload = {
        "family": family,
        "style": style_name,
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
            "slant_angle": p.slant_angle,
            "jitter_x": p.jitter_x,
            "row_jitter": p.row_jitter,
            "seed": p.seed,
        },
        "kerning": {pair: delta for pair, delta in p.kerning_pairs},
        "glyphs": {
            ch: {"width": glyph_width(ch), "modules": GLYPHS.get(ch, [])}
            for ch in GLYPH_CHARS
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def profile_to_render_params(profile: dict, *, preview_scale: float = 1.0) -> RenderParams:
    """Build ``RenderParams`` from a preset profile dict."""
    kern_raw = profile.get("kerning_pairs") or {}
    kern_pairs = tuple(
        sorted((str(k), float(v)) for k, v in dict(kern_raw).items() if len(str(k)) == 2)
    )
    return RenderParams(
        rx=float(profile.get("rx", 30.0)),
        ry=float(profile.get("ry", 10.0)),
        stroke_width=float(profile.get("stroke_width", 0.0)),
        fill_opacity=float(profile.get("fill_opacity", 1.0)),
        step_x=float(profile.get("step_x", 38.5)),
        step_y=float(profile.get("step_y", 16.0)),
        letter_spacing=float(profile.get("letter_spacing", 1.0)),
        col_scale=int(profile.get("col_scale", 1)),
        row_scale=int(profile.get("row_scale", 1)),
        fill=str(profile.get("fill", "#FFFFFF")),
        stroke=str(profile.get("stroke", "#FFFFFF")),
        background=str(profile.get("background", "#000000")),
        show_guides=False,
        show_grid=False,
        preview_scale=preview_scale,
        kerning_pairs=kern_pairs,
        slant_angle=float(profile.get("slant_angle", 0.0)),
        jitter_x=float(profile.get("jitter_x", 0.0)),
        row_jitter=float(profile.get("row_jitter", 0.0)),
        seed=int(profile.get("seed", 0)),
    )


def build_family_zip(
    styles: dict[str, dict],
    *,
    family: str = FAMILY,
    specimen: str = "НОБЕЛЬФАЙК",
) -> bytes:
    """Pack every style into a ZIP: SVG alphabet, specimen, TTF."""
    import zipfile

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for style_name, profile in styles.items():
            folder = safe_folder_name(style_name)
            params = profile_to_render_params(profile)
            # Alphabet SVGs
            for ch in GLYPH_CHARS:
                if ch == " ":
                    continue
                svg = render_glyph_svg(ch, params)
                fname = f"u{ord(ch):04X}" if not ch.isascii() or not ch.isalnum() else ch
                zf.writestr(f"{folder}/svg/{fname}.svg", svg.encode("utf-8"))
            # Specimen
            spec_svg = render_text_svg(specimen, params)
            zf.writestr(f"{folder}/specimen.svg", spec_svg.encode("utf-8"))
            # TTF
            try:
                ttf = build_ttf_bytes(params, family=family, style=style_name)
                zf.writestr(f"{folder}/{folder}.ttf", ttf)
            except Exception as exc:  # noqa: BLE001
                zf.writestr(f"{folder}/TTF_ERROR.txt", f"{type(exc).__name__}: {exc}\n")
    return buf.getvalue()
