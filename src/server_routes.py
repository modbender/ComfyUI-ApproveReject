"""HTTP routes for the approve/reject gate.

POST /approve_reject/decision    Submit an approve/reject decision for an open gate.
GET  /approve_reject/state/<id>  Read the current pending state (for client reconnect).

Routes are registered against `PromptServer.instance.routes` in `__init__.py`.
"""

from __future__ import annotations

from aiohttp import web

from .decision_holder import holder


def register_routes(routes: web.RouteTableDef) -> None:
    @routes.post("/approve_reject/decision")
    async def post_decision(request: web.Request) -> web.Response:
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "invalid json"}, status=400)

        node_id = body.get("node_id")
        action = body.get("action")
        if not node_id or action not in ("approve", "reject", "cancel"):
            return web.json_response(
                {"ok": False, "error": "node_id and action in {approve,reject,cancel} required"},
                status=400,
            )

        decision = {"action": action}
        override = body.get("override_seed")
        if override is not None:
            try:
                decision["override_seed"] = int(override)
            except (TypeError, ValueError):
                return web.json_response(
                    {"ok": False, "error": "override_seed must be int or null"},
                    status=400,
                )

        submitted = await holder.submit(str(node_id), decision)
        if not submitted:
            return web.json_response(
                {"ok": False, "error": "no open decision slot for node_id"},
                status=409,
            )
        return web.json_response({"ok": True})

    @routes.get("/approve_reject/state/{node_id}")
    async def get_state(request: web.Request) -> web.Response:
        node_id = request.match_info["node_id"]
        async with holder._lock:  # noqa: SLF001 — internal read for diagnostics
            is_open = node_id in holder._events
            has_decision = node_id in holder._decisions
        return web.json_response(
            {"node_id": node_id, "open": is_open, "has_decision": has_decision}
        )
