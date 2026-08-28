"""Serialize glyph matrices for the browser live-preview renderer."""

from __future__ import annotations

import json
from functools import lru_cache

from engine.glyphs import (
    BASELINE,
    BODY_BOTTOM,
    BODY_TOP,
    GLYPH_CHARS,
    GLYPH_WIDTHS,
    GLYPHS,
    ROWS_TOTAL,
    SPACE_WIDTH_COLS,
)


@lru_cache(maxsize=1)
def glyph_pack_json() -> str:
    """Compact JSON blob: glyphs, widths, layout constants (cached)."""
    glyphs = {ch: [list(pt) for pt in GLYPHS.get(ch, [])] for ch in GLYPH_CHARS if ch in GLYPHS}
    widths = {ch: int(GLYPH_WIDTHS[ch]) for ch in GLYPH_CHARS if ch in GLYPH_WIDTHS}
    payload = {
        "glyphs": glyphs,
        "widths": widths,
        "constants": {
            "ROWS_TOTAL": ROWS_TOTAL,
            "BASELINE": BASELINE,
            "BODY_TOP": BODY_TOP,
            "BODY_BOTTOM": BODY_BOTTOM,
            "SPACE_WIDTH_COLS": SPACE_WIDTH_COLS,
        },
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
