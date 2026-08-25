"""Hand TYPE-TOOL overrides on top of Compresso matrices.

These win over glyphs_data.py for the listed characters.
Skeleton rule from references: stroke = 1 module, gap between stems = 3.
"""

from __future__ import annotations


def _rows(rows: list[str], top: int = 4) -> list[tuple[int, int]]:
    pts: list[tuple[int, int]] = []
    for i, row in enumerate(rows):
        for c, ch in enumerate(row):
            if ch == "#":
                pts.append((c, top + i))
    return pts


def _R(row: str, n: int) -> list[str]:
    return [row] * n


# Cap-Height bodies (rows 4..23) + optional descenders (24..)
# Ф: wide 9-col, bowls only — stem does NOT continue below bottom bar / baseline.
GLYPH_OVERRIDES: dict[str, list[tuple[int, int]]] = {
    "0": _rows(
        [".###.", "#...#"] + _R("#...#", 16) + ["#...#", ".###."]
    ),
    # Ф capital (9 cols): stem tip ABOVE Cap-Height (rows 2–3), bowls from row 4, lower stem to baseline
    "Ф": [(4, 2), (4, 3)]
    + _rows(
        ["#########"]
        + _R("#...#...#", 11)
        + ["#########"]
        + _R("....#....", 7)
    ),
    # Ц: stems 0/4, base, thick right tail
    "Ц": _rows(_R("#...#", 18) + ["#####", "#####"])
    + [(4, 24), (5, 24), (4, 25), (5, 25)],
    # Ш: stems 0/4/8 (gap 3), base
    "Ш": _rows(_R("#...#...#", 19) + ["#########"]),
    # Щ: same as Ш + tail col 9
    "Щ": _rows(_R("#...#...#", 19) + ["#########"])
    + [(9, 24), (9, 25)],
    # Ы: Ь (bowl 5 wide) + 1-col gap + stem
    "Ы": _rows(
        _R("#.....#", 10)
        + ["#####.#"]
        + _R("#...#.#", 8)
        + ["#####.#"]
    ),
    # Д: body stems on inner cols, top bar, flare base, outer feet
    "Д": _rows([".#####."] + _R(".#...#.", 18) + ["#######"])
    + [(0, 24), (6, 24), (0, 25), (6, 25)],
    # Ж: center spine + outer stems + diagonal waist
    "Ж": _rows(
        _R("#..#..#", 6)
        + _R(".#.#.#.", 2)
        + _R("..###..", 2)
        + _R(".#.#.#.", 2)
        + _R("#..#..#", 8)
    ),
    # Ю: stem + 2-col gap + rounded O
    "Ю": _rows(
        ["#...###."]
        + _R("#..#...#", 8)
        + ["####...#"]
        + _R("#..#...#", 9)
        + ["#...###."]
    ),
}

WIDTH_OVERRIDES: dict[str, int] = {
    "0": 5,
    "Ф": 9,
    "Ц": 6,
    "Ш": 9,
    "Щ": 10,
    "Ы": 7,
    "Д": 7,
    "Ж": 7,
    "Ю": 8,
}
