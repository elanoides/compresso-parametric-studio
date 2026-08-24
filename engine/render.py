"""SVG renderer for CRT oval modular glyphs."""

from __future__ import annotations

from dataclasses import dataclass

from engine.glyphs import (
    BASELINE,
    BODY_BOTTOM,
    BODY_TOP,
    ROWS_TOTAL,
    get_glyph,
    scaled_width,
)


@dataclass
class RenderParams:
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


def _module_center(
    col: int, row: int, p: RenderParams, origin_x: float, origin_y: float
) -> tuple[float, float]:
    return origin_x + col * p.step_x, origin_y + row * p.step_y


def _ellipse(cx: float, cy: float, p: RenderParams) -> str:
    return (
        f'<ellipse cx="{cx:.2f}" cy="{cy:.2f}" rx="{p.rx:.2f}" ry="{p.ry:.2f}" '
        f'fill="{p.fill}" fill-opacity="{p.fill_opacity:.3f}" '
        f'stroke="{p.stroke}" stroke-width="{p.stroke_width:.2f}"/>'
    )


def render_glyph_svg(
    ch: str,
    p: RenderParams,
    *,
    force_width_cols: int | None = None,
) -> str:
    coords = get_glyph(ch, p.col_scale, p.row_scale)
    cols = force_width_cols or scaled_width(ch if ch != " " else "A", p.col_scale)
    if ch == " ":
        cols = 5 * p.col_scale

    width = p.padding * 2 + max(cols - 1, 0) * p.step_x + p.rx * 2
    height = p.padding * 2 + (ROWS_TOTAL - 1) * p.step_y + p.ry * 2
    ox = p.padding + p.rx
    oy = p.padding + p.ry

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.1f}" height="{height:.1f}" '
        f'viewBox="0 0 {width:.1f} {height:.1f}">',
        f'<rect width="100%" height="100%" fill="{p.background}"/>',
    ]

    if p.show_grid:
        parts.append('<g opacity="0.25">')
        for r in range(ROWS_TOTAL):
            y = oy + r * p.step_y
            parts.append(
                f'<line x1="{ox:.1f}" y1="{y:.1f}" '
                f'x2="{ox + max(cols - 1, 0) * p.step_x:.1f}" y2="{y:.1f}" '
                f'stroke="#4a6a4a" stroke-width="0.5"/>'
            )
        for c in range(cols):
            x = ox + c * p.step_x
            parts.append(
                f'<line x1="{x:.1f}" y1="{oy:.1f}" x2="{x:.1f}" '
                f'y2="{oy + (ROWS_TOTAL - 1) * p.step_y:.1f}" '
                f'stroke="#4a6a4a" stroke-width="0.5"/>'
            )
        parts.append("</g>")

    if p.show_guides:
        y_cap = oy + BODY_TOP * p.step_y
        y_base = oy + BASELINE * p.step_y
        y_body_bot = oy + BODY_BOTTOM * p.step_y
        x0 = ox - p.rx
        x1 = ox + max(cols - 1, 0) * p.step_x + p.rx
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
            f'<rect x="{x0:.1f}" y="{oy - p.ry:.1f}" width="{x1 - x0:.1f}" '
            f'height="{BODY_TOP * p.step_y:.1f}" fill="#5ec8ff" opacity="0.06"/>'
        )
        parts.append(
            f'<rect x="{x0:.1f}" y="{y_body_bot:.1f}" width="{x1 - x0:.1f}" '
            f'height="{(ROWS_TOTAL - 1 - BODY_BOTTOM) * p.step_y + p.ry:.1f}" '
            f'fill="#ff6b4a" opacity="0.06"/>'
        )

    parts.append("<g>")
    for c, r in coords:
        cx, cy = _module_center(c, r, p, ox, oy)
        parts.append(_ellipse(cx, cy, p))
    parts.append("</g></svg>")
    return "\n".join(parts)


def render_text_svg(text: str, p: RenderParams) -> str:
    normalized: list[str] = []
    for ch in text:
        if ch == " ":
            normalized.append(" ")
        elif ch in "ёЁ":
            normalized.append("Ё")
        else:
            normalized.append(ch.upper())

    cursor_col = 0.0
    ellipses: list[tuple[float, int]] = []
    max_col = 0.0

    for ch in normalized:
        coords = get_glyph(ch, p.col_scale, p.row_scale)
        w = scaled_width(ch, p.col_scale) if ch != " " else 5 * p.col_scale
        for c, r in coords:
            abs_c = cursor_col + c
            max_col = max(max_col, abs_c)
            ellipses.append((abs_c, r))
        cursor_col += w + p.letter_spacing

    if cursor_col > 0:
        max_col = max(max_col, cursor_col - p.letter_spacing - 1)

    width = p.padding * 2 + max(max_col, 0) * p.step_x + p.rx * 2
    height = p.padding * 2 + (ROWS_TOTAL - 1) * p.step_y + p.ry * 2
    ox = p.padding + p.rx
    oy = p.padding + p.ry
    scale = max(0.05, float(p.preview_scale))
    disp_w = width * scale
    disp_h = height * scale

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{disp_w:.1f}" height="{disp_h:.1f}" '
        f'viewBox="0 0 {width:.1f} {height:.1f}">',
        f'<rect width="100%" height="100%" fill="{p.background}"/>',
    ]
    if p.show_guides:
        y_base = oy + BASELINE * p.step_y
        parts.append(
            f'<line x1="{ox - p.rx:.1f}" y1="{y_base:.1f}" '
            f'x2="{ox + max_col * p.step_x + p.rx:.1f}" y2="{y_base:.1f}" '
            f'stroke="#ff6b4a" stroke-width="1" opacity="0.7"/>'
        )
    parts.append("<g>")
    for c, r in ellipses:
        cx, cy = _module_center(c, r, p, ox, oy)
        parts.append(_ellipse(cx, cy, p))
    parts.append("</g></svg>")
    return "\n".join(parts)
