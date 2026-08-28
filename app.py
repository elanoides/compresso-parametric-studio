"""Compresso Parametric Studio — Streamlit UI."""

from __future__ import annotations

import hashlib
import json

import base64

import streamlit as st
import streamlit.components.v1 as components

from engine.browser_store import load_presets_blob, save_presets_blob
from engine.exporter import (
    DEFAULT_STYLE,
    FAMILY,
    build_family_zip,
    build_ttf_bytes,
    normalize_style_name,
    style_slug,
)
from engine.render_params import RenderParams
from engine.geometry import params_cache_key, params_from_cache_key, with_params
from engine.glyphs import (
    BASELINE,
    ROWS_TOTAL,
    get_glyph,
    glyph_width,
)
from engine.live_params import enrich_live_params
from engine.live_studio import live_studio, session_params_for_live
from engine.module_font_catalog import (
    list_module_fonts,
    module_font_catalog,
    module_font_subfamilies,
    module_font_weights,
    resolve_module_font_file,
    subfamily_and_weight_for_file,
)
from engine.module_stamp import parse_custom_svg_markup
from engine.module_types import (
    FILL_ORDER_BY_LABEL,
    FILL_ORDER_LABELS,
    MODULE_CUSTOM_SVG,
    MODULE_FONT,
    MODULE_OVAL,
    MODULE_TYPE_BY_LABEL,
    MODULE_TYPE_LABELS,
    MODULE_LABEL_BY_TYPE,
)
from engine.presets import (
    BUILTIN_NAMES,
    BUILTIN_PRESETS,
    GEOMETRY_KEYS,
    apply_profile_to_session,
    merge_profiles,
    profiles_from_json,
    snapshot_from_session,
)
from engine.render import render_glyph_svg, render_text_svg

# ----- Regular (Default) -----
REGULAR_VERSION = 12
REGULAR: dict[str, float | int | str | bool] = {
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
    "module_type": MODULE_OVAL,
    "custom_svg_markup": "",
    "module_font_file": "",
    "module_font_subfamily": "",
    "module_font_weight": "",
    "module_font_chars": "",
    "module_font_fill_order": "columns",
    "module_font_randomize": False,
}

DEFAULT_PHRASE = "НОБЕЛЬФАЙК"
DEFAULT_FONT_SIZE = 0.38  # preview_scale for word composer

THEME: dict[str, str] = {
    "app_bg": "#000000",
    "sidebar_bg": "#0C0C0C",
    "secondary_bg": "#161616",
    "text": "#FFFFFF",
    "muted": "#9A9A9A",
    "border": "#2A2A2A",
    "fill": "#FFFFFF",
    "stroke": "#FFFFFF",
    "background": "#000000",
    "mobile_btn_bg": "#141414",
    "mobile_btn_fg": "#FFFFFF",
    "mobile_btn_border": "#333333",
}

st.set_page_config(
    page_title="Compresso Parametric Studio",
    page_icon="▣",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _ensure_defaults() -> None:
    """Seed session_state once; migrate when REGULAR_VERSION changes."""
    if st.session_state.get("_regular_version") != REGULAR_VERSION:
        for key, value in REGULAR.items():
            st.session_state[key] = value
        st.session_state["_regular_version"] = REGULAR_VERSION
        st.session_state.setdefault("font_style", DEFAULT_STYLE)
        st.session_state.setdefault("font_size", DEFAULT_FONT_SIZE)
        st.session_state.setdefault("kerning_pairs", {})
        st.session_state.setdefault("kern_pair_in", "АВ")
        st.session_state.setdefault("kern_delta_in", -0.5)
        st.session_state["word_text"] = DEFAULT_PHRASE
        st.session_state.setdefault("custom_presets", {})
        st.session_state.setdefault("active_preset", "Regular")
        st.session_state.setdefault("preset_name_in", "")
        st.session_state.setdefault("preset_selector", "Regular")
        st.session_state.setdefault("word_show_guides", False)
        st.session_state.setdefault("word_show_grid", False)
        st.session_state.setdefault("inspect_show_guides", True)
        st.session_state.setdefault("inspect_show_grid", False)
        st.session_state.setdefault("inspect_letter", "А")
        st.session_state.setdefault("_live_cmd_id", 0)
        st.session_state.setdefault("_export_cache_rev", 0)
        st.session_state.setdefault("_custom_svg_upload_id", "")
        _ensure_module_font_default()
        # Always white-on-black after migration
        st.session_state["fill"] = "#FFFFFF"
        st.session_state["stroke"] = "#FFFFFF"
        st.session_state["background"] = "#000000"
        return
    for key, value in REGULAR.items():
        st.session_state.setdefault(key, value)
    st.session_state.setdefault("font_style", DEFAULT_STYLE)
    st.session_state.setdefault("font_size", DEFAULT_FONT_SIZE)
    st.session_state.setdefault("kerning_pairs", {})
    st.session_state.setdefault("kern_pair_in", "АВ")
    st.session_state.setdefault("kern_delta_in", -0.5)
    st.session_state.setdefault("word_text", DEFAULT_PHRASE)
    st.session_state.setdefault("custom_presets", {})
    st.session_state.setdefault("active_preset", "Regular")
    st.session_state.setdefault("preset_name_in", "")
    st.session_state.setdefault("preset_selector", "Regular")
    st.session_state.setdefault("word_show_guides", False)
    st.session_state.setdefault("word_show_grid", False)
    st.session_state.setdefault("inspect_show_guides", True)
    st.session_state.setdefault("inspect_show_grid", False)
    st.session_state.setdefault("inspect_letter", "А")
    st.session_state.setdefault("_live_cmd_id", 0)
    st.session_state.setdefault("_export_cache_rev", 0)
    st.session_state.setdefault("_custom_svg_upload_id", "")
    _ensure_module_font_default()


def _ensure_module_font_default() -> None:
    """Sync subfamily/weight/file selectors with ``assets/module_fonts/``."""
    catalog = module_font_catalog()
    if not catalog:
        return

    current_file = str(st.session_state.get("module_font_file") or "")
    all_files = list_module_fonts()
    if current_file and current_file in all_files:
        subfamily, weight = subfamily_and_weight_for_file(current_file)
        weights = module_font_weights(subfamily)
        if weight not in weights:
            for label, filename in weights.items():
                if filename == current_file:
                    weight = label
                    break
        st.session_state.setdefault("module_font_subfamily", subfamily)
        st.session_state.setdefault("module_font_weight", weight)
    else:
        subfamily = st.session_state.get("module_font_subfamily") or next(iter(catalog))
        if subfamily not in catalog:
            subfamily = next(iter(catalog))
        weights = catalog[subfamily]
        weight = st.session_state.get("module_font_weight") or next(iter(weights))
        if weight not in weights:
            weight = next(iter(weights))
        st.session_state["module_font_subfamily"] = subfamily
        st.session_state["module_font_weight"] = weight
        st.session_state["module_font_file"] = weights[weight]


def _on_module_font_subfamily_change() -> None:
    """When subfamily changes, pick the first weight."""
    subfamily = str(st.session_state.get("module_font_subfamily") or "")
    weights = module_font_weights(subfamily)
    if not weights:
        return
    weight = next(iter(weights))
    st.session_state["module_font_weight"] = weight
    st.session_state["module_font_file"] = weights[weight]
    _bump_export_cache()
    _push_live_command()


def _sync_module_font_file_from_selectors() -> None:
    """Keep ``module_font_file`` aligned with subfamily + weight."""
    subfamily = str(st.session_state.get("module_font_subfamily") or "")
    weight = str(st.session_state.get("module_font_weight") or "")
    try:
        st.session_state["module_font_file"] = resolve_module_font_file(subfamily, weight)
    except KeyError:
        _ensure_module_font_default()


def _on_module_type_change() -> None:
    """Sync stored module_type and refresh the JS preview."""
    label = str(st.session_state.get("module_type_label") or MODULE_TYPE_LABELS[0])
    st.session_state["module_type"] = MODULE_TYPE_BY_LABEL.get(label, MODULE_OVAL)
    _bump_export_cache()
    _push_live_command()


def _sync_module_type_label() -> None:
    """Keep radio label in sync with stored module_type."""
    mt = str(st.session_state.get("module_type") or MODULE_OVAL)
    label = MODULE_LABEL_BY_TYPE.get(mt, MODULE_TYPE_LABELS[0])
    st.session_state.setdefault("module_type_label", label)
    if st.session_state.get("module_type_label") not in MODULE_TYPE_LABELS:
        st.session_state["module_type_label"] = label


def _push_live_command() -> None:
    """Push current session params to the JS preview (preset / reset)."""
    st.session_state["_live_cmd_id"] = int(st.session_state.get("_live_cmd_id", 0)) + 1
    st.session_state["_live_cmd"] = {"params": enrich_live_params(st.session_state)}


def _live_kerning_dict() -> dict[str, float]:
    kern: dict[str, float] = dict(st.session_state.get("kerning_pairs") or {})
    draft = _normalize_kern_pair(st.session_state.get("kern_pair_in") or "")
    if draft is not None:
        kern[draft] = float(st.session_state.get("kern_delta_in", 0.0))
    return kern


def _clear_render_cache() -> None:
    _cached_glyph_svg.clear()
    _cached_text_svg.clear()
    _cached_ttf_bytes.clear()


def _module_stamp_digest() -> str:
    """Hash of module stamp payload — busts export cache when SVG/font module changes."""
    mt = str(st.session_state.get("module_type") or MODULE_OVAL)
    if mt == MODULE_CUSTOM_SVG:
        raw = str(st.session_state.get("custom_svg_markup") or "")
    elif mt == MODULE_FONT:
        raw = "|".join(
            (
                str(st.session_state.get("module_font_file") or ""),
                str(st.session_state.get("module_font_chars") or ""),
                str(st.session_state.get("module_font_fill_order") or ""),
                str(bool(st.session_state.get("module_font_randomize", False))),
                str(int(st.session_state.get("module_font_symbols_per_module", 1))),
            )
        )
    else:
        raw = mt
    rev = int(st.session_state.get("_export_cache_rev", 0))
    return hashlib.sha256(f"{rev}|{raw}".encode()).hexdigest()[:16]


def _bump_export_cache() -> None:
    st.session_state["_export_cache_rev"] = int(st.session_state.get("_export_cache_rev", 0)) + 1
    _clear_render_cache()


def _apply_custom_svg_upload(uploaded) -> None:
    """Parse uploaded SVG once; ``UploadedFile.read()`` is single-shot on reruns."""
    upload_id = f"{uploaded.name}:{uploaded.size}:{getattr(uploaded, 'file_id', '')}"
    if st.session_state.get("_custom_svg_upload_id") == upload_id:
        return
    markup = parse_custom_svg_markup(uploaded.getvalue())
    st.session_state["custom_svg_markup"] = markup
    st.session_state["_custom_svg_upload_id"] = upload_id
    _bump_export_cache()
    _push_live_command()


def _resolved_font_style() -> str:
    """Return the exact style name the user typed/selected for export."""
    return normalize_style_name(str(st.session_state.get("font_style", DEFAULT_STYLE)))


def _all_presets() -> dict:
    return merge_profiles(st.session_state.get("custom_presets") or {})


def _custom_preset_names() -> list[str]:
    """Names stored in the user's custom_presets map (may shadow built-ins)."""
    raw = st.session_state.get("custom_presets") or {}
    return sorted(str(k).strip() for k in dict(raw) if str(k).strip())


def _on_preset_select() -> None:
    _load_preset(str(st.session_state.get("preset_selector") or "Regular"))
    _clear_render_cache()
    _push_live_command()
    st.rerun()


def _load_preset(name: str) -> None:
    """Callback: apply a named preset's geometry/FX — keep user's ink colors."""
    profiles = merge_profiles(st.session_state.get("custom_presets") or {})
    profile = profiles.get(name)
    if not profile:
        return
    apply_profile_to_session(st.session_state, profile, keys=GEOMETRY_KEYS)
    st.session_state["active_preset"] = name
    st.session_state["preset_selector"] = name
    st.session_state["font_style"] = name
    st.session_state["preset_name_in"] = name if name in _custom_preset_names() else ""


def _save_current_preset() -> None:
    """Callback: save/overwrite current settings under preset_name_in."""
    name = str(st.session_state.get("preset_name_in") or "").strip()
    if not name:
        name = str(st.session_state.get("font_style") or "").strip()
    if not name:
        return
    if name in BUILTIN_NAMES:
        # Keep built-in names reserved — require a distinct custom label.
        name = f"{name} Custom"
    customs = dict(st.session_state.get("custom_presets") or {})
    customs[name] = snapshot_from_session(dict(st.session_state))
    st.session_state["custom_presets"] = customs
    st.session_state["active_preset"] = name
    st.session_state["preset_selector"] = name
    st.session_state["font_style"] = name
    st.session_state["preset_name_in"] = name


def _delete_custom_preset(name: str | None = None) -> None:
    """Remove a custom preset by name (or the current selector if custom)."""
    target = (name if name is not None else str(st.session_state.get("preset_selector") or "")).strip()
    customs = dict(st.session_state.get("custom_presets") or {})
    if not target or target not in customs:
        return
    customs.pop(target, None)
    st.session_state["custom_presets"] = customs
    active = str(st.session_state.get("active_preset") or "")
    selected = str(st.session_state.get("preset_selector") or "")
    if active == target or selected == target:
        st.session_state["active_preset"] = "Regular"
        st.session_state["preset_name_in"] = ""
        _load_preset("Regular")
    _clear_render_cache()
    _push_live_command()
    st.rerun()


def _reroll_seed() -> None:
    import random as _random

    st.session_state["seed"] = int(_random.randint(1, 999_999))
    _clear_render_cache()


def _set_module_angle(angle: float) -> None:
    st.session_state["module_angle"] = float(angle)
    _clear_render_cache()
    _push_live_command()
    st.rerun()


def _theme_palette() -> dict[str, str]:
    """Dark studio palette (only theme)."""
    return THEME


def _apply_ink_defaults() -> None:
    """Force white glyphs on black background."""
    st.session_state["fill"] = THEME["fill"]
    st.session_state["stroke"] = THEME["stroke"]
    st.session_state["background"] = THEME["background"]


def _reset_to_regular() -> None:
    """Callback: write Regular values into session_state before widgets render."""
    apply_profile_to_session(st.session_state, BUILTIN_PRESETS["Regular"])
    _apply_ink_defaults()
    st.session_state["_regular_version"] = REGULAR_VERSION
    st.session_state["active_preset"] = "Regular"
    st.session_state["preset_selector"] = "Regular"
    st.session_state["font_style"] = "Regular"
    st.session_state["preset_name_in"] = ""
    _clear_render_cache()
    _push_live_command()
    st.rerun()


def _to_all_caps(s: str | None) -> str:
    """Force All-Caps; ё/Ё → Ё."""
    out: list[str] = []
    for ch in str(s or ""):
        if ch in "ёЁ":
            out.append("Ё")
        else:
            out.append(ch.upper())
    return "".join(out)


def show_svg(
    svg: str,
    *,
    height: int = 480,
    scale: float = 1.0,
    fit: str = "width",
) -> None:
    """Inline SVG preview via ``st.html`` + data-uri (safe, no iframe)."""
    payload = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    box_style = (
        f"width:100%;min-height:{int(height)}px;background:#000;"
        "display:flex;align-items:center;justify-content:center;"
        "border:1px solid #2A2A2A;border-radius:0.4rem;box-sizing:border-box;"
        "padding:8px;overflow:auto;"
    )
    if fit == "contain":
        img_style = "max-width:100%;max-height:100%;width:auto;height:auto;display:block;"
    else:
        width_pct = max(5.0, min(float(scale), 1.0) * 100.0)
        img_style = f"width:{width_pct:.2f}%;height:auto;display:block;margin:0 auto;"
    st.html(
        f'<div style="{box_style}">'
        f'<img src="data:image/svg+xml;base64,{payload}" alt="preview" style="{img_style}" />'
        f"</div>"
    )


def _safe_hex_color(value: object, fallback: str) -> str:
    """Return a #RRGGBB color; never collapse to an empty/invalid value."""
    s = str(value or "").strip()
    if len(s) == 7 and s[0] == "#" and all(c in "0123456789abcdefABCDEF" for c in s[1:]):
        return "#" + s[1:].upper()
    if len(s) == 6 and all(c in "0123456789abcdefABCDEF" for c in s):
        return f"#{s.upper()}"
    return fallback


def _ensure_ink_colors() -> None:
    """Normalize ink before color_picker widgets mount (never silent black-on-black)."""
    fill = _safe_hex_color(st.session_state.get("fill"), THEME["fill"])
    stroke = _safe_hex_color(st.session_state.get("stroke"), THEME["stroke"])
    background = _safe_hex_color(st.session_state.get("background"), THEME["background"])
    if fill.upper() == background.upper():
        fill = THEME["fill"] if background.upper() != THEME["fill"].upper() else "#000000"
    st.session_state["fill"] = fill
    st.session_state["stroke"] = stroke
    st.session_state["background"] = background


def _current_params(*, show_guides: bool = False, show_grid: bool = False, preview_scale: float = 1.0) -> RenderParams:
    kern_raw: dict[str, float] = st.session_state.get("kerning_pairs") or {}
    kern_pairs = tuple(sorted((str(k), float(v)) for k, v in kern_raw.items() if len(str(k)) == 2))
    fill = _safe_hex_color(st.session_state.get("fill"), THEME["fill"])
    stroke = _safe_hex_color(st.session_state.get("stroke"), THEME["stroke"])
    background = _safe_hex_color(st.session_state.get("background"), THEME["background"])
    return RenderParams(
        rx=float(st.session_state["rx"]),
        ry=float(st.session_state["ry"]),
        stroke_width=float(st.session_state["stroke_width"]),
        fill_opacity=float(st.session_state["fill_opacity"]),
        step_x=float(st.session_state["step_x"]),
        step_y=float(st.session_state["step_y"]),
        letter_spacing=float(st.session_state["letter_spacing"]),
        col_scale=int(st.session_state["col_scale"]),
        row_scale=int(st.session_state["row_scale"]),
        fill=fill,
        stroke=stroke,
        background=background,
        show_guides=show_guides,
        show_grid=show_grid,
        preview_scale=preview_scale,
        kerning_pairs=kern_pairs,
        slant_angle=float(st.session_state.get("slant_angle", 0.0)),
        jitter_x=float(st.session_state.get("jitter_x", 0.0)),
        row_jitter=float(st.session_state.get("row_jitter", 0.0)),
        seed=int(st.session_state.get("seed", 0)),
        module_angle=float(st.session_state.get("module_angle", 0.0)),
        module_type=str(st.session_state.get("module_type", MODULE_OVAL)),
        custom_svg_markup=str(st.session_state.get("custom_svg_markup") or ""),
        module_font_file=str(st.session_state.get("module_font_file") or ""),
        module_font_chars=str(st.session_state.get("module_font_chars") or ""),
        module_font_fill_order=str(st.session_state.get("module_font_fill_order") or "columns"),
        module_font_randomize=bool(st.session_state.get("module_font_randomize", False)),
        module_font_symbols_per_module=int(st.session_state.get("module_font_symbols_per_module", 1)),
    )


@st.cache_data(show_spinner=False)
def _cached_glyph_svg(ch: str, key: tuple) -> str:
    return render_glyph_svg(ch, params_from_cache_key(key))


@st.cache_data(show_spinner=False)
def _cached_text_svg(text: str, key: tuple, stamp_digest: str) -> str:
    del stamp_digest
    return render_text_svg(text, params_from_cache_key(key))


@st.cache_data(show_spinner="Сборка TTF…")
def _cached_ttf_bytes(key: tuple, style: str, stamp_digest: str) -> bytes:
    """Build TTF from a cache key + style name (always matches current export)."""
    del stamp_digest  # cache buster only — full stamp is inside ``key``
    p = with_params(params_from_cache_key(key), show_guides=False, show_grid=False, preview_scale=1.0)
    return build_ttf_bytes(p, family=FAMILY, style=style)


def _normalize_kern_pair(raw: str) -> str | None:
    s = _to_all_caps(raw.strip().replace(" ", ""))
    if len(s) != 2:
        return None
    return s


def _load_kern_pair_into_editor(pair: str, delta: float) -> None:
    """Callback: fill editor widgets before they render."""
    st.session_state["kern_pair_in"] = pair
    st.session_state["kern_delta_in"] = float(delta)


def _delete_kern_pair(pair: str) -> None:
    """Callback: remove a saved kerning pair."""
    pairs: dict[str, float] = dict(st.session_state.get("kerning_pairs") or {})
    pairs.pop(pair, None)
    st.session_state["kerning_pairs"] = pairs


def _save_draft_kern_pair() -> None:
    """Callback: persist the current draft pair/delta."""
    draft = _normalize_kern_pair(st.session_state.get("kern_pair_in") or "")
    if draft is None:
        return
    pairs: dict[str, float] = dict(st.session_state.get("kerning_pairs") or {})
    pairs[draft] = float(st.session_state.get("kern_delta_in", 0.0))
    st.session_state["kerning_pairs"] = pairs


def _inject_app_theme() -> None:
    """Inject dark Streamlit UI colors."""
    t = _theme_palette()
    st.markdown(
        f"""
        <style>
          :root {{
            --cps-app-bg: {t["app_bg"]};
            --cps-sidebar-bg: {t["sidebar_bg"]};
            --cps-secondary-bg: {t["secondary_bg"]};
            --cps-text: {t["text"]};
            --cps-muted: {t["muted"]};
            --cps-border: {t["border"]};
            --cps-mobile-btn-bg: {t["mobile_btn_bg"]};
            --cps-mobile-btn-fg: {t["mobile_btn_fg"]};
            --cps-mobile-btn-border: {t["mobile_btn_border"]};
          }}
          .stApp {{
            background-color: var(--cps-app-bg) !important;
            color: var(--cps-text) !important;
          }}
          .block-container {{
            padding-top: 1.4rem;
            padding-bottom: 2.5rem;
            max-width: 1200px;
          }}
          h1 {{
            letter-spacing: 0.06em;
            font-size: 1.75rem !important;
            font-weight: 600 !important;
            color: var(--cps-text) !important;
            margin-bottom: 0.15rem !important;
          }}
          [data-testid="stCaptionContainer"], .stCaption {{
            color: var(--cps-muted) !important;
          }}
          section[data-testid="stSidebar"] {{
            background: var(--cps-sidebar-bg) !important;
            border-right: 1px solid var(--cps-border);
          }}
          section[data-testid="stSidebar"] .block-container {{
            padding-top: 1.5rem;
          }}
          [data-baseweb="tab-list"] {{
            gap: 0.25rem;
            border-bottom: 1px solid var(--cps-border);
            margin-bottom: 1rem;
          }}
          [data-baseweb="tab"] {{
            color: var(--cps-muted) !important;
            padding: 0.65rem 1rem !important;
          }}
          [data-baseweb="tab"][aria-selected="true"] {{
            color: var(--cps-text) !important;
            border-bottom-color: var(--cps-text) !important;
          }}
          div[data-testid="stSegmentedControl"] {{
            margin-bottom: 1rem;
          }}
          div[data-testid="stSegmentedControl"] label {{
            width: 100%;
          }}
          div[data-baseweb="input"] > div,
          div[data-baseweb="select"] > div,
          textarea,
          input {{
            background-color: var(--cps-secondary-bg) !important;
            color: var(--cps-text) !important;
            border-color: var(--cps-border) !important;
          }}
          [data-testid="stExpander"] details {{
            background-color: var(--cps-secondary-bg);
            border: 1px solid var(--cps-border);
            border-radius: 0.5rem;
          }}
          [data-testid="stExpander"] summary {{
            font-weight: 600;
          }}
          [data-testid="stCode"] pre {{
            background-color: var(--cps-secondary-bg) !important;
            color: var(--cps-text) !important;
          }}
          iframe {{
            border: 1px solid var(--cps-border) !important;
            border-radius: 0.4rem;
            background: #000 !important;
          }}
          /* Dark-theme buttons: white labels on dark surfaces */
          div[data-testid="stButton"] > button,
          div[data-testid="stDownloadButton"] > button {{
            background-color: var(--cps-secondary-bg) !important;
            color: #FFFFFF !important;
            border: 1px solid var(--cps-border) !important;
          }}
          div[data-testid="stButton"] > button:hover,
          div[data-testid="stDownloadButton"] > button:hover {{
            border-color: #FFFFFF !important;
            color: #FFFFFF !important;
          }}
          div[data-testid="stButton"] > button[kind="primary"],
          div[data-testid="stButton"] > button[data-testid="stBaseButton-primary"] {{
            background-color: #222222 !important;
            color: #FFFFFF !important;
            border: 1px solid #FFFFFF !important;
            font-weight: 600 !important;
          }}
          div[data-testid="stButton"] > button[kind="primary"] p,
          div[data-testid="stButton"] > button[data-testid="stBaseButton-primary"] p,
          div[data-testid="stButton"] > button p,
          div[data-testid="stDownloadButton"] > button p {{
            color: #FFFFFF !important;
          }}
          div[data-testid="stButton"] > button:disabled {{
            opacity: 0.45 !important;
            color: var(--cps-muted) !important;
          }}
          section[data-testid="stSidebar"] div[data-testid="stButton"] button {{
            white-space: nowrap !important;
            font-size: 0.85rem !important;
          }}
          div[data-testid="stVerticalBlockBorderWrapper"] {{
            background: transparent;
          }}
          @media (max-width: 768px) {{
            h1 {{ font-size: 1.35rem !important; }}
            [data-testid="column"] {{ min-width: 100% !important; }}
          }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _inject_mobile_sidebar() -> None:
    """Overlay sidebar + hamburger toggle on narrow screens."""
    components.html(
        """
        <script>
        (() => {
          const doc = window.parent.document;
          const win = window.parent;
          const MQ = "(max-width: 768px)";
          const STYLE_ID = "cps-mobile-sidebar-style";
          const BTN_ID = "cps-mobile-menu-btn";
          const BACKDROP_ID = "cps-mobile-backdrop";

          const css = `
            @media ${MQ} {
              section[data-testid="stSidebar"] {
                position: fixed !important;
                top: 0 !important;
                left: 0 !important;
                height: 100vh !important;
                width: min(88vw, 320px) !important;
                z-index: 100000 !important;
                transform: translateX(-105%) !important;
                transition: transform 0.28s ease !important;
                box-shadow: none !important;
              }
              section[data-testid="stSidebar"].cps-mobile-open {
                transform: translateX(0) !important;
                box-shadow: 4px 0 24px rgba(0, 0, 0, 0.55) !important;
              }
              [data-testid="collapsedControl"] {
                display: none !important;
              }
              .main .block-container {
                padding-top: 3.6rem !important;
              }
              #${BTN_ID} {
                position: fixed;
                top: 0.55rem;
                left: 0.55rem;
                z-index: 100001;
                display: inline-flex;
                align-items: center;
                gap: 0.35rem;
                padding: 0.45rem 0.85rem;
                border: 1px solid var(--cps-mobile-btn-border, #333);
                border-radius: 0.45rem;
                background: var(--cps-mobile-btn-bg, #101010);
                color: var(--cps-mobile-btn-fg, #fff);
                font: 600 0.9rem/1.2 system-ui, sans-serif;
                cursor: pointer;
                box-shadow: 0 2px 10px rgba(0, 0, 0, 0.35);
              }
              #${BTN_ID}:active {
                transform: scale(0.98);
              }
              #${BACKDROP_ID} {
                position: fixed;
                inset: 0;
                z-index: 99999;
                background: rgba(0, 0, 0, 0.55);
                opacity: 0;
                pointer-events: none;
                transition: opacity 0.28s ease;
              }
              #${BACKDROP_ID}.open {
                opacity: 1;
                pointer-events: auto;
              }
            }
            @media (min-width: 769px) {
              #${BTN_ID}, #${BACKDROP_ID} {
                display: none !important;
              }
              section[data-testid="stSidebar"] {
                transform: none !important;
              }
            }
          `;

          function sidebar() {
            return doc.querySelector('section[data-testid="stSidebar"]');
          }

          function isMobile() {
            return win.matchMedia(MQ).matches;
          }

          function setOpen(open) {
            const sb = sidebar();
            const backdrop = doc.getElementById(BACKDROP_ID);
            const btn = doc.getElementById(BTN_ID);
            if (!sb) return;
            sb.classList.toggle("cps-mobile-open", open);
            backdrop?.classList.toggle("open", open);
            if (btn) btn.textContent = open ? "✕ Закрыть" : "☰ Параметры";
          }

          function toggle() {
            const sb = sidebar();
            if (!sb) return;
            setOpen(!sb.classList.contains("cps-mobile-open"));
          }

          function ensureStyles() {
            if (doc.getElementById(STYLE_ID)) return;
            const style = doc.createElement("style");
            style.id = STYLE_ID;
            style.textContent = css;
            doc.head.appendChild(style);
          }

          function ensureButton() {
            let btn = doc.getElementById(BTN_ID);
            if (!btn) {
              btn = doc.createElement("button");
              btn.id = BTN_ID;
              btn.type = "button";
              btn.textContent = "☰ Параметры";
              btn.addEventListener("click", toggle);
              doc.body.appendChild(btn);
            }
            btn.style.display = isMobile() ? "inline-flex" : "none";
          }

          function ensureBackdrop() {
            let backdrop = doc.getElementById(BACKDROP_ID);
            if (!backdrop) {
              backdrop = doc.createElement("div");
              backdrop.id = BACKDROP_ID;
              backdrop.addEventListener("click", () => setOpen(false));
              doc.body.appendChild(backdrop);
            }
            backdrop.style.display = isMobile() ? "block" : "none";
          }

          function syncLayout() {
            ensureStyles();
            ensureButton();
            ensureBackdrop();
            if (!isMobile()) {
              setOpen(false);
              return;
            }
            setOpen(false);
          }

          syncLayout();
          win.addEventListener("resize", syncLayout);
        })();
        </script>
        """,
        height=0,
    )


def _hydrate_presets_from_browser() -> None:
    """Restore custom presets from browser localStorage (once per session)."""
    if st.session_state.get("_presets_ls_ready"):
        return
    blob = load_presets_blob()
    if blob is None:
        attempts = int(st.session_state.get("_presets_ls_attempts", 0)) + 1
        st.session_state["_presets_ls_attempts"] = attempts
        if attempts <= 8:
            st.caption("Синхронизация пресетов с браузером…")
            st.stop()
        # Bridge did not answer — continue without stored presets.
        blob = {"presets": {}, "active": None}

    raw_presets = blob.get("presets") if isinstance(blob, dict) else {}
    try:
        customs, _ = profiles_from_json(
            json.dumps({"presets": raw_presets or {}, "active": blob.get("active")})
        )
    except Exception:  # noqa: BLE001
        customs = {}
    st.session_state["custom_presets"] = customs
    active = blob.get("active") if isinstance(blob, dict) else None
    if active and str(active) in merge_profiles(customs):
        st.session_state["_pending_preset"] = str(active)
    st.session_state["_presets_ls_ready"] = True
    st.session_state["_presets_ls_nonce"] = 0
    st.session_state["_presets_ls_last"] = json.dumps(
        {"format": "compresso-presets-v1", "active": active, "presets": customs},
        ensure_ascii=False,
        sort_keys=True,
    )


def _persist_presets_to_browser() -> None:
    """Autosave custom presets (+ active name) into localStorage."""
    if not st.session_state.get("_presets_ls_ready"):
        return
    payload = {
        "format": "compresso-presets-v1",
        "active": st.session_state.get("active_preset"),
        "presets": st.session_state.get("custom_presets") or {},
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if raw == st.session_state.get("_presets_ls_last"):
        return
    st.session_state["_presets_ls_last"] = raw
    nonce = int(st.session_state.get("_presets_ls_nonce", 0)) + 1
    st.session_state["_presets_ls_nonce"] = nonce
    save_presets_blob(payload, nonce=str(nonce))


# ----- UI -----
_ensure_defaults()
_sync_module_type_label()
_hydrate_presets_from_browser()

_inject_app_theme()
_inject_mobile_sidebar()

pending = st.session_state.pop("_pending_preset", None)
if pending:
    _load_preset(str(pending))

_ensure_ink_colors()

st.title("Compresso Parametric Studio")

with st.sidebar:
    st.markdown("### Текущее начертание")
    st.text_input(
        "Имя для TTF",
        key="font_style",
        placeholder="Regular",
        help="Попадёт в name table экспортируемого шрифта.",
    )
    st.caption(f"Сейчас: **{_resolved_font_style()}**")

    st.text_input(
        "Имя начертания",
        key="preset_name_in",
        placeholder="My Ultra Slant",
        help="Имя для сохранения пользовательского пресета.",
    )
    st.button(
        "Сохранить текущее",
        use_container_width=True,
        type="primary",
        on_click=_save_current_preset,
    )
    st.button(
        "Сбросить к Regular",
        use_container_width=True,
        on_click=_reset_to_regular,
    )

    _all = _all_presets()
    _preset_names = list(_all.keys())
    if st.session_state.get("preset_selector") not in _preset_names:
        st.session_state["preset_selector"] = "Regular"
        st.session_state["active_preset"] = "Regular"
    st.selectbox(
        "Начертание",
        options=_preset_names,
        key="preset_selector",
        on_change=_on_preset_select,
    )
    st.caption(f"Активно: **{st.session_state.get('active_preset')}**")

    with st.expander("Модуль", expanded=False):
        module_label = st.radio(
            "Тип модуля",
            MODULE_TYPE_LABELS,
            horizontal=True,
            key="module_type_label",
            on_change=_on_module_type_change,
        )
        st.session_state["module_type"] = MODULE_TYPE_BY_LABEL[module_label]

        if st.session_state["module_type"] == MODULE_OVAL:
            st.slider("Radius X (rx)", 5.0, 100.0, step=0.5, key="rx")
            st.slider("Radius Y (ry)", 2.0, 200.0, step=0.5, key="ry")
            st.slider("Stroke width", 0.0, 6.0, step=0.1, key="stroke_width")
            st.slider("Fill opacity", 0.0, 1.0, step=0.05, key="fill_opacity")

        elif st.session_state["module_type"] == MODULE_CUSTOM_SVG:
            uploaded = st.file_uploader(
                "Загрузить SVG",
                type=["svg"],
                key="custom_svg_upload",
            )
            if uploaded is not None:
                try:
                    _apply_custom_svg_upload(uploaded)
                except ValueError as exc:
                    st.error(str(exc))
            if st.session_state.get("custom_svg_markup"):
                st.caption("SVG загружен — модули используют этот контур.")
            st.slider("Radius X (rx)", 5.0, 100.0, step=0.5, key="rx")
            st.slider("Radius Y (ry)", 2.0, 200.0, step=0.5, key="ry")
            st.slider("Stroke width", 0.0, 6.0, step=0.1, key="stroke_width")
            st.slider("Fill opacity", 0.0, 1.0, step=0.05, key="fill_opacity")

        else:
            subfamilies = module_font_subfamilies()
            if subfamilies:
                _ensure_module_font_default()
                if st.session_state.get("module_font_subfamily") not in subfamilies:
                    st.session_state["module_font_subfamily"] = subfamilies[0]
                st.selectbox(
                    "Гарнитура",
                    subfamilies,
                    key="module_font_subfamily",
                    on_change=_on_module_font_subfamily_change,
                )
                subfamily = str(st.session_state.get("module_font_subfamily"))
                weights = module_font_weights(subfamily)
                weight_names = list(weights.keys())
                if st.session_state.get("module_font_weight") not in weight_names:
                    st.session_state["module_font_weight"] = weight_names[0]
                st.selectbox(
                    "Толщина",
                    weight_names,
                    key="module_font_weight",
                )
                _sync_module_font_file_from_selectors()
            else:
                st.warning("Положите `.ttf`/`.otf` в `assets/module_fonts/`.")
            st.text_input(
                "Строка символов",
                placeholder="01, *#@!, ABC — пусто = A–Z, А–Я, 0–9",
                key="module_font_chars",
            )
            st.slider("Высота ячейки (ry)", 2.0, 200.0, step=0.5, key="ry")
            st.caption("Размер символа задаётся высотой ячейки (ry).")
            fill_label = st.selectbox(
                "Порядок заполнения",
                FILL_ORDER_LABELS,
                index=0
                if st.session_state.get("module_font_fill_order", "columns") == "columns"
                else 1,
                key="module_font_fill_order_label",
            )
            st.session_state["module_font_fill_order"] = FILL_ORDER_BY_LABEL[fill_label]
            st.checkbox("Рандом (Randomize)", key="module_font_randomize")
            st.slider("Stroke width", 0.0, 6.0, step=0.1, key="stroke_width")
            st.slider("Fill opacity", 0.0, 1.0, step=0.05, key="fill_opacity")

        st.slider("Module Angle (°)", -90.0, 90.0, step=1.0, key="module_angle")
        q0, q45, qm45, q90 = st.columns(4)
        with q0:
            st.button("0°", use_container_width=True, on_click=_set_module_angle, args=(0.0,))
        with q45:
            st.button("45°", use_container_width=True, on_click=_set_module_angle, args=(45.0,))
        with qm45:
            st.button("-45°", use_container_width=True, on_click=_set_module_angle, args=(-45.0,))
        with q90:
            st.button("90°", use_container_width=True, on_click=_set_module_angle, args=(90.0,))

    with st.expander("Интервалы и плотность", expanded=False):
        st.slider("Grid step X", 2.0, 60.0, step=0.5, key="step_x")
        st.slider("Grid step Y (overlap OK)", 1.0, 40.0, step=0.5, key="step_y")
        st.slider("Matrix columns ×", 1, 3, step=1, key="col_scale")
        st.slider("Matrix rows ×", 1, 3, step=1, key="row_scale")
        st.slider("Letter spacing (cols)", 0.0, 6.0, step=0.5, key="letter_spacing")

    with st.expander("Деформации и FX", expanded=False):
        st.slider("Slant / Skew (°)", -30.0, 30.0, step=0.5, key="slant_angle")
        st.slider("Glitch (X Jitter)", 0.0, 50.0, step=0.5, key="jitter_x")
        st.slider("Row Jitter (Scanline Shift)", 0.0, 50.0, step=0.5, key="row_jitter")
        seed_col, roll_col = st.columns([2, 1])
        with seed_col:
            st.number_input(
                "Random Seed",
                min_value=0,
                max_value=999_999,
                step=1,
                key="seed",
            )
        with roll_col:
            st.write("")
            st.button("Reroll", use_container_width=True, on_click=_reroll_seed)
        if float(st.session_state.get("jitter_x", 0)) == 0 and float(
            st.session_state.get("row_jitter", 0)
        ) == 0:
            st.caption("Seed не влияет, пока jitter = 0.")

    with st.expander("Цвет", expanded=False):
        st.caption("Не меняется при выборе пресета — только вручную или при сбросе.")
        st.color_picker("Fill (модули)", key="fill")
        st.color_picker("Stroke (обводка)", key="stroke")
        st.color_picker("Background (фон)", key="background")

    mt = str(st.session_state.get("module_type") or MODULE_OVAL)
    if mt == MODULE_CUSTOM_SVG and st.session_state.get("custom_svg_markup"):
        _push_live_command()
    elif mt == MODULE_FONT and st.session_state.get("module_font_file"):
        _push_live_command()

    _persist_presets_to_browser()

font_style = _resolved_font_style()

tab_words, tab_inspect, tab_styles = st.tabs(
    ["Наборщик текста", "Инспектор глифа", "Начертания"]
)

LATIN = [chr(c) for c in range(ord("A"), ord("Z") + 1)]
CYR = list("АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ")
DIGITS = list("0123456789")
PUNCT = list(".,:;!?/+-=")

with tab_words:
    st.text_input("Строка (All-Caps)", key="word_text")
    text = _to_all_caps(st.session_state.get("word_text")) or DEFAULT_PHRASE

    pc1, pc2, pc3 = st.columns([2, 1, 1])
    with pc1:
        st.slider(
            "Размер шрифта (превью)",
            min_value=0.15,
            max_value=1.0,
            step=0.01,
            key="font_size",
        )
    with pc2:
        st.checkbox("Показать Baseline", key="word_show_guides")
    with pc3:
        st.checkbox("Сетка модулей", key="word_show_grid")

    preview_scale = float(st.session_state.get("font_size", DEFAULT_FONT_SIZE))
    live_params = enrich_live_params(st.session_state)
    live_studio(
        preview_only=True,
        mode="text",
        text=text,
        params=live_params,
        kerning_pairs=_live_kerning_dict(),
        show_guides=bool(st.session_state.get("word_show_guides")),
        show_grid=bool(st.session_state.get("word_show_grid")),
        preview_scale=preview_scale,
        command=st.session_state.get("_live_cmd"),
        command_id=int(st.session_state.get("_live_cmd_id", 0)),
        height=520,
        key="cps_live_preview_word",
    )

    params = _current_params()
    word_preview_params = with_params(
        params,
        show_guides=bool(st.session_state.get("word_show_guides")),
        show_grid=bool(st.session_state.get("word_show_grid")),
        preview_scale=preview_scale,
        kerning_pairs=tuple(sorted((k, float(v)) for k, v in _live_kerning_dict().items())),
    )

    with st.expander("Кернинговые пары", expanded=False):
        st.caption(
            "Пара = 2 символа (напр. АВ). Отрицательный сдвиг — плотнее, положительный — шире."
        )
        kc1, kc2 = st.columns([1, 2])
        with kc1:
            st.text_input("Пара", placeholder="АВ", key="kern_pair_in", max_chars=4)
            st.slider(
                "Сдвиг (cols)",
                min_value=-3.0,
                max_value=3.0,
                step=0.05,
                key="kern_delta_in",
            )
            draft_pair = _normalize_kern_pair(st.session_state.get("kern_pair_in") or "")
            st.button(
                "Сохранить пару",
                use_container_width=True,
                disabled=draft_pair is None,
                on_click=_save_draft_kern_pair,
            )

        with kc2:
            if draft_pair is not None:
                st.caption(f"Превью пары **{draft_pair}** — в строке выше.")
            else:
                st.caption("Введите пару из двух символов для превью.")

        current: dict[str, float] = dict(st.session_state.get("kerning_pairs") or {})
        if current:
            st.markdown("**Сохранённые пары**")
            for pair, delta in sorted(current.items()):
                r1, r2, r3, r4 = st.columns([1, 2, 1, 1])
                r1.code(pair)
                r2.write(f"{delta:+.2f} cols")
                r3.button(
                    "✎",
                    key=f"edit_kern_{pair}",
                    help="Подставить в редактор",
                    on_click=_load_kern_pair_into_editor,
                    args=(pair, float(delta)),
                )
                r4.button(
                    "✕",
                    key=f"del_kern_{pair}",
                    use_container_width=True,
                    on_click=_delete_kern_pair,
                    args=(pair,),
                )
        else:
            st.info("Сохранённых пар пока нет — двигайте слайдер, смотрите превью, затем «Сохранить».")

    export_params = with_params(
        word_preview_params,
        show_guides=False,
        show_grid=False,
        preview_scale=1.0,
    )
    stamp_digest = _module_stamp_digest()
    cache_key = params_cache_key(export_params)
    text_svg_export = _cached_text_svg(text, cache_key, stamp_digest)

    kern_count = len(export_params.kerning_pairs)
    col_svg, col_ttf = st.columns(2)
    with col_svg:
        st.download_button(
            label="Экспорт SVG",
            data=text_svg_export.encode("utf-8"),
            file_name="compresso_word.svg",
            mime="image/svg+xml",
            use_container_width=True,
            key=f"dl_svg_{stamp_digest}",
        )
    with col_ttf:
        try:
            ttf_bytes = _cached_ttf_bytes(cache_key, font_style, stamp_digest)
            st.download_button(
                label=f"Скачать TTF · {font_style}",
                data=ttf_bytes,
                file_name=f"Compresso-Parametric-{style_slug(font_style)}.ttf",
                mime="font/ttf",
                use_container_width=True,
                key=f"dl_ttf_{stamp_digest}_{style_slug(font_style)}",
            )
            st.caption(f"Кернинг: **{kern_count}** пар")
        except Exception as exc:  # noqa: BLE001 — surface in UI
            st.error(f"TTF: {exc}")

    with st.expander("Экспорт семейства (ZIP)", expanded=False):
        st.caption(
            "В архив: все built-in + ваши сохранённые начертания — SVG алфавит, specimen и TTF."
        )
        family_styles = _all_presets()
        live_name = _resolved_font_style()
        if live_name not in family_styles:
            family_styles = dict(family_styles)
            family_styles[live_name] = snapshot_from_session(dict(st.session_state))

        st.write(
            f"Начертаний: **{len(family_styles)}** — " + ", ".join(family_styles.keys())
        )
        if st.button("Собрать ZIP", use_container_width=True):
            try:
                with st.spinner("Сборка ZIP…"):
                    st.session_state["family_zip_bytes"] = build_family_zip(
                        family_styles,
                        family=FAMILY,
                        specimen=text or DEFAULT_PHRASE,
                    )
                    st.session_state["family_zip_ok"] = True
            except Exception as exc:  # noqa: BLE001
                st.session_state["family_zip_ok"] = False
                st.error(f"ZIP: {exc}")

        zip_bytes = st.session_state.get("family_zip_bytes")
        if zip_bytes and st.session_state.get("family_zip_ok"):
            st.download_button(
                "Скачать Compresso_Family_Pack.zip",
                data=zip_bytes,
                file_name="Compresso_Family_Pack.zip",
                mime="application/zip",
                use_container_width=True,
                key=f"dl_family_zip_{len(zip_bytes)}",
            )

with tab_inspect:
    c1, c2 = st.columns([1, 2])
    with c1:
        group = st.radio(
            "Набор",
            ["Латиница A–Z", "Кириллица А–Я", "Цифры 0–9", "Пунктуация"],
            index=1,
        )
        pool = {
            "Латиница A–Z": LATIN,
            "Кириллица А–Я": CYR,
            "Цифры 0–9": DIGITS,
            "Пунктуация": PUNCT,
        }[group]
        letter = st.selectbox("Символ", pool, index=0, key="inspect_letter")
        st.checkbox("Baseline / Cap-Height", key="inspect_show_guides")
        st.checkbox("Сетка модулей", key="inspect_show_grid")
        pts = get_glyph(letter)
        st.write(f"Модулей в глифе: **{len(pts)}**")
        if pts:
            rows = sorted({r for _, r in pts})
            st.code(
                f"width cols: {glyph_width(letter)}\n"
                f"row span: {min(rows)}…{max(rows)}\n"
                f"baseline: {BASELINE}",
                language="text",
            )

    params = _current_params()
    inspect_params = with_params(
        params,
        show_guides=bool(st.session_state.get("inspect_show_guides")),
        show_grid=bool(st.session_state.get("inspect_show_grid")),
    )
    with c2:
        live_studio(
            preview_only=True,
            mode="glyph",
            glyph=str(st.session_state.get("inspect_letter", "А")),
            params=enrich_live_params(st.session_state),
            show_guides=bool(st.session_state.get("inspect_show_guides")),
            show_grid=bool(st.session_state.get("inspect_show_grid")),
            command=st.session_state.get("_live_cmd"),
            command_id=int(st.session_state.get("_live_cmd_id", 0)),
            height=420,
            key="cps_live_preview_glyph",
        )
        svg = _cached_glyph_svg(letter, params_cache_key(inspect_params))
        st.download_button(
            label=f"Скачать SVG · {letter}",
            data=svg.encode("utf-8"),
            file_name=f"compresso_glyph_{letter}.svg",
            mime="image/svg+xml",
            use_container_width=True,
        )

with tab_styles:
    st.markdown("### Сохранённые начертания")
    st.caption(
        "Выбор начертания — в боковом меню. Здесь можно удалить свои пресеты "
        "(они хранятся в localStorage браузера)."
    )

    all_profiles = _all_presets()
    preset_names = list(all_profiles.keys())

    st.markdown("**Встроенные**")
    st.caption(", ".join(n for n in preset_names if n in BUILTIN_NAMES) or "—")

    st.markdown("**Ваши**")
    custom_names = _custom_preset_names()
    if not custom_names:
        st.caption("Пока нет — сохраните из бокового меню.")
    else:
        for cname in custom_names:
            row_l, row_r = st.columns([5, 1])
            with row_l:
                is_active = cname == st.session_state.get("active_preset")
                st.write(f"{'● ' if is_active else ''}{cname}")
            with row_r:
                st.button(
                    "Удалить",
                    key=f"del_preset_{cname}",
                    use_container_width=True,
                    on_click=_delete_custom_preset,
                    args=(cname,),
                )
