"""ApproveRejectGate — the single in-graph gate node.

M1 scope: IMAGE only; Approve continues, Reject aborts the current prompt
cleanly via InterruptProcessingException. M2 will wire the frontend re-queue
flow with seed bumping.
"""

from __future__ import annotations

import math
from typing import Any

import comfy.model_management as mm
import nodes as comfy_nodes
from server import PromptServer

from .any_type import ANY
from .decision_holder import holder
from .preview_writer import (
    get_history,
    get_last_approved,
    mark_approved,
    mark_rejected,
    record_pending,
    write_image_preview,
)


_AWAITING_EVENT = "approve_reject/awaiting"


class ApproveRejectGate:
    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "payload": (ANY, {}),
            },
            "optional": {
                "seed_source_node_id": ("INT", {"default": -1, "min": -1, "max": 0xFFFFFFFF}),
                "seed_widget_name": ("STRING", {"default": "seed"}),
                "history_size": ("INT", {"default": 5, "min": 1, "max": 50}),
                "timeout_s": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 86400.0, "step": 1.0}),
                "on_timeout": (["keep_waiting", "approve", "reject"], {"default": "keep_waiting"}),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
            },
        }

    RETURN_TYPES = (ANY,)
    RETURN_NAMES = ("payload",)
    FUNCTION = "gate"
    CATEGORY = "approve_reject"
    OUTPUT_NODE = False

    @classmethod
    def IS_CHANGED(cls, *args: Any, **kwargs: Any) -> float:
        return math.nan

    async def gate(
        self,
        payload: Any,
        seed_source_node_id: int = -1,
        seed_widget_name: str = "seed",
        history_size: int = 5,
        timeout_s: float = 0.0,
        on_timeout: str = "keep_waiting",
        unique_id: str | int | None = None,
    ) -> tuple[Any]:
        node_id = str(unique_id) if unique_id is not None else "unknown"

        # M1: only IMAGE preview is supported. If payload doesn't look like a
        # batched image tensor, pass-through with no gate (silent for now;
        # M3 will route MASK / LATENT / VIDEO_FRAMES through the right preview).
        is_image_tensor = (
            hasattr(payload, "shape")
            and hasattr(payload, "ndim")
            and payload.ndim == 4
            and payload.shape[-1] in (1, 3, 4)
        )
        if not is_image_tensor:
            return (payload,)

        preview_entry = await write_image_preview(node_id, payload)
        record_pending(node_id, preview_entry, history_size=history_size)

        await holder.open(node_id)
        PromptServer.instance.send_sync(
            _AWAITING_EVENT,
            {
                "node_id": node_id,
                "type": "image",
                "preview": preview_entry,
                "history": get_history(node_id, limit=history_size),
                "last_approved": get_last_approved(node_id),
                "seed_source_node_id": seed_source_node_id,
                "seed_widget_name": seed_widget_name,
                "timeout_s": timeout_s,
                "on_timeout": on_timeout,
            },
        )

        wait_timeout = timeout_s if timeout_s > 0 else None
        decision = await holder.wait(
            node_id,
            timeout_s=wait_timeout,
            interrupt_check_fn=mm.processing_interrupted,
            poll_interval_s=0.25,
        )

        action = decision.get("action", "cancel")

        if action == "timeout":
            if on_timeout == "approve":
                action = "approve"
            elif on_timeout == "reject":
                action = "reject"
            else:
                # keep_waiting: re-enter the wait once. Bounded to one extra
                # cycle so a wedged tab can't hold the queue forever.
                decision = await holder.wait(
                    node_id,
                    timeout_s=None,
                    interrupt_check_fn=mm.processing_interrupted,
                    poll_interval_s=0.25,
                )
                action = decision.get("action", "cancel")

        if action == "approve":
            mark_approved(node_id, preview_entry)
            return (payload,)

        # reject / cancel — clean abort
        mark_rejected(node_id, preview_entry)
        comfy_nodes.interrupt_processing(True)
        raise mm.InterruptProcessingException()


NODE_CLASS_MAPPINGS = {
    "ApproveRejectGate": ApproveRejectGate,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ApproveRejectGate": "Approve / Reject Gate",
}
