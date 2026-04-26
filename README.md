# ComfyUI-ApproveReject

In-graph **approve/reject gate** for ComfyUI. Halts execution at the gate, shows the candidate output in a modal, and on Reject re-fires the upstream subgraph with a new seed — true reject→regenerate loop, in one workflow, no manual re-queue.

> **Status:** Alpha. v1.0 in active development. M1 (image-only, manual re-queue on reject) shipped; M2 (auto re-queue with seed bump) next.

## Why

Iterating on a Flux/SD image before feeding it into expensive video gen? Today you click *Run* repeatedly until you like the candidate. This node lets you click **Reject** instead — it bumps the configured upstream seed widget and re-fires automatically.

## Install (development)

1. Clone into your ComfyUI custom_nodes folder (or symlink from your dev location).

   On Windows + WSL development (run from WSL — no admin needed):
   ```bash
   /mnt/c/Windows/System32/cmd.exe /c "mklink /D \
     D:\path\to\ComfyUI\custom_nodes\ComfyUI-ApproveReject \
     \\wsl.localhost\Ubuntu\home\you\path\to\ComfyUI-ApproveReject"
   ```
2. Restart ComfyUI.
3. The node `Approve / Reject Gate` shows up under category `approve_reject`.

## Use

Place the gate between any node producing an `IMAGE` (today; LATENT/MASK/VIDEO_FRAMES land in M3) and the consumer downstream.

Example: in a Flux workflow `… → KSampler → VAEDecode → ApproveRejectGate → SaveImage`. Configure the gate's `seed_source_node_id` to your KSampler's node id, and `seed_widget_name` to `seed`. Queue the prompt — modal pops on the rendered image. **Approve** → `SaveImage` runs. **Reject** → the prompt aborts (M1) / the workflow re-fires with a new seed (M2+).

See [`examples/flux2_klein_with_gate.json`](examples/flux2_klein_with_gate.json) for a drop-in.

## License

Apache 2.0 — see [`LICENSE`](LICENSE).
