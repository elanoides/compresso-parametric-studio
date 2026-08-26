"""Built-in and custom style presets for Compresso Parametric Studio."""

from __future__ import annotations

import copy
import json
from typing import Any

# Keys persisted in a style profile (sliders + FX + kerning + style label).
PROFILE_PARAM_KEYS: tuple[str, ...] = (
    "rx",
    "ry",
    "stroke_width",
    "fill_opacity",
    "step_x",
    "step_y",
    "col_scale",
    "row_scale",
    "letter_spacing",
    "fill",
    "stroke",
    "background",
    "slant_angle",
    "jitter_x",
    "row_jitter",
    "seed",
    "font_size",
    "kerning_pairs",
)

BASE_REGULAR: dict[str, Any] = {
    "rx": 30.0,
    "ry": 10.0,
    "stroke_width": 0.0,
    "fill_opacity": 1.0,
    "step_x": 38.5,
    "step_y": 16.0,
    "col_scale": 1,
    "row_scale": 1,
    "letter_spacing": 1.0,
    "fill": "#FFFFFF",
    "stroke": "#FFFFFF",
    "background": "#000000",
    "slant_angle": 0.0,
    "jitter_x": 0.0,
    "row_jitter": 0.0,
    "seed": 0,
    "font_size": 0.38,
    "kerning_pairs": {},
}

BUILTIN_PRESETS: dict[str, dict[str, Any]] = {
    "Regular": copy.deepcopy(BASE_REGULAR),
    "Condensed Light": {
        **BASE_REGULAR,
        "rx": 18.0,
        "ry": 7.0,
        "step_x": 28.0,
        "step_y": 14.0,
        "letter_spacing": 0.5,
        "fill_opacity": 0.92,
    },
    "Expanded Heavy": {
        **BASE_REGULAR,
        "rx": 42.0,
        "ry": 14.0,
        "step_x": 34.0,
        "step_y": 14.0,
        "letter_spacing": 1.5,
        "fill_opacity": 1.0,
    },
    "Italic CRT": {
        **BASE_REGULAR,
        "slant_angle": 14.0,
        "letter_spacing": 1.0,
    },
    "Damaged / Glitch": {
        **BASE_REGULAR,
        "jitter_x": 18.0,
        "row_jitter": 12.0,
        "seed": 42,
        "stroke_width": 0.4,
        "fill_opacity": 0.95,
    },
}

BUILTIN_NAMES: tuple[str, ...] = tuple(BUILTIN_PRESETS.keys())


def snapshot_from_session(session: dict[str, Any]) -> dict[str, Any]:
    """Capture current UI params into a serializable profile dict."""
    out: dict[str, Any] = {}
    for key in PROFILE_PARAM_KEYS:
        if key == "kerning_pairs":
            raw = session.get("kerning_pairs") or {}
            out[key] = {str(k): float(v) for k, v in dict(raw).items()}
        elif key in session:
            out[key] = session[key]
        else:
            out[key] = copy.deepcopy(BASE_REGULAR.get(key))
    return out


def apply_profile_to_session(session: Any, profile: dict[str, Any]) -> None:
    """Write profile values into Streamlit session_state (or a mapping)."""
    for key in PROFILE_PARAM_KEYS:
        if key not in profile:
            continue
        value = profile[key]
        if key == "kerning_pairs":
            session[key] = {str(k): float(v) for k, v in dict(value or {}).items()}
        else:
            session[key] = value


def merge_profiles(
    custom: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Built-ins first, then user customs (customs may override same name)."""
    merged = {name: copy.deepcopy(cfg) for name, cfg in BUILTIN_PRESETS.items()}
    if custom:
        for name, cfg in custom.items():
            label = str(name).strip()
            if not label:
                continue
            base = copy.deepcopy(BASE_REGULAR)
            base.update(cfg or {})
            merged[label] = base
    return merged


def profiles_to_json(
    custom: dict[str, dict[str, Any]],
    *,
    active: str | None = None,
) -> str:
    """Serialize custom profiles (+ optional active name) for download."""
    payload = {
        "format": "compresso-presets-v1",
        "active": active,
        "presets": custom,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def profiles_from_json(raw: str | bytes) -> tuple[dict[str, dict[str, Any]], str | None]:
    """Parse uploaded presets JSON → (custom_presets, active_name)."""
    text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
    data = json.loads(text)
    if isinstance(data, dict) and "presets" in data:
        presets = data.get("presets") or {}
        active = data.get("active")
    elif isinstance(data, dict):
        presets = data
        active = None
    else:
        raise ValueError("JSON должен быть объектом с пресетами")
    cleaned: dict[str, dict[str, Any]] = {}
    for name, cfg in dict(presets).items():
        label = str(name).strip()
        if not label or not isinstance(cfg, dict):
            continue
        base = copy.deepcopy(BASE_REGULAR)
        base.update(cfg)
        cleaned[label] = base
    return cleaned, (str(active) if active else None)


def safe_folder_name(name: str) -> str:
    """Filesystem-safe folder / file stem for a style name."""
    slug = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name).strip()
    slug = "_".join(slug.split())
    return slug or "Style"
