"""Render parameter dataclass — isolated to avoid stale import caches."""

from __future__ import annotations

from dataclasses import dataclass

from engine.module_types import MODULE_OVAL


@dataclass(frozen=True)
class RenderParams:
    """Parametric module settings for SVG export and preview."""

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
    kerning_pairs: tuple[tuple[str, float], ...] = ()
    slant_angle: float = 0.0
    jitter_x: float = 0.0
    row_jitter: float = 0.0
    seed: int = 0
    module_angle: float = 0.0
    module_type: str = MODULE_OVAL
    custom_svg_markup: str = ""
    module_font_file: str = ""
    module_font_chars: str = ""
    module_font_fill_order: str = "columns"
    module_font_randomize: bool = False
    module_font_symbols_per_module: int = 1
