"""ComfyUI-ApproveReject — entry point.

Registers the gate node and the /approve_reject/* HTTP routes against ComfyUI's
PromptServer. WEB_DIRECTORY exposes web/ to the frontend so the JS extension
auto-loads on page boot.

The runtime imports below are guarded so the package remains importable
outside ComfyUI (for linting, packaging, and unit tests).
"""

WEB_DIRECTORY = "./web"
NODE_CLASS_MAPPINGS: dict = {}
NODE_DISPLAY_NAME_MAPPINGS: dict = {}

try:
    from server import PromptServer  # provided by ComfyUI runtime

    from .src.nodes import (
        NODE_CLASS_MAPPINGS as _NODE_CLASS_MAPPINGS,
        NODE_DISPLAY_NAME_MAPPINGS as _NODE_DISPLAY_NAME_MAPPINGS,
    )
    from .src.server_routes import register_routes

    NODE_CLASS_MAPPINGS = _NODE_CLASS_MAPPINGS
    NODE_DISPLAY_NAME_MAPPINGS = _NODE_DISPLAY_NAME_MAPPINGS
    register_routes(PromptServer.instance.routes)
except ImportError:
    # Outside ComfyUI: skip ComfyUI-only wiring. Tests and packaging tools
    # can still import the package; node definitions are simply not present.
    pass


__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
]
