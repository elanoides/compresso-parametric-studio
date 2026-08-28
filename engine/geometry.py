"""SVG geometry: oval modules, deformations, layout bounds, rendering."""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Mapping

from engine.glyphs import (
    BASELINE,
    BODY_BOTTOM,
    BODY_TOP,
    ROWS_TOTAL,
    SPACE_WIDTH_COLS,
    get_glyph,
    normalize_text,
    scaled_width,
)
from engine.module_types import MODULE_FONT, MODULE_OVAL
from engine.render_params import RenderParams

Coord = tuple[int, int]
KerningMap = Mapping[str, float]


def _module_draw():
    """Lazy import to avoid circular dependency with ``engine.module_draw``."""
    from engine.module_draw import font_char_map, module_svg_at

    return font_char_map, module_svg_at


def ellipse_effective_half_extents(rx: float, ry: float, angle_deg: float) -> tuple[float, float]:
    """Axis-aligned half-width / half-height of a rotated ellipse."""
    if abs(float(angle_deg)) < 1e-9:
        return float(rx), float(ry)
    rad = math.radians(float(angle_deg))
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    half_w = math.sqrt((rx * cos_a) ** 2 + (ry * sin_a) ** 2)
    half_h = math.sqrt((rx * sin_a) ** 2 + (ry * cos_a) ** 2)
    return half_w, half_h


def module_ink_extents(p: RenderParams) -> tuple[float, float]:
    """Effective half-width / half-height of one module including stroke."""
    m = stroke_margin(p)
    hw, hh = ellipse_effective_half_extents(p.rx, p.ry, p.module_angle)
    return hw + m, hh + m


def kerning_dict(p: RenderParams) -> dict[str, float]:
    """Materialize kerning pairs as a lookup dict."""
    return {pair: delta for pair, delta in p.kerning_pairs}


def stroke_margin(p: RenderParams) -> float:
    """Extra ink margin beyond rx/ry for SVG stroke."""
    return p.stroke_width / 2.0


def slant_tan(p: RenderParams) -> float:
    """``tan(slant_angle)`` in radians."""
    return math.tan(math.radians(float(p.slant_angle)))


def deform_pad_x(p: RenderParams) -> float:
    """Horizontal canvas padding needed for slant + jitter so ovals do not clip."""
    # Worst-case vertical distance from baseline across the full grid.
    max_above = BASELINE * p.step_y + p.ry
    max_below = (ROWS_TOTAL - 1 - BASELINE) * p.step_y + p.ry
    slant_extra = abs(slant_tan(p)) * max(max_above, max_below)
    jitter_extra = abs(float(p.jitter_x)) + abs(float(p.row_jitter))
    return slant_extra + jitter_extra


def module_center(
    col: float, row: float, p: RenderParams, origin_x: float, origin_y: float
) -> tuple[float, float]:
    """Map grid (col, row) to SVG pixel center (before deformation)."""
    return origin_x + col * p.step_x, origin_y + row * p.step_y


def _stable_unit(seed: int, *parts: object) -> float:
    """Deterministic value in ``[-1, 1]`` from seed + parts (hashlib, not salted hash)."""
    import hashlib

    material = "|".join(str(p) for p in (int(seed), *parts)).encode("utf-8")
    digest = hashlib.sha256(material).digest()
    # Map first 8 bytes to [0, 1), then to [-1, 1]
    n = int.from_bytes(digest[:8], "big") / float(2**64)
    return n * 2.0 - 1.0


def deform_offset_x(
    *,
    col: float,
    row: int,
    cy: float,
    y_baseline: float,
    p: RenderParams,
    salt: str = "",
) -> float:
    """Horizontal deformation: slant relative to baseline + glitch jitters."""
    dx = (y_baseline - cy) * slant_tan(p)
    jx = float(p.jitter_x)
    rj = float(p.row_jitter)
    # Quantize col so float layout positions stay stable in the seed mix.
    col_q = round(float(col), 4)
    if jx:
        dx += jx * _stable_unit(p.seed, "jx", salt, col_q, int(row))
    if rj:
        # Scanline shift is per row only (same for every glyph on that row).
        dx += rj * _stable_unit(p.seed, "row", int(row))
    return dx


def module_center_font_units(
    col: int,
    row: int,
    p: RenderParams,
    scale: float,
    *,
    salt: str = "",
) -> tuple[float, float]:
    """Module center in font units (y↑ from baseline) with slant and jitter."""
    cx = col * p.step_x * scale
    cy = (BASELINE - row) * p.step_y * scale
    dx = cy * slant_tan(p)
    jitter_only = RenderParams(
        slant_angle=0.0,
        jitter_x=p.jitter_x,
        row_jitter=p.row_jitter,
        seed=p.seed,
    )
    dx += (
        deform_offset_x(
            col=float(col),
            row=int(row),
            cy=0.0,
            y_baseline=0.0,
            p=jitter_only,
            salt=salt,
        )
        * scale
    )
    return cx + dx, cy


def transformed_center(
    col: float,
    row: int,
    p: RenderParams,
    origin_x: float,
    origin_y: float,
    *,
    min_row: int = 0,
    salt: str = "",
) -> tuple[float, float]:
    """Grid → SVG center with slant / jitter applied."""
    cx, cy = module_center(col, row - min_row, p, origin_x, origin_y)
    y_base = origin_y + (BASELINE - min_row) * p.step_y
    cx += deform_offset_x(col=col, row=row, cy=cy, y_baseline=y_base, p=p, salt=salt)
    return cx, cy


def ellipse_svg(
    cx: float,
    cy: float,
    p: RenderParams,
    *,
    angle: float | None = None,
    fill_opacity: float | None = None,
) -> str:
    """Single oval module as SVG ``<ellipse>`` (rotation around cx, cy)."""
    rot = float(p.module_angle if angle is None else angle)
    fo = p.fill_opacity if fill_opacity is None else float(fill_opacity)
    tag = (
        f'<ellipse cx="{cx:.2f}" cy="{cy:.2f}" rx="{p.rx:.2f}" ry="{p.ry:.2f}"'
    )
    if abs(rot) >= 1e-9:
        tag += f' transform="rotate({rot:.2f}, {cx:.2f}, {cy:.2f})"'
    tag += (
        f' fill="{p.fill}" fill-opacity="{fo:.3f}" '
        f'stroke="{p.stroke}" stroke-width="{p.stroke_width:.2f}"/>'
    )
    return tag


def _layout_origin(p: RenderParams) -> tuple[float, float]:
    """Top-left content origin including stroke + deformation margin."""
    extra = deform_pad_x(p)
    hw, hh = module_ink_extents(p)
    return p.padding + hw + extra, p.padding + hh


def _canvas_size(
    p: RenderParams,
    *,
    max_col: float,
    min_row: int = 0,
    max_row: int = ROWS_TOTAL - 1,
) -> tuple[float, float, float, float]:
    """Return width, height, origin_x, origin_y for a grid span."""
    extra = deform_pad_x(p)
    hw, hh = module_ink_extents(p)
    ox, oy = _layout_origin(p)
    row_span = max(max_row - min_row, 0)
    width = p.padding * 2 + max(max_col, 0) * p.step_x + hw * 2 + extra * 2
    height = p.padding * 2 + row_span * p.step_y + hh * 2
    oy_adjusted = oy - min_row * p.step_y
    return width, height, ox, oy_adjusted


def _row_span(coords: list[Coord]) -> tuple[int, int]:
    if not coords:
        return 0, ROWS_TOTAL - 1
    rows = [r for _, r in coords]
    return min(rows), max(rows)


def _append_grid_guides(
    parts: list[str],
    p: RenderParams,
    ox: float,
    oy: float,
    cols: int,
    min_row: int,
    max_row: int,
) -> None:
    parts.append('<g opacity="0.25">')
    for r in range(min_row, max_row + 1):
        y = oy + (r - min_row) * p.step_y
        parts.append(
            f'<line x1="{ox:.1f}" y1="{y:.1f}" '
            f'x2="{ox + max(cols - 1, 0) * p.step_x:.1f}" y2="{y:.1f}" '
            f'stroke="#4a6a4a" stroke-width="0.5"/>'
        )
    for c in range(cols):
        x = ox + c * p.step_x
        parts.append(
            f'<line x1="{x:.1f}" y1="{oy:.1f}" x2="{x:.1f}" '
            f'y2="{oy + (max_row - min_row) * p.step_y:.1f}" '
            f'stroke="#4a6a4a" stroke-width="0.5"/>'
        )
    parts.append("</g>")


def _append_grid_module_ghosts(
    parts: list[str],
    p: RenderParams,
    ox: float,
    oy: float,
    cols: int,
    min_row: int,
    max_row: int,
) -> None:
    """Inactive module slots — same rotation as active ovals."""
    if p.module_type == MODULE_FONT:
        return
    _, module_svg_at = _module_draw()
    parts.append("<g>")
    ghost_opacity = min(0.18, max(0.04, p.fill_opacity * 0.15))
    for r in range(min_row, max_row + 1):
        for c in range(cols):
            cx, cy = transformed_center(c, r, p, ox, oy, min_row=min_row, salt="grid")
            parts.append(module_svg_at(cx, cy, p, fill_opacity=ghost_opacity))
    parts.append("</g>")


def _append_glyph_guides(
    parts: list[str],
    p: RenderParams,
    ox: float,
    oy: float,
    cols: int,
    min_row: int,
    max_row: int,
) -> None:
    hw, hh = module_ink_extents(p)
    y_cap = oy + (BODY_TOP - min_row) * p.step_y
    y_base = oy + (BASELINE - min_row) * p.step_y
    y_body_bot = oy + (BODY_BOTTOM - min_row) * p.step_y
    x0 = ox - hw
    x1 = ox + max(cols - 1, 0) * p.step_x + hw
    parts.append(
        f'<line x1="{x0:.1f}" y1="{y_cap:.1f}" x2="{x1:.1f}" y2="{y_cap:.1f}" '
        f'stroke="#5ec8ff" stroke-width="1" stroke-dasharray="4 3"/>'
    )
    parts.append(
        f'<line x1="{x0:.1f}" y1="{y_base:.1f}" x2="{x1:.1f}" y2="{y_base:.1f}" '
        f'stroke="#ff6b4a" stroke-width="1.4"/>'
    )
    parts.append(
        f'<text x="{x1 + 4:.1f}" y="{y_cap + 3:.1f}" fill="#5ec8ff" '
        f'font-size="11" font-family="monospace">Cap-Height (row {BODY_TOP})</text>'
    )
    parts.append(
        f'<text x="{x1 + 4:.1f}" y="{y_base + 3:.1f}" fill="#ff6b4a" '
        f'font-size="11" font-family="monospace">Baseline (row {BASELINE})</text>'
    )
    parts.append(
        f'<rect x="{x0:.1f}" y="{oy - hh:.1f}" width="{x1 - x0:.1f}" '
        f'height="{(BODY_TOP - min_row) * p.step_y:.1f}" fill="#5ec8ff" opacity="0.06"/>'
    )
    desc_h = max(0.0, (max_row - BODY_BOTTOM) * p.step_y + hh)
    parts.append(
        f'<rect x="{x0:.1f}" y="{y_body_bot:.1f}" width="{x1 - x0:.1f}" '
        f'height="{desc_h:.1f}" fill="#ff6b4a" opacity="0.06"/>'
    )


def render_glyph_svg(
    ch: str,
    p: RenderParams,
    *,
    force_width_cols: int | None = None,
) -> str:
    """Render one glyph to a standalone SVG string."""
    coords = get_glyph(ch, p.col_scale, p.row_scale)
    # Always reserve full grid height so accents/descenders never clip guides.
    min_row, max_row = 0, ROWS_TOTAL - 1
    cols = force_width_cols or (
        SPACE_WIDTH_COLS * p.col_scale if ch in (" ", "") else scaled_width(ch, p.col_scale)
    )
    width, height, ox, oy = _canvas_size(
        p, max_col=max(cols - 1, 0), min_row=min_row, max_row=max_row
    )

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.1f}" height="{height:.1f}" '
        f'viewBox="0 0 {width:.1f} {height:.1f}">',
        f'<rect width="100%" height="100%" fill="{p.background}"/>',
    ]

    if p.show_grid:
        _append_grid_guides(parts, p, ox, oy, cols, min_row, max_row)
        _append_grid_module_ghosts(parts, p, ox, oy, cols, min_row, max_row)
    if p.show_guides:
        _append_glyph_guides(parts, p, ox, oy, cols, min_row, max_row)

    char_map = {}
    if p.module_type == MODULE_FONT:
        font_char_map, module_svg_at = _module_draw()
        char_map = font_char_map(coords, p, salt=ch)
    else:
        _, module_svg_at = _module_draw()
    parts.append("<g>")
    for c, r in coords:
        cx, cy = transformed_center(c, r, p, ox, oy, min_row=min_row, salt=ch)
        parts.append(
            module_svg_at(cx, cy, p, font_char=char_map.get((c, r)))
        )
    parts.append("</g></svg>")
    return "\n".join(parts)


def _advance_for(ch: str, p: RenderParams) -> float:
    if ch in (" ", ""):
        return SPACE_WIDTH_COLS * max(1, p.col_scale) + p.letter_spacing
    return scaled_width(ch, p.col_scale) + p.letter_spacing


def _layout_text_modules(
    text: str, p: RenderParams
) -> tuple[list[tuple[float, int, str]], float, int, int]:
    """Place text on the grid with kerning; return modules, max column, row span."""
    kern = kerning_dict(p)
    ellipses: list[tuple[float, int, str]] = []
    max_col = 0.0
    min_row = ROWS_TOTAL - 1
    max_row = 0
    cursor_col = 0.0
    prev: str | None = None

    for ch in normalize_text(text):
        if prev is not None and ch not in (" ", "") and prev not in (" ", ""):
            cursor_col += kern.get(prev + ch, 0.0)

        coords = get_glyph(ch, p.col_scale, p.row_scale)
        if ch in (" ", "") or not coords:
            cursor_col += _advance_for(ch, p)
            prev = ch
            continue

        for c, r in coords:
            abs_c = cursor_col + c
            max_col = max(max_col, abs_c)
            min_row = min(min_row, r)
            max_row = max(max_row, r)
            ellipses.append((abs_c, r, ch))
        cursor_col += _advance_for(ch, p)
        prev = ch

    if cursor_col > 0:
        max_col = max(max_col, cursor_col - p.letter_spacing - 1)

    if not ellipses:
        min_row, max_row = 0, ROWS_TOTAL - 1
    else:
        # Keep accents/descenders fully inside the canvas.
        min_row = min(min_row, 0)
        max_row = max(max_row, ROWS_TOTAL - 1)

    return ellipses, max_col, min_row, max_row


def render_text_svg(text: str, p: RenderParams) -> str:
    """Render a baseline-aligned string to SVG."""
    ellipses, max_col, min_row, max_row = _layout_text_modules(text, p)
    width, height, ox, oy = _canvas_size(
        p, max_col=max_col, min_row=min_row, max_row=max_row
    )
    scale = max(0.05, float(p.preview_scale))
    disp_w = width * scale
    disp_h = height * scale
    hw, _hh = module_ink_extents(p)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{disp_w:.1f}" height="{disp_h:.1f}" '
        f'viewBox="0 0 {width:.1f} {height:.1f}">',
        f'<rect width="100%" height="100%" fill="{p.background}"/>',
    ]
    if p.show_guides:
        y_base = oy + (BASELINE - min_row) * p.step_y
        parts.append(
            f'<line x1="{ox - hw:.1f}" y1="{y_base:.1f}" '
            f'x2="{ox + max_col * p.step_x + hw:.1f}" y2="{y_base:.1f}" '
            f'stroke="#ff6b4a" stroke-width="1" opacity="0.7"/>'
        )
    glyph_coords: dict[str, list[Coord]] = {}
    for c, r, ch in ellipses:
        glyph_coords.setdefault(ch, []).append((int(c), r))
    font_char_map, module_svg_at = _module_draw()
    char_maps: dict[str, dict[Coord, str]] = {}
    if p.module_type == MODULE_FONT:
        for ch, coords in glyph_coords.items():
            char_maps[ch] = font_char_map(coords, p, salt=ch)

    parts.append("<g>")
    for c, r, ch in ellipses:
        cx, cy = transformed_center(c, r, p, ox, oy, min_row=min_row, salt=ch)
        fmap = char_maps.get(ch, {})
        parts.append(
            module_svg_at(cx, cy, p, font_char=fmap.get((int(c), r)))
        )
    parts.append("</g></svg>")
    return "\n".join(parts)


def params_cache_key(p: RenderParams) -> tuple:
    """Hashable key for Streamlit ``@st.cache_data``."""
    return (
        p.rx,
        p.ry,
        p.stroke_width,
        p.fill_opacity,
        p.step_x,
        p.step_y,
        p.letter_spacing,
        p.col_scale,
        p.row_scale,
        p.fill,
        p.stroke,
        p.background,
        p.show_guides,
        p.show_grid,
        p.padding,
        p.preview_scale,
        p.kerning_pairs,
        p.slant_angle,
        p.jitter_x,
        p.row_jitter,
        p.seed,
        p.module_angle,
        p.module_type,
        p.custom_svg_markup,
        p.module_font_file,
        p.module_font_chars,
        p.module_font_fill_order,
        p.module_font_randomize,
        p.module_font_symbols_per_module,
    )


def params_from_cache_key(key: tuple) -> RenderParams:
    """Rebuild ``RenderParams`` from ``params_cache_key`` output."""
    return RenderParams(
        rx=key[0],
        ry=key[1],
        stroke_width=key[2],
        fill_opacity=key[3],
        step_x=key[4],
        step_y=key[5],
        letter_spacing=key[6],
        col_scale=key[7],
        row_scale=key[8],
        fill=key[9],
        stroke=key[10],
        background=key[11],
        show_guides=key[12],
        show_grid=key[13],
        padding=key[14],
        preview_scale=key[15],
        kerning_pairs=key[16],
        slant_angle=key[17] if len(key) > 17 else 0.0,
        jitter_x=key[18] if len(key) > 18 else 0.0,
        row_jitter=key[19] if len(key) > 19 else 0.0,
        seed=int(key[20]) if len(key) > 20 else 0,
        module_angle=float(key[21]) if len(key) > 21 else 0.0,
        module_type=str(key[22]) if len(key) > 22 else MODULE_OVAL,
        custom_svg_markup=str(key[23]) if len(key) > 23 else "",
        module_font_file=str(key[24]) if len(key) > 24 else "",
        module_font_chars=str(key[25]) if len(key) > 25 else "",
        module_font_fill_order=str(key[26]) if len(key) > 26 else "columns",
        module_font_randomize=bool(key[27]) if len(key) > 27 else False,
        module_font_symbols_per_module=int(key[28]) if len(key) > 28 else 1,
    )


def with_params(p: RenderParams, **updates: object) -> RenderParams:
    """Return a copy of ``p`` with field overrides."""
    return replace(p, **updates)
