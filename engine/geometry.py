"""SVG geometry: oval modules, layout bounds, glyph and text rendering."""

from __future__ import annotations

from dataclasses import dataclass, replace
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

Coord = tuple[int, int]
KerningMap = Mapping[str, float]


@dataclass(frozen=True)
class RenderParams:
    """Parametric oval module settings for SVG export and preview."""

    rx: float = 30.0
    ry: float = 10.0
    stroke_width: float = 0.0
    fill_opacity: float = 1.0
    step_x: float = 38.5
    step_y: float = 16.0
    letter_spacing: float = 1.0
    col_scale: int = 1
    row_scale: int = 1
    fill: str = "#FFFFFF"
    stroke: str = "#FFFFFF"
    background: str = "#000000"
    show_guides: bool = False
    show_grid: bool = False
    padding: float = 24.0
    preview_scale: float = 1.0
    # Kerning: pair "АВ" → delta in grid columns (negative = tighter).
    kerning_pairs: tuple[tuple[str, float], ...] = ()


def kerning_dict(p: RenderParams) -> dict[str, float]:
    """Materialize kerning pairs as a lookup dict."""
    return {pair: delta for pair, delta in p.kerning_pairs}


def stroke_margin(p: RenderParams) -> float:
    """Extra ink margin beyond rx/ry for SVG stroke."""
    return p.stroke_width / 2.0


def module_center(
    col: float, row: float, p: RenderParams, origin_x: float, origin_y: float
) -> tuple[float, float]:
    """Map grid (col, row) to SVG pixel center."""
    return origin_x + col * p.step_x, origin_y + row * p.step_y


def ellipse_svg(cx: float, cy: float, p: RenderParams) -> str:
    """Single horizontal oval module as an SVG ``<ellipse>`` tag."""
    return (
        f'<ellipse cx="{cx:.2f}" cy="{cy:.2f}" rx="{p.rx:.2f}" ry="{p.ry:.2f}" '
        f'fill="{p.fill}" fill-opacity="{p.fill_opacity:.3f}" '
        f'stroke="{p.stroke}" stroke-width="{p.stroke_width:.2f}"/>'
    )


def _layout_origin(p: RenderParams) -> tuple[float, float]:
    """Top-left content origin including stroke margin."""
    m = stroke_margin(p)
    return p.padding + p.rx + m, p.padding + p.ry + m


def _canvas_size(
    p: RenderParams,
    *,
    max_col: float,
    min_row: int = 0,
    max_row: int = ROWS_TOTAL - 1,
) -> tuple[float, float, float, float]:
    """Return width, height, origin_x, origin_y for a grid span."""
    m = stroke_margin(p)
    ox, oy = _layout_origin(p)
    row_span = max(max_row - min_row, 0)
    width = p.padding * 2 + max(max_col, 0) * p.step_x + (p.rx + m) * 2
    height = p.padding * 2 + row_span * p.step_y + (p.ry + m) * 2
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


def _append_glyph_guides(
    parts: list[str],
    p: RenderParams,
    ox: float,
    oy: float,
    cols: int,
    min_row: int,
    max_row: int,
) -> None:
    m = stroke_margin(p)
    y_cap = oy + (BODY_TOP - min_row) * p.step_y
    y_base = oy + (BASELINE - min_row) * p.step_y
    y_body_bot = oy + (BODY_BOTTOM - min_row) * p.step_y
    x0 = ox - p.rx - m
    x1 = ox + max(cols - 1, 0) * p.step_x + p.rx + m
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
        f'<rect x="{x0:.1f}" y="{oy - p.ry - m:.1f}" width="{x1 - x0:.1f}" '
        f'height="{(BODY_TOP - min_row) * p.step_y:.1f}" fill="#5ec8ff" opacity="0.06"/>'
    )
    desc_h = max(0.0, (max_row - BODY_BOTTOM) * p.step_y + p.ry + m)
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
    if p.show_guides:
        _append_glyph_guides(parts, p, ox, oy, cols, min_row, max_row)

    parts.append("<g>")
    for c, r in coords:
        cx, cy = module_center(c, r - min_row, p, ox, oy)
        parts.append(ellipse_svg(cx, cy, p))
    parts.append("</g></svg>")
    return "\n".join(parts)


def _advance_for(ch: str, p: RenderParams) -> float:
    if ch in (" ", ""):
        return SPACE_WIDTH_COLS * max(1, p.col_scale) + p.letter_spacing
    return scaled_width(ch, p.col_scale) + p.letter_spacing


def _layout_text_modules(
    text: str, p: RenderParams
) -> tuple[list[tuple[float, int]], float, int, int]:
    """Place text on the grid with kerning; return modules, max column, row span."""
    kern = kerning_dict(p)
    ellipses: list[tuple[float, int]] = []
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
            ellipses.append((abs_c, r))
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
    m = stroke_margin(p)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{disp_w:.1f}" height="{disp_h:.1f}" '
        f'viewBox="0 0 {width:.1f} {height:.1f}">',
        f'<rect width="100%" height="100%" fill="{p.background}"/>',
    ]
    if p.show_guides:
        y_base = oy + (BASELINE - min_row) * p.step_y
        parts.append(
            f'<line x1="{ox - p.rx - m:.1f}" y1="{y_base:.1f}" '
            f'x2="{ox + max_col * p.step_x + p.rx + m:.1f}" y2="{y_base:.1f}" '
            f'stroke="#ff6b4a" stroke-width="1" opacity="0.7"/>'
        )
    parts.append("<g>")
    for c, r in ellipses:
        cx, cy = module_center(c, r - min_row, p, ox, oy)
        parts.append(ellipse_svg(cx, cy, p))
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
    )


def with_params(p: RenderParams, **updates: object) -> RenderParams:
    """Return a copy of ``p`` with field overrides."""
    return replace(p, **updates)
