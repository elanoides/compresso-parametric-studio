"""Glyph access layer for Compresso Parametric Studio.

Matrices live in ``glyphs_data.py`` (Compresso import) with hand overrides
from ``glyph_overrides.py`` (TYPE TOOL corrections).
"""

from __future__ import annotations

from typing import Iterable

from engine.glyph_overrides import GLYPH_OVERRIDES, WIDTH_OVERRIDES
from engine.glyphs_data import GLYPHS as _RAW_GLYPHS
from engine.glyphs_data import GLYPH_WIDTHS as _RAW_WIDTHS

ROWS_TOTAL = 28
ACCENT_TOP, ACCENT_BOTTOM = 0, 3
BODY_TOP, BODY_BOTTOM = 4, 23
DESC_TOP, DESC_BOTTOM = 24, 27
CAP_HEIGHT = BODY_BOTTOM - BODY_TOP + 1  # 20
BASELINE = BODY_BOTTOM  # 23
SPACE_WIDTH_COLS = 5

GLYPH_CHARS: list[str] = (
    [chr(c) for c in range(ord("A"), ord("Z") + 1)]
    + list("АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ")
    + list("0123456789")
    + list(".,:;!?/+-=")
)

GLYPH_WIDTHS: dict[str, int] = {**_RAW_WIDTHS, **WIDTH_OVERRIDES}

GLYPHS: dict[str, list[tuple[int, int]]] = {
    ch: list(pts) for ch, pts in _RAW_GLYPHS.items()
}
GLYPHS.update({ch: list(pts) for ch, pts in GLYPH_OVERRIDES.items()})


def resolve_glyph_key(ch: str) -> str | None:
    """Map input character to a ``GLYPHS`` key, or ``None`` for whitespace."""
    if ch in " \t":
        return " "
    if ch in "\n\r\v\f":
        return None
    if ch in "ёЁ":
        return "Ё"
    upper = ch.upper()
    if upper in GLYPHS:
        return upper
    if ch in GLYPHS:
        return ch
    return ""


def normalize_text(text: str) -> list[str]:
    """Normalize user text to All-Caps glyph keys; unknowns become empty tokens."""
    out: list[str] = []
    for ch in text:
        key = resolve_glyph_key(ch)
        if key is None:
            continue
        out.append(key)
    return out


def glyph_width(ch: str) -> int:
    """Advance width in grid columns for ``ch``."""
    if ch == " ":
        return SPACE_WIDTH_COLS
    if ch == "":
        return SPACE_WIDTH_COLS
    if ch in GLYPH_WIDTHS:
        return max(1, GLYPH_WIDTHS[ch])
    pts = GLYPHS.get(ch, [])
    if not pts:
        return SPACE_WIDTH_COLS
    return max(c for c, _ in pts) + 1


def scaled_width(ch: str, col_scale: int) -> int:
    """Column width after matrix density scaling."""
    return glyph_width(ch) * max(1, col_scale)


def scale_glyph_density(
    coords: Iterable[tuple[int, int]],
    src_cols: int,
    col_scale: int,
    row_scale: int,
) -> list[tuple[int, int]]:
    """Upsample glyph modules for matrix density sliders."""
    if col_scale <= 1 and row_scale <= 1:
        return list(coords)
    out: set[tuple[int, int]] = set()
    for c, r in coords:
        for dr in range(row_scale):
            for dc in range(col_scale):
                out.add((c * col_scale + dc, r * row_scale + dr))
    if row_scale > 1:
        max_r = ROWS_TOTAL * row_scale - 1
        squashed: set[tuple[int, int]] = set()
        for c, r in out:
            squashed.add((c, int(r * (ROWS_TOTAL - 1) / max_r)))
        out = squashed
    return sorted(out, key=lambda t: (t[1], t[0]))


def get_glyph(
    ch: str,
    col_scale: int = 1,
    row_scale: int = 1,
) -> list[tuple[int, int]]:
    """Return module coordinates for ``ch``; unknown/space yields empty list."""
    key = resolve_glyph_key(ch) if len(ch) == 1 else ch
    if key is None or key == " " or key == "":
        return []
    if key not in GLYPHS:
        return []
    base = GLYPHS[key]
    if not base or (col_scale <= 1 and row_scale <= 1):
        return list(base)
    return scale_glyph_density(base, glyph_width(key), col_scale, row_scale)
