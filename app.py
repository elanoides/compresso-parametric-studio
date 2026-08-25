"""Compresso Parametric Studio — Streamlit UI."""

from __future__ import annotations

import base64

import streamlit as st
import streamlit.components.v1 as components

from engine.exporter import (
    DEFAULT_STYLE,
    FAMILY,
    STYLE_NAMES,
    build_glyphs_json,
    build_ttf_bytes,
    normalize_style_name,
    style_slug,
)
from engine.geometry import RenderParams, params_cache_key, with_params
from engine.glyphs import (
    BASELINE,
    BODY_TOP,
    CAP_HEIGHT,
    ROWS_TOTAL,
    get_glyph,
    glyph_width,
)
from engine.render import render_glyph_svg, render_text_svg

# ----- Regular (Default) -----
REGULAR_VERSION = 4
REGULAR: dict[str, float | int | str] = {
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
}

DEFAULT_PHRASE = "НАДЁЖНЫЕ И РАБОТЯЩИЕ"
DEFAULT_FONT_SIZE = 0.38  # preview_scale for word composer

THEMES: dict[str, dict[str, str]] = {
    "dark": {
        "app_bg": "#000000",
        "sidebar_bg": "#101010",
        "secondary_bg": "#101010",
        "text": "#FFFFFF",
        "muted": "#AAAAAA",
        "border": "#333333",
        "fill": "#FFFFFF",
        "stroke": "#FFFFFF",
        "background": "#000000",
        "mobile_btn_bg": "#101010",
        "mobile_btn_fg": "#FFFFFF",
        "mobile_btn_border": "#333333",
    },
    "light": {
        "app_bg": "#FFFFFF",
        "sidebar_bg": "#F5F5F5",
        "secondary_bg": "#F0F0F0",
        "text": "#111111",
        "muted": "#555555",
        "border": "#DDDDDD",
        "fill": "#000000",
        "stroke": "#000000",
        "background": "#FFFFFF",
        "mobile_btn_bg": "#FFFFFF",
        "mobile_btn_fg": "#111111",
        "mobile_btn_border": "#DDDDDD",
    },
}

st.set_page_config(
    page_title="Compresso Parametric Studio",
    page_icon="▣",
    layout="wide",
    initial_sidebar_state="collapsed",
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
        st.session_state.setdefault("word_text", DEFAULT_PHRASE)
        st.session_state.setdefault("ui_theme", "dark")
        return
    for key, value in REGULAR.items():
        st.session_state.setdefault(key, value)
    st.session_state.setdefault("font_style", DEFAULT_STYLE)
    st.session_state.setdefault("font_size", DEFAULT_FONT_SIZE)
    st.session_state.setdefault("kerning_pairs", {})
    st.session_state.setdefault("kern_pair_in", "АВ")
    st.session_state.setdefault("kern_delta_in", -0.5)
    st.session_state.setdefault("word_text", DEFAULT_PHRASE)
    st.session_state.setdefault("ui_theme", "dark")


def _resolved_font_style() -> str:
    """Return the exact style name the user typed/selected for export."""
    return normalize_style_name(str(st.session_state.get("font_style", DEFAULT_STYLE)))


def _apply_style_preset(name: str) -> None:
    """Callback: put a preset style name into the free-text field."""
    st.session_state["font_style"] = name


def _theme_palette(name: str | None = None) -> dict[str, str]:
    """Return UI + preview colors for the active theme."""
    key = name or str(st.session_state.get("ui_theme", "dark"))
    return THEMES.get(key, THEMES["dark"])


def _apply_theme_colors(theme: str | None = None) -> None:
    """Sync glyph preview colors with the selected UI theme."""
    palette = _theme_palette(theme)
    st.session_state["fill"] = palette["fill"]
    st.session_state["stroke"] = palette["stroke"]
    st.session_state["background"] = palette["background"]


def _on_theme_change() -> None:
    _apply_theme_colors(str(st.session_state.get("ui_theme", "dark")))


def _reset_to_regular() -> None:
    """Callback: write Regular values into session_state before widgets render."""
    for key, value in REGULAR.items():
        if key in {"fill", "stroke", "background"}:
            continue
        st.session_state[key] = value
    _apply_theme_colors()
    st.session_state["_regular_version"] = REGULAR_VERSION
    st.session_state["font_size"] = DEFAULT_FONT_SIZE


def _to_all_caps(s: str) -> str:
    """Force All-Caps; ё/Ё → Ё."""
    out: list[str] = []
    for ch in s:
        if ch in "ёЁ":
            out.append("Ё")
        else:
            out.append(ch.upper())
    return "".join(out)


def _on_word_text_change() -> None:
    st.session_state["word_text"] = _to_all_caps(st.session_state.get("word_text", ""))


def show_svg(svg: str, *, height: int = 480) -> None:
    """Embed SVG via base64 data URL (markdown strips raw SVG)."""
    payload = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    st.iframe(f"data:image/svg+xml;base64,{payload}", height=height)


def _current_params(*, show_guides: bool = False, show_grid: bool = False, preview_scale: float = 1.0) -> RenderParams:
    kern_raw: dict[str, float] = st.session_state.get("kerning_pairs") or {}
    kern_pairs = tuple(sorted((str(k), float(v)) for k, v in kern_raw.items() if len(str(k)) == 2))
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
        fill=str(st.session_state["fill"]),
        stroke=str(st.session_state["stroke"]),
        background=str(st.session_state["background"]),
        show_guides=show_guides,
        show_grid=show_grid,
        preview_scale=preview_scale,
        kerning_pairs=kern_pairs,
    )


@st.cache_data(show_spinner=False)
def _cached_glyph_svg(ch: str, key: tuple) -> str:
    p = RenderParams(
        rx=key[0],
        ry=key[1],
        stroke_width=key[2],
        fill_opacity=key[3],
        step_x=key[4],
        step_y=key[5],
        letter_spacing=key[6],
        col_scale=key[7],
        row_scale=key[8],
        fill=key[9],
        stroke=key[10],
        background=key[11],
        show_guides=key[12],
        show_grid=key[13],
        padding=key[14],
        preview_scale=key[15],
        kerning_pairs=key[16],
    )
    return render_glyph_svg(ch, p)


@st.cache_data(show_spinner=False)
def _cached_text_svg(text: str, key: tuple) -> str:
    p = RenderParams(
        rx=key[0],
        ry=key[1],
        stroke_width=key[2],
        fill_opacity=key[3],
        step_x=key[4],
        step_y=key[5],
        letter_spacing=key[6],
        col_scale=key[7],
        row_scale=key[8],
        fill=key[9],
        stroke=key[10],
        background=key[11],
        show_guides=key[12],
        show_grid=key[13],
        padding=key[14],
        preview_scale=key[15],
        kerning_pairs=key[16],
    )
    return render_text_svg(text, p)


@st.cache_data(show_spinner="Сборка TTF…")
def _cached_ttf_bytes(key: tuple, style: str) -> bytes:
    """Build TTF from a cache key + style name (always matches current export)."""
    p = RenderParams(
        rx=key[0],
        ry=key[1],
        stroke_width=key[2],
        fill_opacity=key[3],
        step_x=key[4],
        step_y=key[5],
        letter_spacing=key[6],
        col_scale=key[7],
        row_scale=key[8],
        fill=key[9],
        stroke=key[10],
        background=key[11],
        show_guides=False,
        show_grid=False,
        padding=key[14],
        preview_scale=1.0,
        kerning_pairs=key[16],
    )
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


def _inject_app_theme(theme: str) -> None:
    """Inject Streamlit UI colors for dark/light mode."""
    t = _theme_palette(theme)
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
          .block-container {{ padding-top: 1.2rem; padding-bottom: 2rem; }}
          h1, h2, h3, h4, h5, h6, p, label, span, div {{
            color: inherit;
          }}
          h1 {{ letter-spacing: 0.04em; color: var(--cps-text) !important; }}
          section[data-testid="stSidebar"] {{
            background: var(--cps-sidebar-bg) !important;
            border-right: 1px solid var(--cps-border);
          }}
          section[data-testid="stSidebar"] * {{
            color: var(--cps-text);
          }}
          [data-testid="stCaptionContainer"], .stCaption {{
            color: var(--cps-muted) !important;
          }}
          [data-baseweb="tab"] {{
            color: var(--cps-text) !important;
          }}
          [data-baseweb="tab"][aria-selected="true"] {{
            border-bottom-color: var(--cps-text) !important;
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
          [data-testid="stCode"] pre {{
            background-color: var(--cps-secondary-bg) !important;
            color: var(--cps-text) !important;
          }}
          iframe {{
            border: 1px solid var(--cps-border) !important;
            border-radius: 0.35rem;
          }}
          section[data-testid="stSidebar"] div[data-testid="stButton"] button {{
            white-space: nowrap !important;
            font-size: 0.78rem !important;
            line-height: 1.2 !important;
            padding-left: 0.4rem !important;
            padding-right: 0.4rem !important;
            overflow: hidden;
            text-overflow: ellipsis;
          }}
          @media (max-width: 768px) {{
            h1 {{ font-size: 1.35rem; margin-bottom: 0.25rem; }}
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


# ----- UI -----
_ensure_defaults()

_inject_app_theme(str(st.session_state.get("ui_theme", "dark")))
_inject_mobile_sidebar()

st.title("Compresso Parametric Studio")
st.caption(
    f"All-Caps modular oval type · grid {ROWS_TOTAL} rows · "
    f"Cap-Height {BODY_TOP}–{BASELINE} ({CAP_HEIGHT}) · Baseline = row {BASELINE}"
)

with st.sidebar:
    st.header("Тема")
    st.radio(
        "Интерфейс",
        options=["dark", "light"],
        format_func=lambda value: "Тёмная" if value == "dark" else "Светлая",
        horizontal=True,
        key="ui_theme",
        on_change=_on_theme_change,
    )

    st.header("Пресет")
    st.button(
        "Сбросить к Regular (Default)",
        use_container_width=True,
        on_click=_reset_to_regular,
    )

    st.header("Начертание")
    st.text_input(
        "Название начертания (попадёт в TTF/JSON как есть)",
        key="font_style",
        placeholder="Например Expanded или Display",
        help="Именно этот текст запишется в метаданные шрифта.",
    )
    st.caption("Быстрый выбор:")
    preset_cols = st.columns(2)
    for i, name in enumerate(STYLE_NAMES):
        preset_cols[i % 2].button(
            name,
            key=f"style_preset_{name}",
            use_container_width=True,
            on_click=_apply_style_preset,
            args=(name,),
        )
    st.caption(f"В экспорт: **{_resolved_font_style()}**")

    st.header("Module")
    st.slider("Radius X (rx)", 1.0, 90.0, step=0.5, key="rx")
    st.slider("Radius Y (ry)", 0.5, 40.0, step=0.5, key="ry")
    st.slider("Stroke width", 0.0, 6.0, step=0.1, key="stroke_width")
    st.slider("Fill opacity", 0.0, 1.0, step=0.05, key="fill_opacity")

    st.header("Spacing & density")
    st.slider("Grid step X", 2.0, 60.0, step=0.5, key="step_x")
    st.slider("Grid step Y (overlap OK)", 1.0, 40.0, step=0.5, key="step_y")
    st.slider("Matrix columns ×", 1, 3, step=1, key="col_scale")
    st.slider("Matrix rows ×", 1, 3, step=1, key="row_scale")
    st.slider("Letter spacing (cols)", 0.0, 6.0, step=0.5, key="letter_spacing")

    st.header("Look")
    st.color_picker("Fill", key="fill")
    st.color_picker("Stroke", key="stroke")
    st.color_picker("Background", key="background")

params = _current_params()
font_style = _resolved_font_style()

tab_inspect, tab_words = st.tabs(["Инспектор глифа", "Наборщик текста"])

LATIN = [chr(c) for c in range(ord("A"), ord("Z") + 1)]
CYR = list("АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ")
DIGITS = list("0123456789")
PUNCT = list(".,:;!?/+-=")

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
        letter = st.selectbox("Символ", pool, index=0)
        show_guides = st.checkbox("Baseline / Cap-Height", value=True)
        show_grid = st.checkbox("Сетка осей", value=True)
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

    inspect_params = with_params(params, show_guides=show_guides, show_grid=show_grid)
    svg = _cached_glyph_svg(letter, params_cache_key(inspect_params))
    with c2:
        embed_h = int(
            inspect_params.padding * 2
            + (ROWS_TOTAL - 1) * inspect_params.step_y
            + inspect_params.ry * 2
            + 80
        )
        show_svg(svg, height=min(max(embed_h, 420), 900))
        st.download_button(
            label=f"Скачать SVG · {letter}",
            data=svg.encode("utf-8"),
            file_name=f"compresso_glyph_{letter}.svg",
            mime="image/svg+xml",
            use_container_width=True,
        )

with tab_words:
    st.text_input(
        "Строка (All-Caps)",
        key="word_text",
        on_change=_on_word_text_change,
    )
    text = _to_all_caps(st.session_state["word_text"])

    size_col, base_col = st.columns([2, 1])
    with size_col:
        st.slider(
            "Размер шрифта (превью)",
            min_value=0.15,
            max_value=1.0,
            step=0.01,
            key="font_size",
            help="Масштаб предпросмотра наборщика. Экспорт SVG/TTF — в полном размере.",
        )
    with base_col:
        show_base = st.checkbox("Показать Baseline", value=True)

    with st.expander("Кернинговые пары", expanded=True):
        st.caption(
            "Пара = 2 символа (напр. АВ). Сдвиг в колонках: "
            "отрицательный — плотнее, положительный — шире. "
            "Превью обновляется сразу при движении слайдера."
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
            draft_delta = float(st.session_state.get("kern_delta_in", 0.0))
            st.button(
                "Сохранить пару",
                use_container_width=True,
                disabled=draft_pair is None,
                on_click=_save_draft_kern_pair,
            )

        with kc2:
            # Live pair preview: saved kerning + current draft override
            live_kern = dict(st.session_state.get("kerning_pairs") or {})
            preview_label = "—"
            if draft_pair:
                live_kern[draft_pair] = draft_delta
                preview_label = f"{draft_pair}  ({draft_delta:+.2f})"
                pair_text = draft_pair
            else:
                pair_text = "АВ"
                preview_label = "введите пару"

            live_pairs_tuple = tuple(sorted((k, float(v)) for k, v in live_kern.items()))
            kern_preview_params = with_params(
                params,
                show_guides=True,
                show_grid=False,
                preview_scale=0.55,
                kerning_pairs=live_pairs_tuple,
            )
            st.caption(f"Превью: **{preview_label}**")
            pair_svg = _cached_text_svg(pair_text, params_cache_key(kern_preview_params))
            show_svg(pair_svg, height=220)

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

    # Draft kerning also affects the main word preview in real time
    live_kern_for_word = dict(st.session_state.get("kerning_pairs") or {})
    draft_pair_w = _normalize_kern_pair(st.session_state.get("kern_pair_in") or "")
    if draft_pair_w is not None:
        live_kern_for_word[draft_pair_w] = float(st.session_state.get("kern_delta_in", 0.0))

    params = _current_params()
    live_tuple = tuple(sorted((k, float(v)) for k, v in live_kern_for_word.items()))
    params_live = with_params(params, kerning_pairs=live_tuple)
    font_size = float(st.session_state["font_size"])
    word_params = with_params(
        params_live,
        show_guides=show_base,
        show_grid=False,
        preview_scale=font_size,
    )
    export_params = with_params(
        params_live,
        show_guides=False,
        show_grid=False,
        preview_scale=1.0,
    )

    text_svg_preview = _cached_text_svg(text, params_cache_key(word_params))
    text_svg_export = _cached_text_svg(text, params_cache_key(export_params))

    embed_h = int(
        (
            word_params.padding * 2
            + (ROWS_TOTAL - 1) * word_params.step_y
            + word_params.ry * 2
            + 60
        )
        * font_size
        + 40
    )
    show_svg(text_svg_preview, height=min(max(embed_h, 160), 640))

    kern_count = len(export_params.kerning_pairs)
    col_svg, col_json, col_ttf = st.columns(3)
    with col_svg:
        st.download_button(
            label="Экспорт SVG",
            data=text_svg_export.encode("utf-8"),
            file_name="compresso_word.svg",
            mime="image/svg+xml",
            use_container_width=True,
        )
    with col_json:
        json_blob = build_glyphs_json(export_params, family=FAMILY, style=font_style)
        st.download_button(
            label=f"Экспорт JSON · {font_style}",
            data=json_blob.encode("utf-8"),
            file_name=f"compresso_{style_slug(font_style).lower()}.json",
            mime="application/json",
            use_container_width=True,
            key=f"dl_json_{style_slug(font_style)}",
        )
    with col_ttf:
        try:
            ttf_bytes = _cached_ttf_bytes(params_cache_key(export_params), font_style)
            st.download_button(
                label=f"Скачать TTF · {font_style}",
                data=ttf_bytes,
                file_name=f"Compresso-Parametric-{style_slug(font_style)}.ttf",
                mime="font/ttf",
                use_container_width=True,
                key=f"dl_ttf_{style_slug(font_style)}_{kern_count}_{len(ttf_bytes)}",
            )
            st.caption(
                f"Начертание: **{font_style}** · кернинг: **{kern_count}** пар"
            )
        except Exception as exc:  # noqa: BLE001 — surface in UI
            st.error(f"TTF: {exc}")
