# Changelog

All notable changes to ComfyUI-ApproveReject will be documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [SemVer](https://semver.org/).

## [0.1.1](https://github.com/modbender/ComfyUI-ApproveReject/compare/v0.1.0...v0.1.1) (2026-04-28)


### CI

* add release-please + pytest workflows ([483bdae](https://github.com/modbender/ComfyUI-ApproveReject/commit/483bdae57696c63c7300d37ddd1d77dff93d6fe6))

## [0.1.0] — 2026-04-25

### Added
- Initial M1: `ApproveRejectGate` node — pauses execution mid-prompt, sends a websocket event to the frontend, awaits an Approve/Reject decision posted to `POST /approve_reject/decision`.
- Frontend modal extension that listens for `approve_reject/awaiting`, renders the candidate IMAGE preview, and posts the user's decision back to the server.
- Async `DecisionHolder` primitive (per-node-id `asyncio.Event`) with cancellation propagation via `comfy.model_management.processing_interrupted()`.
- IMAGE preview rendering via PIL; previews stored under `temp/approve_reject/<node_id>/`.
- Per-node history tracking (LRU-capped) with approve/reject status flags.
- Apache 2.0 license, pyproject metadata, ComfyUI-Manager `[tool.comfy]` registry block.

### Fixed
- **Multi-gate race in modal singleton.** When two gate nodes were used in the same workflow, the second gate's "awaiting" event could arrive while the first gate's POST response was still in flight; `_close()` in the POST's `finally` block then clobbered the freshly-opened modal. Replaced with a queue: `_enqueue` defers if a decision is in-flight; `_close` drains one queued payload after resetting state.
