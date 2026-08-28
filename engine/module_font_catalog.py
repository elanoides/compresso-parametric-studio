"""Module font catalog: subfamily (гарнитура) → weight → filename."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from engine.module_types import MODULE_FONTS_DIR

# Display order matches the SB product menu (sans → serif).
SUBFAMILY_ORDER: tuple[str, ...] = (
    "SB Sans Cond Mono",
    "SB Sans Display",
    "SB Sans Interface",
    "SB SANS INTERFACE CAPS",
    "SB Sans Screen",
    "SB Sans Text",
    "SB SANS TEXT CAPS",
    "SB Sans Text Cond",
    "SB Sans Text Mono",
    "SB Serif Condensed",
    "SB Serif Display",
    "SB Serif Text",
)

_WEIGHT_ORDER: dict[str, int] = {
    "Thin": 0,
    "Light": 1,
    "Regular": 2,
    "Medium": 3,
    "Semi Bold": 4,
    "Bold": 5,
    "Heavy": 6,
    "Italic": 7,
    "Light Italic": 8,
    "Semi Bold Italic": 9,
    "Bold Italic": 10,
}

# Longer stem prefixes first (``SBSansTextCaps`` before ``SBSansText``).
_STEM_TO_SUBFAMILY: tuple[tuple[str, str], ...] = (
    ("SBSansCondMono", "SB Sans Cond Mono"),
    ("SBSansTextCaps", "SB SANS TEXT CAPS"),
    ("SBSansTextCond", "SB Sans Text Cond"),
    ("SBSansTextMono", "SB Sans Text Mono"),
    ("SBSansDisplay", "SB Sans Display"),
    ("SBSansScreen", "SB Sans Screen"),
    ("SBSansText", "SB Sans Text"),
    ("SBSansUI-Caps", "SB SANS INTERFACE CAPS"),
    ("SBSansUI", "SB Sans Interface"),
    ("SBSerifCondensed", "SB Serif Condensed"),
    ("SBSerifDisplay", "SB Serif Display"),
    ("SBSerifText", "SB Serif Text"),
)


def list_module_fonts() -> list[str]:
    """Return sorted ``.ttf``/``.otf`` filenames in ``assets/module_fonts/``."""
    if not MODULE_FONTS_DIR.is_dir():
        return []
    names: list[str] = []
    for path in MODULE_FONTS_DIR.iterdir():
        if path.suffix.lower() in {".ttf", ".otf"} and path.is_file():
            names.append(path.name)
    return sorted(names, key=str.lower)


def _format_weight(suffix: str) -> str:
    if not suffix:
        return "Regular"
    label = suffix.replace("-", " ")
    label = re.sub(r"([a-z])([A-Z])", r"\1 \2", label)
    return label.strip() or "Regular"


def _weight_sort_key(weight: str) -> tuple[int, str]:
    return (_WEIGHT_ORDER.get(weight, 99), weight.lower())


def subfamily_and_weight_for_file(filename: str) -> tuple[str, str]:
    """Map ``SBSansDisplay-Regular.otf`` → (``SB Sans Display``, ``Regular``)."""
    stem = Path(filename).stem
    for prefix, subfamily in _STEM_TO_SUBFAMILY:
        if stem == prefix:
            return subfamily, "Regular"
        if stem.startswith(prefix + "-"):
            return subfamily, _format_weight(stem[len(prefix) + 1 :])
    if "-" in stem:
        base, weight = stem.split("-", 1)
        return _format_weight(base), _format_weight(weight)
    return stem, "Regular"


def family_and_style_for_file(filename: str) -> tuple[str, str]:
    """Legacy combined label."""
    subfamily, weight = subfamily_and_weight_for_file(filename)
    if weight == "Regular":
        return subfamily, subfamily
    return subfamily, f"{subfamily} {weight}"


@lru_cache(maxsize=1)
def module_font_catalog() -> dict[str, dict[str, str]]:
    """``subfamily_label → weight → filename``."""
    catalog: dict[str, dict[str, str]] = {}
    for filename in list_module_fonts():
        subfamily, weight = subfamily_and_weight_for_file(filename)
        bucket = catalog.setdefault(subfamily, {})
        if weight in bucket:
            weight = f"{weight} ({Path(filename).stem})"
        bucket[weight] = filename
    order_index = {name: i for i, name in enumerate(SUBFAMILY_ORDER)}
    sorted_catalog: dict[str, dict[str, str]] = {}
    for subfamily in sorted(catalog, key=lambda name: (order_index.get(name, 999), name)):
        weights = catalog[subfamily]
        sorted_catalog[subfamily] = dict(
            sorted(weights.items(), key=lambda item: _weight_sort_key(item[0]))
        )
    return sorted_catalog


def module_font_subfamilies() -> list[str]:
    """Flat list of subfamily labels (``SB Sans Display``, …)."""
    return list(module_font_catalog().keys())


def module_font_weights(subfamily: str) -> dict[str, str]:
    return dict(module_font_catalog().get(subfamily, {}))


def resolve_module_font_file(subfamily: str, weight: str) -> str:
    weights = module_font_weights(subfamily)
    if weight not in weights:
        raise KeyError(f"Unknown weight {weight!r} for subfamily {subfamily!r}")
    return weights[weight]
