"""Compresso Parametric Studio — Streamlit app."""

from __future__ import annotations

import base64

import streamlit as st

from engine.export_ttf import build_ttf_bytes
from engine.glyphs import GLYPHS, BASELINE, BODY_TOP, CAP_HEIGHT, ROWS_TOTAL
from engine.render import RenderParams, render_glyph_svg, render_text_svg

# ----- Regular (Default) — studio reference look -----
REGULAR_VERSION = 3
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

WORD_PREVIEW_SCALE = 0.38

st.set_page_config(
    page_title="Compresso Parametric Studio",
    page_icon="▣",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _ensure_defaults() -> None:
    if st.session_state.get("_regular_version") != REGULAR_VERSION:
        for key, value in REGULAR.items():
            st.session_state[key] = value
        st.session_state["_regular_version"] = REGULAR_VERSION
        return
    for key, value in REGULAR.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _reset_to_regular() -> None:
    for key, value in REGULAR.items():
        st.session_state[key] = value
    st.session_state["_regular_version"] = REGULAR_VERSION


def show_svg(svg: str, *, height: int = 480) -> None:
    payload = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    st.iframe(f"data:image/svg+xml;base64,{payload}", height=height)


_ensure_defaults()

st.markdown(
    """
    <style>
      .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
      h1 { letter-spacing: 0.04em; }
      div[data-testid="stSidebar"] { background: #101010; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Compresso Parametric Studio")
st.caption(
    f"All-Caps modular oval type · grid {ROWS_TOTAL} rows · "
    f"Cap-Height {BODY_TOP}–{BASELINE} ({CAP_HEIGHT}) · Baseline = row {BASELINE}"
)

with st.sidebar:
    st.header("Пресет")
    if st.button("Сбросить к Regular (Default)", use_container_width=True):
        _reset_to_regular()
        st.rerun()

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

params = RenderParams(
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
)

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
        st.write(f"Модулей в глифе: **{len(GLYPHS.get(letter, []))}**")
        coords = GLYPHS.get(letter, [])
        if coords:
            cols = sorted({c for c, _ in coords})
            rows = sorted({r for _, r in coords})
            st.code(
                f"width cols: {max(cols) + 1 if cols else 0}\n"
                f"row span: {min(rows)}…{max(rows)}\n"
                f"baseline: {BASELINE}",
                language="text",
            )

    inspect_params = RenderParams(
        **{**params.__dict__, "show_guides": show_guides, "show_grid": show_grid}
    )
    svg = render_glyph_svg(letter, inspect_params)
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
            file_name=f"crt_glyph_{letter}.svg",
            mime="image/svg+xml",
            use_container_width=True,
        )

DEFAULT_PHRASE = "НАДЁЖНЫЕ И РАБОТЯЩИЕ"


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


with tab_words:
    if "word_text" not in st.session_state:
        st.session_state["word_text"] = DEFAULT_PHRASE

    st.text_input(
        "Строка (All-Caps)",
        key="word_text",
        on_change=_on_word_text_change,
    )
    text = _to_all_caps(st.session_state["word_text"])
    show_base = st.checkbox("Показать Baseline набора", value=True)
    word_params = RenderParams(
        **{
            **params.__dict__,
            "show_guides": show_base,
            "show_grid": False,
            "preview_scale": WORD_PREVIEW_SCALE,
        }
    )
    export_params = RenderParams(
        **{**params.__dict__, "show_guides": False, "show_grid": False, "preview_scale": 1.0}
    )
    text_svg_preview = render_text_svg(text, word_params)
    text_svg_export = render_text_svg(text, export_params)
    embed_h = int(
        (
            word_params.padding * 2
            + (ROWS_TOTAL - 1) * word_params.step_y
            + word_params.ry * 2
            + 60
        )
        * WORD_PREVIEW_SCALE
        + 40
    )
    show_svg(text_svg_preview, height=min(max(embed_h, 200), 520))

    col_svg, col_ttf = st.columns(2)
    with col_svg:
        st.download_button(
            label="Экспорт SVG-вектора",
            data=text_svg_export.encode("utf-8"),
            file_name="compresso_word.svg",
            mime="image/svg+xml",
            use_container_width=True,
        )
    with col_ttf:
        if st.button("Собрать TTF (весь набор)", use_container_width=True):
            try:
                st.session_state["ttf_bytes"] = build_ttf_bytes(params)
                st.session_state["ttf_ok"] = True
            except Exception as exc:  # noqa: BLE001 — show in UI
                st.session_state["ttf_ok"] = False
                st.error(f"TTF: {exc}")
        ttf_bytes = st.session_state.get("ttf_bytes")
        if ttf_bytes and st.session_state.get("ttf_ok"):
            st.download_button(
                label="Скачать TTF",
                data=ttf_bytes,
                file_name="Compresso-Parametric-Regular.ttf",
                mime="font/ttf",
                use_container_width=True,
            )
