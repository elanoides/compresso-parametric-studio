"""Module type constants and asset paths."""

from __future__ import annotations

from pathlib import Path

MODULE_OVAL = "oval"
MODULE_CUSTOM_SVG = "custom_svg"
MODULE_FONT = "font_symbols"

MODULE_TYPE_LABELS: tuple[str, ...] = ("Овал", "Кастомный SVG", "Символы шрифта")
MODULE_TYPE_BY_LABEL: dict[str, str] = {
    "Овал": MODULE_OVAL,
    "Кастомный SVG": MODULE_CUSTOM_SVG,
    "Символы шрифта": MODULE_FONT,
}
MODULE_LABEL_BY_TYPE: dict[str, str] = {v: k for k, v in MODULE_TYPE_BY_LABEL.items()}

FILL_ORDER_COLUMNS = "columns"
FILL_ORDER_ROWS = "rows"
FILL_ORDER_LABELS: tuple[str, ...] = (
    "Сверху вниз (по колонкам)",
    "Слева направо (по строкам)",
)
FILL_ORDER_BY_LABEL: dict[str, str] = {
    FILL_ORDER_LABELS[0]: FILL_ORDER_COLUMNS,
    FILL_ORDER_LABELS[1]: FILL_ORDER_ROWS,
}
FILL_LABEL_BY_ORDER: dict[str, str] = {v: k for k, v in FILL_ORDER_BY_LABEL.items()}

MODULE_FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "module_fonts"

# Default module-font pool when «Строка символов» is empty (no font technical glyphs).
READABLE_CHAR_POOL: str = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
    "0123456789"
    ".,:;!?/+-="
)

# Circle- or dot-like at module scale — never use as font modules.
RANDOM_EXCLUDED_CHARS: frozenset[str] = frozenset("O0QОo.°,;·•●◦∙")

ALLOWED_SVG_TAGS = frozenset(
    {
        "svg",
        "g",
        "path",
        "circle",
        "ellipse",
        "rect",
        "line",
        "polyline",
        "polygon",
    }
)

# Drawable leaf tags extracted from uploaded SVG stamps.
SVG_PRIMITIVE_TAGS = frozenset(
    {"path", "circle", "ellipse", "rect", "line", "polyline", "polygon"}
)

# Removed so module fill/stroke from the studio controls the stamp.
SVG_STRIP_ATTRS = frozenset(
    {"fill", "stroke", "fill-opacity", "stroke-opacity", "opacity", "style", "class", "id"}
)
