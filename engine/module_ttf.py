"""Draw parametric modules into a TrueType glyph pen (oval / custom SVG / font)."""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from functools import lru_cache
from typing import TYPE_CHECKING

from fontTools.misc.transform import Transform
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.svgLib.path.parser import parse_path

from engine.module_draw import font_char_map, _font_uniform_scale, _symbol_y_offset
from engine.geometry import module_center_font_units
from engine.module_stamp import custom_svg_bbox, font_glyph_path_d
from engine.module_types import MODULE_CUSTOM_SVG, MODULE_FONT, MODULE_OVAL

if TYPE_CHECKING:
    from engine.render_params import RenderParams

_ELLIPSE_SEGMENTS = 28
# Cubic → quadratic tolerance in font units (UPM 1000 → ~1.0).
_CU2QU_MAX_ERR = 1.0


def _tt_draw_pen() -> tuple[TTGlyphPen, Cu2QuPen]:
    """Return ``(glyph_pen, draw_pen)`` — draw to ``draw_pen``, read ``glyph_pen.glyph()``."""
    glyph_pen = TTGlyphPen(None)
    draw_pen = Cu2QuPen(glyph_pen, max_err=_CU2QU_MAX_ERR, reverse_direction=False)
    return glyph_pen, draw_pen


def _ttf_module_angle(angle_deg: float) -> float:
    """Match SVG ``rotate(angle)`` (Y↓) in font outline space (Y↑)."""
    return -float(angle_deg)


def _local_tag(elem: ET.Element) -> str:
    tag = elem.tag
    return tag.split("}")[-1] if "}" in tag else tag


def _replay_recording(recording: RecordingPen | list, pen) -> None:
    ops = recording.value if isinstance(recording, RecordingPen) else recording
    for op, args in ops:
        if op == "moveTo":
            pen.moveTo(args[0])
        elif op == "lineTo":
            pen.lineTo(args[0])
        elif op == "qCurveTo":
            pen.qCurveTo(*args)
        elif op == "curveTo":
            pen.curveTo(*args)
        elif op == "closePath":
            pen.closePath()


def _append_ellipse(rec: RecordingPen, cx: float, cy: float, rx: float, ry: float) -> None:
    pts: list[tuple[float, float]] = []
    for i in range(_ELLIPSE_SEGMENTS):
        a = 2.0 * math.pi * i / _ELLIPSE_SEGMENTS
        pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    rec.moveTo(pts[0])
    for pt in pts[1:]:
        rec.lineTo(pt)
    rec.closePath()


def _append_circle(rec: RecordingPen, cx: float, cy: float, r: float) -> None:
    _append_ellipse(rec, cx, cy, r, r)


def _append_rect(rec: RecordingPen, x: float, y: float, w: float, h: float) -> None:
    rec.moveTo((x, y))
    rec.lineTo((x + w, y))
    rec.lineTo((x + w, y + h))
    rec.lineTo((x, y + h))
    rec.closePath()


def _append_poly(rec: RecordingPen, points: str, *, closed: bool) -> None:
    nums = [float(n) for n in re.findall(r"-?\d+\.?\d*", points or "")]
    if len(nums) < 4:
        return
    pts = [(nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)]
    rec.moveTo(pts[0])
    for pt in pts[1:]:
        rec.lineTo(pt)
    if closed:
        rec.closePath()


def _parse_inner_markup_to_recording(inner: str) -> RecordingPen:
    rec = RecordingPen()
    wrapper = f'<svg xmlns="http://www.w3.org/2000/svg">{inner}</svg>'
    root = ET.fromstring(wrapper)
    for elem in root.iter():
        tag = _local_tag(elem)
        if tag == "path":
            d = elem.get("d") or elem.get("{http://www.w3.org/2000/svg}d") or ""
            if d.strip():
                parse_path(d.strip(), rec)
        elif tag == "circle":
            cx = float(elem.get("cx", "0"))
            cy = float(elem.get("cy", "0"))
            r = float(elem.get("r", "0"))
            if r > 0:
                _append_circle(rec, cx, cy, r)
        elif tag == "ellipse":
            cx = float(elem.get("cx", "0"))
            cy = float(elem.get("cy", "0"))
            rx = float(elem.get("rx", "0"))
            ry = float(elem.get("ry", "0"))
            if rx > 0 and ry > 0:
                _append_ellipse(rec, cx, cy, rx, ry)
        elif tag == "rect":
            x = float(elem.get("x", "0"))
            y = float(elem.get("y", "0"))
            w = float(elem.get("width", "0"))
            h = float(elem.get("height", "0"))
            if w > 0 and h > 0:
                _append_rect(rec, x, y, w, h)
        elif tag == "line":
            x1 = float(elem.get("x1", "0"))
            y1 = float(elem.get("y1", "0"))
            x2 = float(elem.get("x2", "0"))
            y2 = float(elem.get("y2", "0"))
            rec.moveTo((x1, y1))
            rec.lineTo((x2, y2))
        elif tag == "polyline":
            _append_poly(rec, elem.get("points", ""), closed=False)
        elif tag == "polygon":
            _append_poly(rec, elem.get("points", ""), closed=True)
    return rec


@lru_cache(maxsize=32)
def _custom_svg_stamp_ops(inner: str) -> tuple[tuple, tuple[float, float, float, float]]:
    rec = _parse_inner_markup_to_recording(inner)
    bbox = custom_svg_bbox(inner)
    return tuple(rec.value), bbox


def _custom_svg_normalize_transform(
    bbox: tuple[float, float, float, float],
    rx: float,
    ry: float,
) -> Transform:
    x0, y0, x1, y1 = bbox
    w = max(x1 - x0, 1e-6)
    h = max(y1 - y0, 1e-6)
    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0
    uniform = min((2.0 * rx) / w, (2.0 * ry) / h)
    # SVG stamp is Y↓; TTF outlines are Y↑ — flip at normalize (matches live preview placement).
    return (
        Transform()
        .translate(-cx, -cy)
        .scale(uniform, -uniform)
    )


def _module_world_transform(
    cx: float,
    cy: float,
    *,
    angle_deg: float,
    normalize: Transform,
) -> Transform:
    t = Transform(*normalize) if normalize != Transform() else Transform()
    t = Transform().translate(cx, cy).transform(t)
    angle = _ttf_module_angle(angle_deg)
    if abs(angle) >= 1e-9:
        rot = Transform().translate(cx, cy).rotate(angle).translate(-cx, -cy)
        t = rot.transform(t)
    return t


def _draw_oval_module(
    pen,
    cx: float,
    cy: float,
    p: RenderParams,
    scale: float,
) -> None:
    rx = p.rx * scale
    ry = p.ry * scale
    rec = RecordingPen()
    _append_ellipse(rec, 0.0, 0.0, rx, ry)
    t = _module_world_transform(cx, cy, angle_deg=p.module_angle, normalize=Transform())
    _replay_recording(rec, TransformPen(pen, t))


def _draw_custom_svg_module(
    pen,
    cx: float,
    cy: float,
    p: RenderParams,
    scale: float,
) -> None:
    inner = str(p.custom_svg_markup or "").strip()
    if not inner:
        _draw_oval_module(pen, cx, cy, p, scale)
        return
    ops, bbox = _custom_svg_stamp_ops(inner)
    if not ops:
        return
    norm = _custom_svg_normalize_transform(bbox, p.rx * scale, p.ry * scale)
    t = _module_world_transform(cx, cy, angle_deg=p.module_angle, normalize=norm)
    _replay_recording(ops, TransformPen(pen, t))


def _draw_font_module(
    pen,
    cx: float,
    cy: float,
    p: RenderParams,
    scale: float,
    chars: tuple[str, ...],
) -> None:
    if not p.module_font_file or not chars:
        return
    count = len(chars)
    uniform = _font_uniform_scale(p, count=count) * scale
    for i, ch in enumerate(chars):
        path_d = font_glyph_path_d(p.module_font_file, ch)
        if not path_d:
            continue
        rec = RecordingPen()
        parse_path(path_d, rec)
        if not rec.value:
            continue
        dy_svg = _symbol_y_offset(i, count, p.ry)
        dy_font = -dy_svg * scale
        t = Transform().translate(cx, cy + dy_font).scale(uniform, uniform)
        angle = _ttf_module_angle(p.module_angle)
        if abs(angle) >= 1e-9:
            rot = (
                Transform()
                .translate(cx, cy + dy_font)
                .rotate(angle)
                .translate(-cx, -(cy + dy_font))
            )
            t = rot.transform(t)
        _replay_recording(rec, TransformPen(pen, t))


def draw_module_at(
    pen,
    cx: float,
    cy: float,
    p: RenderParams,
    scale: float,
    *,
    font_char: str | tuple[str, ...] | None = None,
) -> None:
    """Emit one module into ``pen`` at font-unit center ``(cx, cy)``."""
    module_type = str(p.module_type or MODULE_OVAL)
    if module_type == MODULE_OVAL:
        _draw_oval_module(pen, cx, cy, p, scale)
        return
    if module_type == MODULE_CUSTOM_SVG:
        _draw_custom_svg_module(pen, cx, cy, p, scale)
        return
    if module_type == MODULE_FONT:
        if isinstance(font_char, str):
            chars = (font_char,)
        elif font_char:
            chars = tuple(font_char)
        else:
            chars = ()
        _draw_font_module(pen, cx, cy, p, scale, chars)
        return


def build_glyph_outline(
    ch: str,
    coords: list[tuple[int, int]],
    p: RenderParams,
    scale: float,
):
    """Build one TrueType glyph outline (quadratic-only) for ``ch``."""
    glyph_pen, draw_pen = _tt_draw_pen()
    draw_glyph_modules(draw_pen, ch, coords, p, scale)
    return glyph_pen.glyph()


def draw_glyph_modules(
    pen,
    ch: str,
    coords: list[tuple[int, int]],
    p: RenderParams,
    scale: float,
) -> None:
    """Draw all modules for one glyph character into ``pen`` (e.g. Cu2QuPen)."""
    char_map: dict[tuple[int, int], tuple[str, ...]] = {}
    if p.module_type == MODULE_FONT:
        char_map = font_char_map(coords, p, salt=ch)
    for c, r in coords:
        cx, cy = module_center_font_units(c, r, p, scale, salt=ch)
        draw_module_at(
            pen,
            cx,
            cy,
            p,
            scale,
            font_char=char_map.get((c, r)),
        )
