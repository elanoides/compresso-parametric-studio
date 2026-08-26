"""Browser localStorage bridge for Compresso preset persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit.components.v1 as components

STORAGE_KEY = "compresso_presets_v1"
_COMPONENT_DIR = Path(__file__).resolve().parent.parent / "components" / "cps_local_storage"

_cps_local_storage = components.declare_component(
    "cps_local_storage",
    path=str(_COMPONENT_DIR),
)


def load_presets_blob(*, storage_key: str = STORAGE_KEY) -> dict[str, Any] | None:
    """Read presets JSON blob from localStorage. ``None`` while the bridge is syncing."""
    result = _cps_local_storage(
        mode="load",
        storage_key=storage_key,
        default=None,
        key=f"cps_ls_load_{storage_key}",
    )
    if result is None:
        return None
    if not isinstance(result, dict) or not result.get("ok"):
        return {"presets": {}, "active": None}
    raw = result.get("payload") or ""
    if not str(raw).strip():
        return {"presets": {}, "active": None}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"presets": {}, "active": None}
    if not isinstance(data, dict):
        return {"presets": {}, "active": None}
    return data


def save_presets_blob(
    payload: dict[str, Any],
    *,
    storage_key: str = STORAGE_KEY,
    nonce: str = "0",
) -> None:
    """Write presets JSON blob to localStorage."""
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    _cps_local_storage(
        mode="save",
        storage_key=storage_key,
        payload=raw,
        default=None,
        key=f"cps_ls_save_{storage_key}_{nonce}",
    )
