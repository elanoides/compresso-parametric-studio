"""Built-in and custom style presets for Compresso Parametric Studio."""

from __future__ import annotations

import copy
import json
from typing import Any

# Keys persisted in a style profile (sliders + FX + kerning + style label).
PROFILE_PARAM_KEYS: tuple[str, ...] = (
    "rx",
    "ry",
    "module_angle",
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
    "module_type",
    "custom_svg_markup",
    "module_font_file",
    "module_font_chars",
    "module_font_fill_order",
    "module_font_randomize",
    "module_font_symbols_per_module",
    "font_size",
    "kerning_pairs",
)

# Ink is user-controlled in the UI — never overwrite when loading a style preset.
INK_KEYS: tuple[str, ...] = ("fill", "stroke", "background")
GEOMETRY_KEYS: tuple[str, ...] = tuple(k for k in PROFILE_PARAM_KEYS if k not in INK_KEYS)

BASE_REGULAR: dict[str, Any] = {
    "rx": 30.0,
    "ry": 10.0,
    "module_angle": 0.0,
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
    "module_type": "oval",
    "custom_svg_markup": "",
    "module_font_file": "",
    "module_font_chars": "",
    "module_font_fill_order": "columns",
    "module_font_randomize": False,
    "module_font_symbols_per_module": 1,
    "font_size": 0.38,
    "kerning_pairs": {},
}

BUILTIN_PRESETS: dict[str, dict[str, Any]] = {
    "Regular": copy.deepcopy(BASE_REGULAR),
    "Italic Slant": {
        **BASE_REGULAR,
        "slant_angle": 14.0,
        "letter_spacing": 1.0,
    },
    "Diamond 45°": {
        **BASE_REGULAR,
        "module_angle": 45.0,
        "step_x": 36.0,
        "step_y": 15.0,
        "letter_spacing": 1.0,
    },
    "Glitch CRT": {
        **BASE_REGULAR,
        "jitter_x": 18.0,
        "row_jitter": 12.0,
        "seed": 42,
        "stroke_width": 0.4,
        "fill_opacity": 0.95,
    },
}

BUILTIN_NAMES: tuple[str, ...] = tuple(BUILTIN_PRESETS.keys())
DEFAULT_PRESET_NAMES: tuple[str, ...] = BUILTIN_NAMES
PROTECTED_FROM_DELETE: frozenset[str] = frozenset({"Regular"})

_LEGACY_PRESET_ALIASES: dict[str, str] = {
    "Italic CRT": "Italic Slant",
    "Diagonal 45° (CRT Diamond)": "Diamond 45°",
    "Damaged / Glitch": "Glitch CRT",
    "Condensed Light": "Condensed Light",
    "Expanded Heavy": "Expanded Heavy",
}


def canonical_preset_name(name: str) -> str:
    label = str(name).strip()
    return _LEGACY_PRESET_ALIASES.get(label, label)


def default_presets() -> dict[str, dict[str, Any]]:
    """Fresh copy of the built-in preset library."""
    return {name: copy.deepcopy(cfg) for name, cfg in BUILTIN_PRESETS.items()}


def normalize_profile(cfg: dict[str, Any] | None) -> dict[str, Any]:
    """Merge partial profile data onto ``BASE_REGULAR``."""
    base = copy.deepcopy(BASE_REGULAR)
    if cfg:
        base.update(cfg)
    return base


def is_user_preset(name: str, presets: dict[str, dict[str, Any]]) -> bool:
    """True if ``name`` is not one of the four factory defaults."""
    return str(name).strip() not in DEFAULT_PRESET_NAMES and str(name).strip() in presets


def ensure_presets_store(session: Any) -> dict[str, dict[str, Any]]:
    """Initialize ``session['presets']`` and migrate legacy ``custom_presets``."""
    if "current_preset_name" not in session:
        legacy_active = session.get("active_preset") or session.get("preset_selector")
        if legacy_active:
            session["current_preset_name"] = canonical_preset_name(str(legacy_active))

    raw = session.get("presets")
    if not isinstance(raw, dict) or not raw:
        store = default_presets()
        legacy = session.get("custom_presets")
        if isinstance(legacy, dict):
            for label, cfg in legacy.items():
                name = canonical_preset_name(str(label))
                if not name or not isinstance(cfg, dict):
                    continue
                store[name] = normalize_profile(cfg)
        session["presets"] = store
        return store

    store: dict[str, dict[str, Any]] = {}
    for label, cfg in raw.items():
        name = canonical_preset_name(str(label))
        if not name or not isinstance(cfg, dict):
            continue
        store[name] = normalize_profile(cfg)
    for name, cfg in default_presets().items():
        store.setdefault(name, copy.deepcopy(cfg))
    session["presets"] = store
    return store


def merge_imported_presets(
    existing: dict[str, dict[str, Any]],
    imported: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Merge uploaded presets; imported names overwrite existing ones."""
    merged = {name: copy.deepcopy(cfg) for name, cfg in existing.items()}
    for label, cfg in imported.items():
        name = canonical_preset_name(str(label))
        if not name:
            continue
        merged[name] = normalize_profile(cfg)
    return merged


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


def apply_profile_to_session(
    session: Any,
    profile: dict[str, Any],
    *,
    keys: tuple[str, ...] | None = None,
) -> None:
    """Write profile values into Streamlit session_state (or a mapping).

    By default applies all ``PROFILE_PARAM_KEYS``. Pass ``keys=GEOMETRY_KEYS``
    to leave the user's fill/stroke/background untouched.
    """
    for key in keys if keys is not None else PROFILE_PARAM_KEYS:
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
    merged = default_presets()
    if custom:
        for name, cfg in custom.items():
            label = str(name).strip()
            if not label:
                continue
            merged[label] = normalize_profile(cfg)
    return merged


def presets_library_to_json(
    presets: dict[str, dict[str, Any]],
    *,
    active: str | None = None,
) -> str:
    """Serialize the full preset library for download."""
    payload = {
        "format": "compresso-presets-v2",
        "active": active,
        "presets": presets,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def profiles_to_json(
    custom: dict[str, dict[str, Any]],
    *,
    active: str | None = None,
) -> str:
    """Serialize custom profiles (+ optional active name) for download."""
    return presets_library_to_json(merge_profiles(custom), active=active)


def profiles_from_json(raw: str | bytes) -> tuple[dict[str, dict[str, Any]], str | None]:
    """Parse uploaded presets JSON → (presets_dict, active_name)."""
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
        label = canonical_preset_name(str(name))
        if not label or not isinstance(cfg, dict):
            continue
        cleaned[label] = normalize_profile(cfg)
    active_name = canonical_preset_name(str(active)) if active else None
    return cleaned, (active_name if active_name else None)


def safe_folder_name(name: str) -> str:
    """Filesystem-safe folder / file stem for a style name."""
    slug = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name).strip()
    slug = "_".join(slug.split())
    return slug or "Style"
