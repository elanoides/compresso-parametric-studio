"""Assign module-font characters to grid cells and draw module stamps."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from engine.module_stamp import font_glyph_path_d, normalize_custom_svg_stamp
from engine.module_types import (
    FILL_ORDER_ROWS,
    MODULE_CUSTOM_SVG,
    MODULE_FONT,
    MODULE_OVAL,
)

if TYPE_CHECKING:
    from engine.render_params import RenderParams

Coord = tuple[int, int]


def _stable_index(seed: int, salt: str, n: int) -> int:
    if n <= 0:
        return 0
    material = f"{seed}|{salt}".encode("utf-8")
    digest = hashlib.sha256(material).digest()
    val = int.from_bytes(digest[:4], "big")
    return val % n


def sort_coords(coords: list[Coord], fill_order: str) -> list[Coord]:
    if fill_order == FILL_ORDER_ROWS:
        return sorted(coords, key=lambda pt: (pt[1], pt[0]))
    return sorted(coords, key=lambda pt: (pt[0], pt[1]))


def build_char_pool(p: RenderParams) -> str:
    from engine.module_stamp import font_alphabet
    from engine.module_types import READABLE_CHAR_POOL

    raw = str(p.module_font_chars or "").strip()
    if raw:
        return "".join(ch.upper() if ch != "ё" else "Ё" for ch in raw if not ch.isspace())
    if p.module_font_file:
        pool = font_alphabet(p.module_font_file)
        return pool or READABLE_CHAR_POOL[:1]
    return "A"


def _symbols_per_module(p: RenderParams) -> int:
    return max(1, int(getattr(p, "module_font_symbols_per_module", 1)))


def _font_uniform_scale(p: RenderParams, *, count: int = 1) -> float:
    """Uniform scale from cell height (ry); glyph keeps aspect ratio."""
    from engine.geometry import stroke_margin

    m = stroke_margin(p)
    n = max(1, count)
    return max(p.ry - m, 0.5) / n


def _symbol_y_offset(index: int, count: int, ry: float) -> float:
    """Vertical offset from module center for stacked symbols (SVG Y↓)."""
    if count <= 1:
        return 0.0
    strip = (2.0 * ry) / count
    return (index - (count - 1) / 2.0) * strip


def _drawable_char_pool(pool: str, p: RenderParams) -> str:
    """Font-symbol pool: no circle-like glyphs, only chars with font paths."""
    from engine.module_stamp import font_glyph_path_d
    from engine.module_types import RANDOM_EXCLUDED_CHARS

    filtered: list[str] = []
    for ch in pool:
        if ch in RANDOM_EXCLUDED_CHARS:
            continue
        if p.module_font_file and not font_glyph_path_d(p.module_font_file, ch):
            continue
        filtered.append(ch)
    if filtered:
        return "".join(filtered)
    for ch in pool:
        if p.module_font_file and font_glyph_path_d(p.module_font_file, ch):
            return ch
    return "A"


def font_char_map(
    coords: list[Coord],
    p: RenderParams,
    *,
    salt: str = "",
) -> dict[Coord, tuple[str, ...]]:
    """Map each grid cell to one or more characters from the module-font pool."""
    ordered = sort_coords(coords, p.module_font_fill_order)
    pool = build_char_pool(p)
    if not pool:
        pool = "A"
    pool = _drawable_char_pool(pool, p)
    per_module = _symbols_per_module(p)
    result: dict[Coord, tuple[str, ...]] = {}
    seq = 0
    for c, r in ordered:
        chars: list[str] = []
        for slot in range(per_module):
            if p.module_font_randomize:
                ch = pool[_stable_index(p.seed, f"{salt}:{c}:{r}:{slot}", len(pool))]
            else:
                ch = pool[seq % len(pool)]
                seq += 1
            chars.append(ch)
        result[(c, r)] = tuple(chars)
    return result


def _font_paths_svg(
    cx: float,
    cy: float,
    p: RenderParams,
    chars: tuple[str, ...],
    *,
    fill_opacity: float,
    rot: float,
) -> str:
    """Draw one or more font glyphs centered in a module cell."""
    count = len(chars)
    uniform = _font_uniform_scale(p, count=count)
    rot_attr = (
        f' transform="rotate({rot:.2f}, {cx:.2f}, {cy:.2f})"' if abs(rot) >= 1e-9 else ""
    )
    parts = [f"<g{rot_attr}>"]
    for i, ch in enumerate(chars):
        path_d = font_glyph_path_d(p.module_font_file, ch)
        if not path_d:
            continue
        dy = _symbol_y_offset(i, count, p.ry)
        # scale(u, -u): font paths are Y↑, SVG is Y↓
        parts.append(
            f'<g transform="translate({cx:.2f},{cy + dy:.2f}) scale({uniform:.4f},{-uniform:.4f})">'
            f'<path d="{path_d}" fill="{p.fill}" fill-opacity="{fill_opacity:.3f}" '
            f'stroke="{p.stroke}" stroke-width="{p.stroke_width:.2f}"/>'
            f"</g>"
        )
    parts.append("</g>")
    return "".join(parts)


def module_svg_at(
    cx: float,
    cy: float,
    p: RenderParams,
    *,
    fill_opacity: float | None = None,
    font_char: str | tuple[str, ...] | None = None,
) -> str:
    """Emit SVG for one module at ``(cx, cy)`` according to ``p.module_type``."""
    from engine.geometry import ellipse_svg

    fo = p.fill_opacity if fill_opacity is None else float(fill_opacity)
    rot = float(p.module_angle)

    if p.module_type == MODULE_OVAL:
        return ellipse_svg(cx, cy, p, fill_opacity=fo)

    if p.module_type == MODULE_CUSTOM_SVG:
        inner = str(p.custom_svg_markup or "").strip()
        if not inner:
            return ellipse_svg(cx, cy, p, fill_opacity=fo)
        stamp = normalize_custom_svg_stamp(inner, p.rx, p.ry)
        rot_attr = (
            f' transform="rotate({rot:.2f}, {cx:.2f}, {cy:.2f})"' if abs(rot) >= 1e-9 else ""
        )
        return (
            f'<g{rot_attr}>'
            f'<g transform="translate({cx:.2f},{cy:.2f})" fill="{p.fill}" '
            f'stroke="{p.stroke}" stroke-width="{p.stroke_width:.2f}" '
            f'fill-opacity="{fo:.3f}">{stamp}</g>'
            f"</g>"
        )

    if p.module_type == MODULE_FONT:
        if not font_char or not p.module_font_file:
            return ""
        if isinstance(font_char, str):
            chars = (font_char,)
        else:
            chars = tuple(font_char)
        if not chars:
            return ""
        svg = _font_paths_svg(cx, cy, p, chars, fill_opacity=fo, rot=rot)
        return svg if "<path" in svg else ""

    return ""
