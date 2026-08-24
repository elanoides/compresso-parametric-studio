"""Build engine/glyphs_data.py from authoritative author_bodies matrices."""

from __future__ import annotations

from pathlib import Path

from engine.author_bodies import (
    ACCENTS,
    BODY_H,
    DESCENDERS,
    PUNCT,
    resolve_bodies,
    validate,
)

BODY_TOP = 4
BASELINE = 23
DESC_TOP = 24
OUT = Path(__file__).resolve().parent / "glyphs_data.py"

CHARSET: list[str] = (
    [chr(c) for c in range(ord("A"), ord("Z") + 1)]
    + list("АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ")
    + list("0123456789")
    + list(".,:;!?/+-=")
)


def _bitmap_to_coords(rows: list[str], row_offset: int) -> list[tuple[int, int]]:
    pts: list[tuple[int, int]] = []
    for r, line in enumerate(rows):
        for c, ch in enumerate(line):
            if ch == "#":
                pts.append((c, row_offset + r))
    return pts


def _place_punct(ch: str, bmp: list[str]) -> list[tuple[int, int]]:
    h = len(bmp)
    w = max(len(r) for r in bmp)
    padded = [line.ljust(w, ".") for line in bmp]
    if ch == ".":
        top = BASELINE - h + 1
    elif ch == ",":
        top = BASELINE - 1
    elif ch in "+-=":
        top = BODY_TOP + (BODY_H - h) // 2
    elif ch in ":;":
        top = BODY_TOP + (BODY_H - h) // 2
    else:
        top = BODY_TOP + max(0, (BODY_H - h) // 6)
    return _bitmap_to_coords(padded, top)


def build() -> dict[str, list[tuple[int, int]]]:
    bodies = resolve_bodies()
    validate(bodies)
    glyphs: dict[str, list[tuple[int, int]]] = {" ": []}
    for ch in CHARSET:
        if ch in PUNCT:
            glyphs[ch] = sorted(set(_place_punct(ch, PUNCT[ch])), key=lambda t: (t[1], t[0]))
            continue
        if ch not in bodies:
            glyphs[ch] = []
            continue
        pts = _bitmap_to_coords(bodies[ch], BODY_TOP)
        if ch in ACCENTS:
            pts.extend(_bitmap_to_coords(ACCENTS[ch], 1))
        if ch in DESCENDERS:
            # strip body descender rows if duplicated in body (Ц/Щ/Д last rows)
            body_clean = [
                (c, r)
                for c, r in pts
                if not (ch in DESCENDERS and r > BASELINE)
            ]
            # For Д/Ц/Щ bodies that include leg modules on last body rows,
            # keep body as authored; add explicit descender zone modules.
            pts = body_clean
            pts.extend(_bitmap_to_coords(DESCENDERS[ch], DESC_TOP))
        glyphs[ch] = sorted(set(pts), key=lambda t: (t[1], t[0]))
    return glyphs


def write(glyphs: dict[str, list[tuple[int, int]]]) -> Path:
    lines = [
        '"""CRT glyph matrices — authored TYPE TOOL 5×20 lattice.',
        "",
        "Source: engine/author_bodies.py",
        "Rebuild:  py -m engine.build_glyphs",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "GLYPHS: dict[str, list[tuple[int, int]]] = {",
    ]
    for ch in [" "] + CHARSET:
        pts = glyphs.get(ch, [])
        if ch == " ":
            lines.append('    " ": [],')
            continue
        inner = ", ".join(f"({c}, {r})" for c, r in pts)
        lines.append(f"    {ch!r}: [{inner}],")
    lines.append("}")
    lines.append("")
    lines.append("GLYPH_WIDTHS: dict[str, int] = {")
    for ch in [" "] + CHARSET:
        pts = glyphs.get(ch, [])
        if ch == " ":
            lines.append('    " ": 5,')
            continue
        w = (max((c for c, _ in pts), default=-1) + 1) if pts else 5
        lines.append(f"    {ch!r}: {max(w, 1)},")
    lines.append("}")
    lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    return OUT


if __name__ == "__main__":
    g = build()
    path = write(g)
    print(f"Wrote {path} · {len(g)} keys")
    for sample in ("A", "H", "П", "Б", "Г", "Д", "Ё", "Й", "Ж", "Ш", "Ю", "Ы"):
        pts = g[sample]
        w = max((c for c, _ in pts), default=0) + 1
        print(f"\n{sample} pts={len(pts)}")
        for r in range(4, 24):
            line = "".join("#" if (c, r) in set(pts) else "." for c in range(w))
            print(f"  {r:2d}|{line}|")
        acc = [t for t in pts if t[1] < 4]
        desc = [t for t in pts if t[1] > 23]
        if acc:
            print("  accents", acc)
        if desc:
            print("  desc", desc)
