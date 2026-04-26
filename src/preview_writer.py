"""Encode gated payloads to a preview file ComfyUI's /view endpoint can serve.

M1: IMAGE only. M3 will add LATENT, MASK, VIDEO_FRAMES.

Files are written under <comfy_temp>/approve_reject/<node_id>/. URLs returned
are relative paths suitable for `/view?filename=...&type=temp&subfolder=...`.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

import folder_paths


_SUBFOLDER_ROOT = "approve_reject"
_HISTORY_LIMIT_DEFAULT = 5
_history: dict[str, list[dict[str, str]]] = {}
_last_approved: dict[str, dict[str, str]] = {}


def _temp_dir_for(node_id: str) -> Path:
    base = Path(folder_paths.get_temp_directory()) / _SUBFOLDER_ROOT / str(node_id)
    base.mkdir(parents=True, exist_ok=True)
    return base


def _view_url(node_id: str, filename: str) -> str:
    subfolder = f"{_SUBFOLDER_ROOT}/{node_id}"
    return f"/view?filename={filename}&type=temp&subfolder={subfolder}"


def _image_tensor_to_png_bytes(tensor: Any) -> bytes:
    arr = tensor[0] if hasattr(tensor, "shape") and len(tensor.shape) == 4 else tensor
    if hasattr(arr, "cpu"):
        arr = arr.cpu().numpy()
    arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr)
    from io import BytesIO

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _write_png_sync(path: Path, png_bytes: bytes) -> None:
    path.write_bytes(png_bytes)


async def write_image_preview(node_id: str, image_tensor: Any) -> dict[str, str]:
    """Encode and write a single IMAGE preview. Returns {url, filename, type}."""
    png_bytes = await asyncio.to_thread(_image_tensor_to_png_bytes, image_tensor)
    filename = f"{int(time.time() * 1000)}.png"
    target = _temp_dir_for(node_id) / filename
    await asyncio.to_thread(_write_png_sync, target, png_bytes)

    return {
        "url": _view_url(node_id, filename),
        "filename": filename,
        "type": "image",
    }


def record_pending(node_id: str, entry: dict[str, str], history_size: int = _HISTORY_LIMIT_DEFAULT) -> None:
    """Track a just-written preview as a candidate; promoted/demoted on decision."""
    items = _history.setdefault(node_id, [])
    items.append({**entry, "status": "pending"})
    _evict_excess(node_id, history_size)


def mark_approved(node_id: str, entry: dict[str, str]) -> None:
    items = _history.setdefault(node_id, [])
    for it in items:
        if it.get("filename") == entry.get("filename"):
            it["status"] = "approved"
            break
    _last_approved[node_id] = entry


def mark_rejected(node_id: str, entry: dict[str, str]) -> None:
    items = _history.setdefault(node_id, [])
    for it in items:
        if it.get("filename") == entry.get("filename"):
            it["status"] = "rejected"
            break


def get_history(node_id: str, limit: int = _HISTORY_LIMIT_DEFAULT) -> list[dict[str, str]]:
    items = _history.get(node_id, [])
    return list(reversed(items[-limit:]))


def get_last_approved(node_id: str) -> dict[str, str] | None:
    return _last_approved.get(node_id)


def _evict_excess(node_id: str, history_size: int) -> None:
    items = _history.get(node_id, [])
    overflow = len(items) - history_size
    if overflow <= 0:
        return
    base = Path(folder_paths.get_temp_directory()) / _SUBFOLDER_ROOT / str(node_id)
    for _ in range(overflow):
        evicted = items.pop(0)
        candidate = base / evicted.get("filename", "")
        try:
            candidate.unlink(missing_ok=True)
        except OSError:
            pass


def reset_node(node_id: str) -> None:
    _history.pop(node_id, None)
    _last_approved.pop(node_id, None)
