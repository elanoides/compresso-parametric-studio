"""Live-preview parameter extraction (no Streamlit component deps)."""

from __future__ import annotations

from typing import Any

from engine.render_params import RenderParams
from engine.module_draw import build_char_pool, _drawable_char_pool
from engine.module_stamp import font_alphabet, font_paths_for_pool
from engine.module_types import MODULE_FONT
from engine.presets import PROFILE_PARAM_KEYS

LIVE_PARAM_KEYS: tuple[str, ...] = tuple(k for k in PROFILE_PARAM_KEYS if k != "kerning_pairs")


def session_params_for_live(session: dict[str, Any]) -> dict[str, Any]:
    """Extract render params from Streamlit session_state for the JS studio."""
    out: dict[str, Any] = {}
    for key in LIVE_PARAM_KEYS:
        if key in session:
            out[key] = session[key]
    raw_kern = session.get("kerning_pairs") or {}
    out["kerning_pairs"] = {str(k): float(v) for k, v in dict(raw_kern).items()}
    return out


def render_params_from_session(session: dict[str, Any]) -> RenderParams:
    live = session_params_for_live(session)
    return RenderParams(
        rx=float(live.get("rx", 30.0)),
        ry=float(live.get("ry", 10.0)),
        stroke_width=float(live.get("stroke_width", 0.0)),
        fill_opacity=float(live.get("fill_opacity", 1.0)),
        step_x=float(live.get("step_x", 38.5)),
        step_y=float(live.get("step_y", 16.0)),
        letter_spacing=float(live.get("letter_spacing", 1.0)),
        col_scale=int(live.get("col_scale", 1)),
        row_scale=int(live.get("row_scale", 1)),
        fill=str(live.get("fill", "#FFFFFF")),
        stroke=str(live.get("stroke", "#FFFFFF")),
        background=str(live.get("background", "#000000")),
        slant_angle=float(live.get("slant_angle", 0.0)),
        jitter_x=float(live.get("jitter_x", 0.0)),
        row_jitter=float(live.get("row_jitter", 0.0)),
        seed=int(live.get("seed", 0)),
        module_angle=float(live.get("module_angle", 0.0)),
        module_type=str(live.get("module_type", "oval")),
        custom_svg_markup=str(session.get("custom_svg_markup") or ""),
        module_font_file=str(live.get("module_font_file") or ""),
        module_font_chars=str(live.get("module_font_chars") or ""),
        module_font_fill_order=str(live.get("module_font_fill_order") or "columns"),
        module_font_randomize=bool(live.get("module_font_randomize", False)),
        module_font_symbols_per_module=int(live.get("module_font_symbols_per_module", 1)),
    )


def enrich_live_params(session: dict[str, Any]) -> dict[str, Any]:
    """Add module-font path data and SVG markup for the JS preview."""
    out = session_params_for_live(session)
    out["module_type"] = str(session.get("module_type") or out.get("module_type") or "oval")
    out["custom_svg_markup"] = str(session.get("custom_svg_markup") or "")
    module_type = str(out.get("module_type") or "oval")
    if module_type == MODULE_FONT:
        filename = str(out.get("module_font_file") or "")
        if filename:
            p = render_params_from_session(session)
            raw_pool = build_char_pool(p)
            pool = _drawable_char_pool(raw_pool, p) if raw_pool else raw_pool
            out["font_paths"] = font_paths_for_pool(filename, pool or raw_pool)
            out["font_alphabet"] = font_alphabet(filename)
    return out
