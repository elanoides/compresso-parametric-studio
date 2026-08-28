"""Build normalized module stamps (SVG fragments) for custom SVG and font glyphs."""

from __future__ import annotations

import copy
import re
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

from engine.module_types import (
    ALLOWED_SVG_TAGS,
    MODULE_FONTS_DIR,
    READABLE_CHAR_POOL,
    SVG_PRIMITIVE_TAGS,
    SVG_STRIP_ATTRS,
)

_ET = ET

# Bump when glyph→SVG transform changes (invalidates ``lru_cache``).
_PATH_CACHE_VERSION = 3


def _module_font_path(filename: str) -> Path:
    safe = Path(filename).name
    path = MODULE_FONTS_DIR / safe
    if not path.is_file():
        raise FileNotFoundError(f"Module font not found: {safe}")
    return path


def _recording_to_path_d(recording: RecordingPen) -> str:
    parts: list[str] = []
    for op, args in recording.value:
        if op == "moveTo":
            x, y = args[0]
            parts.append(f"M {x:.4f} {y:.4f}")
        elif op == "lineTo":
            x, y = args[0]
            parts.append(f"L {x:.4f} {y:.4f}")
        elif op == "qCurveTo":
            coords = args
            if len(coords) >= 2:
                x, y = coords[-1]
                parts.append(f"Q {coords[0][0]:.4f} {coords[0][1]:.4f} {x:.4f} {y:.4f}")
        elif op == "curveTo":
            x1, y1 = args[0]
            x2, y2 = args[1]
            x3, y3 = args[2]
            parts.append(f"C {x1:.4f} {y1:.4f} {x2:.4f} {y2:.4f} {x3:.4f} {y3:.4f}")
        elif op == "closePath":
            parts.append("Z")
    return " ".join(parts)


def _path_bbox(path_d: str) -> tuple[float, float, float, float] | None:
    nums = [float(n) for n in re.findall(r"-?\d+\.?\d*", path_d)]
    if len(nums) < 2:
        return None
    xs = nums[0::2]
    ys = nums[1::2]
    return min(xs), min(ys), max(xs), max(ys)


def _bbox_from_recording(recording: RecordingPen) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for op, args in recording.value:
        if op in {"moveTo", "lineTo"}:
            x, y = args[0]
            xs.append(x)
            ys.append(y)
        elif op == "qCurveTo":
            for pt in args:
                xs.append(pt[0])
                ys.append(pt[1])
        elif op == "curveTo":
            for pt in args:
                xs.append(pt[0])
                ys.append(pt[1])
    if not xs:
        return 0.0, 0.0, 1.0, 1.0
    return min(xs), min(ys), max(xs), max(ys)


def _local_tag(elem: ET.Element) -> str:
    tag = elem.tag
    return tag.split("}")[-1] if "}" in tag else tag


def _strip_presentation(elem: ET.Element) -> ET.Element:
    """Return a copy without fill/stroke attrs so studio ink colors apply."""
    out = copy.deepcopy(elem)
    for attr in list(out.attrib):
        local = attr.split("}")[-1]
        if local in SVG_STRIP_ATTRS:
            del out.attrib[attr]
    return out


def _primitive_to_svg(elem: ET.Element) -> str:
    """Serialize one primitive without XML namespaces (safe for SVG innerHTML)."""
    tag = _local_tag(elem)
    attrs: list[str] = []
    for key, value in elem.attrib.items():
        local = key.split("}")[-1] if "}" in key else key
        if local in SVG_STRIP_ATTRS:
            continue
        safe = str(value).replace('"', "&quot;")
        attrs.append(f'{local}="{safe}"')
    attr_str = f' {" ".join(attrs)}' if attrs else ""
    return f"<{tag}{attr_str}/>"


def _collect_svg_primitives(root: ET.Element) -> list[str]:
    """Extract drawable primitives from anywhere in the SVG tree."""
    parts: list[str] = []
    for elem in root.iter():
        if _local_tag(elem) not in SVG_PRIMITIVE_TAGS:
            continue
        parts.append(_primitive_to_svg(_strip_presentation(elem)))
    return parts


@lru_cache(maxsize=64)
def font_glyph_path_d(filename: str, char: str, _cache_version: int = _PATH_CACHE_VERSION) -> str:
    """Extract normalized SVG path ``d`` for one character from a module font."""
    del _cache_version
    ch = char if char else "A"
    path = _module_font_path(filename)
    font = TTFont(str(path), lazy=True)
    try:
        cmap = font.getBestCmap() or {}
        code = ord(ch)
        if ch == "Ё" and code not in cmap and ord("ё") in cmap:
            code = ord("ё")
        if code not in cmap:
            for fallback in ("A", "0"):
                if ord(fallback) in cmap:
                    code = ord(fallback)
                    break
            else:
                return ""
        glyph_name = cmap[code]
        glyph_set = font.getGlyphSet()
        if glyph_name not in glyph_set:
            return ""
        rec = RecordingPen()
        glyph_set[glyph_name].draw(rec)
        x0, y0, x1, y1 = _bbox_from_recording(rec)
        gw = max(x1 - x0, 1e-6)
        gh = max(y1 - y0, 1e-6)
        if gw < 1e-3 and gh < 1e-3:
            return ""
        cx = (x0 + x1) / 2.0
        cy = (y0 + y1) / 2.0
        scale = 1.0 / max(gw, gh)
        # Center glyph; keep font Y↑ in path — flip to SVG Y↓ at render time only.
        transform = (scale, 0.0, 0.0, scale, -scale * cx, -scale * cy)
        pen = SVGPathPen(glyph_set)
        glyph_set[glyph_name].draw(TransformPen(pen, transform))
        return pen.getCommands()
    finally:
        font.close()


@lru_cache(maxsize=32)
def font_alphabet(filename: str) -> str:
    """Readable uppercase pool present in the font (A–Z, А–Я, digits, punctuation)."""
    path = _module_font_path(filename)
    font = TTFont(str(path), lazy=True)
    try:
        cmap = font.getBestCmap() or {}
        chars: list[str] = []
        skip_names = {".notdef", ".null", "NULL", "nonmarkingreturn"}
        for ch in READABLE_CHAR_POOL:
            code = ord(ch)
            if ch == "Ё" and code not in cmap and ord("ё") in cmap:
                code = ord("ё")
            if code not in cmap:
                continue
            glyph_name = cmap[code]
            if glyph_name in skip_names:
                continue
            if ch not in chars:
                chars.append(ch)
        return "".join(chars)
    finally:
        font.close()


def parse_custom_svg_markup(raw: str | bytes) -> str:
    """Sanitize uploaded SVG and return inner markup for use as a module stamp."""
    text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
    text = text.strip()
    if not text:
        return ""
    root = ET.fromstring(text)
    if _local_tag(root) != "svg":
        raise ValueError("Файл должен быть SVG-документом")

    parts = _collect_svg_primitives(root)
    if not parts:
        raise ValueError("SVG не содержит поддерживаемых примитивов (path, circle, …)")
    return "".join(parts)


def custom_svg_bbox(inner: str) -> tuple[float, float, float, float]:
    """Rough bbox for custom SVG inner markup."""
    xs: list[float] = []
    ys: list[float] = []
    for path_d in re.findall(r'd=["\']([^"\']+)["\']', inner):
        bb = _path_bbox(path_d)
        if bb:
            xs.extend([bb[0], bb[2]])
            ys.extend([bb[1], bb[3]])
    for cx, cy, r in re.findall(
        r'cx=["\']([^"\']+)["\']\s+cy=["\']([^"\']+)["\']\s+r=["\']([^"\']+)["\']', inner
    ):
        cx_f, cy_f, r_f = float(cx), float(cy), float(r)
        xs.extend([cx_f - r_f, cx_f + r_f])
        ys.extend([cy_f - r_f, cy_f + r_f])
    for cx, cy, rx, ry in re.findall(
        r'cx=["\']([^"\']+)["\']\s+cy=["\']([^"\']+)["\']\s+rx=["\']([^"\']+)["\']\s+ry=["\']([^"\']+)["\']',
        inner,
    ):
        cx_f, cy_f, rx_f, ry_f = float(cx), float(cy), float(rx), float(ry)
        xs.extend([cx_f - rx_f, cx_f + rx_f])
        ys.extend([cy_f - ry_f, cy_f + ry_f])
    for x, y, w, h in re.findall(
        r'x=["\']([^"\']+)["\']\s+y=["\']([^"\']+)["\']\s+width=["\']([^"\']+)["\']\s+height=["\']([^"\']+)["\']',
        inner,
    ):
        x_f, y_f, w_f, h_f = float(x), float(y), float(w), float(h)
        xs.extend([x_f, x_f + w_f])
        ys.extend([y_f, y_f + h_f])
    if not xs:
        return -1.0, -1.0, 1.0, 1.0
    return min(xs), min(ys), max(xs), max(ys)


def normalize_custom_svg_stamp(inner: str, rx: float, ry: float) -> str:
    """Wrap custom SVG content in a group scaled to module rx/ry."""
    x0, y0, x1, y1 = custom_svg_bbox(inner)
    w = max(x1 - x0, 1e-6)
    h = max(y1 - y0, 1e-6)
    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0
    sx = (2.0 * rx) / w
    sy = (2.0 * ry) / h
    uniform = min(sx, sy)
    return (
        f'<g transform="translate({-cx:.4f},{-cy:.4f}) scale({uniform:.6f})">'
        f"{inner}</g>"
    )


def font_paths_for_pool(filename: str, pool: str) -> dict[str, str]:
    """Precompute path ``d`` for each character in the pool."""
    out: dict[str, str] = {}
    for ch in pool:
        if ch not in out:
            path_d = font_glyph_path_d(filename, ch)
            if path_d:
                out[ch] = path_d
    return out
