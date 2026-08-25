"""Compresso Parametric Studio — Streamlit UI."""

from __future__ import annotations

import base64

import streamlit as st

from engine.exporter import (
    DEFAULT_STYLE,
    FAMILY,
    STYLE_NAMES,
    build_glyphs_json,
    build_ttf_bytes,
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
        st.session_state.setdefault("word_text", DEFAULT_PHRASE)
        return
    for key, value in REGULAR.items():
        st.session_state.setdefault(key, value)
    st.session_state.setdefault("font_style", DEFAULT_STYLE)
    st.session_state.setdefault("font_size", DEFAULT_FONT_SIZE)
    st.session_state.setdefault("kerning_pairs", {})
    st.session_state.setdefault("kern_pair_in", "АВ")
    st.session_state.setdefault("kern_delta_in", -0.5)
    st.session_state.setdefault("word_text", DEFAULT_PHRASE)


def _reset_to_regular() -> None:
    """Callback: write Regular values into session_state before widgets render."""
    for key, value in REGULAR.items():
        st.session_state[key] = value
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


def _normalize_kern_pair(raw: str) -> str | None:
    s = _to_all_caps(raw.strip().replace(" ", ""))
    if len(s) != 2:
        return None
    return s


# ----- UI -----
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
    st.button(
        "Сбросить к Regular (Default)",
        use_container_width=True,
        on_click=_reset_to_regular,
    )

    st.header("Начертание")
    style_choice = st.selectbox(
        "Название стиля (для TTF/JSON)",
        options=list(STYLE_NAMES) + ["Custom…"],
        index=list(STYLE_NAMES).index(st.session_state["font_style"])
        if st.session_state["font_style"] in STYLE_NAMES
        else len(STYLE_NAMES),
        key="style_select",
    )
    if style_choice == "Custom…":
        custom = st.text_input("Своё название", value=st.session_state.get("font_style_custom", "Regular"))
        st.session_state["font_style_custom"] = custom
        st.session_state["font_style"] = (custom or "Regular").strip() or "Regular"
    else:
        st.session_state["font_style"] = style_choice

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
font_style = str(st.session_state["font_style"])

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
            if st.button("Сохранить пару", use_container_width=True, disabled=draft_pair is None):
                if draft_pair is None:
                    st.warning("Нужно ровно 2 символа.")
                else:
                    pairs: dict[str, float] = dict(st.session_state.get("kerning_pairs") or {})
                    pairs[draft_pair] = draft_delta
                    st.session_state["kerning_pairs"] = pairs
                    st.rerun()

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
                if r3.button("✎", key=f"edit_kern_{pair}", help="Подставить в редактор"):
                    st.session_state["kern_pair_in"] = pair
                    st.session_state["kern_delta_in"] = float(delta)
                    st.rerun()
                if r4.button("✕", key=f"del_kern_{pair}", use_container_width=True):
                    current.pop(pair, None)
                    st.session_state["kerning_pairs"] = current
                    st.rerun()
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
        params,
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
            label="Экспорт JSON",
            data=json_blob.encode("utf-8"),
            file_name=f"compresso_{font_style.lower()}.json",
            mime="application/json",
            use_container_width=True,
        )
    with col_ttf:
        if st.button("Собрать TTF", use_container_width=True):
            try:
                st.session_state["ttf_bytes"] = build_ttf_bytes(
                    export_params, family=FAMILY, style=font_style
                )
                st.session_state["ttf_ok"] = True
                st.session_state["ttf_style"] = font_style
            except Exception as exc:  # noqa: BLE001 — surface in UI
                st.session_state["ttf_ok"] = False
                st.error(f"TTF: {exc}")
        ttf_bytes = st.session_state.get("ttf_bytes")
        if ttf_bytes and st.session_state.get("ttf_ok"):
            style_slug = str(st.session_state.get("ttf_style", font_style)).replace(" ", "")
            st.download_button(
                label=f"Скачать TTF · {st.session_state.get('ttf_style', font_style)}",
                data=ttf_bytes,
                file_name=f"Compresso-Parametric-{style_slug}.ttf",
                mime="font/ttf",
                use_container_width=True,
            )
