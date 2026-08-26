"""Backward-compatible re-exports — prefer ``engine.geometry``."""

from engine.geometry import (
    RenderParams,
    ellipse_svg,
    kerning_dict,
    module_center,
    params_cache_key,
    params_from_cache_key,
    render_glyph_svg,
    render_text_svg,
    with_params,
)

__all__ = [
    "RenderParams",
    "ellipse_svg",
    "kerning_dict",
    "module_center",
    "params_cache_key",
    "params_from_cache_key",
    "render_glyph_svg",
    "render_text_svg",
    "with_params",
]
