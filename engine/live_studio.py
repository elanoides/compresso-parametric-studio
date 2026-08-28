"""Streamlit bridge for the client-side live preview studio."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit.components.v1 as components

from engine.glyph_pack import glyph_pack_json
from engine.live_params import enrich_live_params, session_params_for_live
from engine.presets import GEOMETRY_KEYS, INK_KEYS

_COMPONENT_DIR = Path(__file__).resolve().parent.parent / "components" / "cps_live_studio"

_live_studio = components.declare_component(
    "cps_live_studio",
    path=str(_COMPONENT_DIR),
)


def _component_font_payload(params: dict[str, Any]) -> tuple[dict[str, Any], str, str]:
    """Strip font path dict from params; pass as JSON string (Streamlit-safe)."""
    payload = dict(params)
    font_paths_json = ""
    font_alphabet = str(payload.pop("font_alphabet", "") or "")
    font_paths = payload.pop("font_paths", None)
    if isinstance(font_paths, dict) and font_paths:
        font_paths_json = json.dumps(font_paths, ensure_ascii=False)
    return payload, font_paths_json, font_alphabet


def _component_command(command: dict[str, Any] | None) -> dict[str, Any] | None:
    if not command:
        return None
    cmd = dict(command)
    params = dict(cmd.get("params") or {})
    payload, font_paths_json, font_alphabet = _component_font_payload(params)
    cmd["params"] = payload
    if font_paths_json:
        cmd["font_paths_json"] = font_paths_json
    if font_alphabet:
        cmd["font_alphabet"] = font_alphabet
    return cmd


def apply_live_params_to_session(session: Any, params: dict[str, Any]) -> None:
    """Write synced client params back into session_state (geometry + ink)."""
    sync_keys = (*GEOMETRY_KEYS, *INK_KEYS, "font_size")
    for key in sync_keys:
        if key not in params:
            continue
        session[key] = params[key]


def live_studio(
    *,
    mode: str = "text",
    text: str = "",
    glyph: str = "А",
    params: dict[str, Any] | None = None,
    kerning_pairs: dict[str, float] | None = None,
    show_guides: bool = False,
    show_grid: bool = False,
    preview_scale: float = 1.0,
    preview_only: bool = False,
    command: dict[str, Any] | None = None,
    command_id: int = 0,
    height: int = 720,
    key: str = "cps_live_studio",
) -> dict[str, Any] | None:
    """Embed live SVG preview. ``preview_only=True``: canvas only, reads sidebar sliders in JS."""
    payload = dict(params or {})
    if kerning_pairs is not None:
        payload["kerning_pairs"] = kerning_pairs
    payload, font_paths_json, font_alphabet = _component_font_payload(payload)
    return _live_studio(
        glyph_pack=glyph_pack_json(),
        preview_only=preview_only,
        mode=mode,
        text=text,
        glyph=glyph,
        params=payload,
        module_type=str(payload.get("module_type") or "oval"),
        custom_svg_markup=str(payload.get("custom_svg_markup") or ""),
        font_paths_json=font_paths_json,
        font_alphabet=font_alphabet,
        kerning_pairs=kerning_pairs or payload.get("kerning_pairs") or {},
        show_guides=show_guides,
        show_grid=show_grid,
        preview_scale=preview_scale,
        command=_component_command(command),
        command_id=command_id,
        height=height,
        default=None,
        key=key,
    )


__all__ = [
    "apply_live_params_to_session",
    "enrich_live_params",
    "live_studio",
    "session_params_for_live",
]
