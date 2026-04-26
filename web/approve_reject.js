// ComfyUI-ApproveReject — frontend extension.
// M1 scope: render a modal with a preview image and Approve / Reject buttons,
// post the decision back to the server. No seed bumping, no auto-requeue
// (those land in M2).

import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const AWAITING_EVENT = "approve_reject/awaiting";
const DECISION_ROUTE = "/approve_reject/decision";

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "className") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on") && typeof v === "function") {
      node.addEventListener(k.slice(2).toLowerCase(), v);
    } else {
      node.setAttribute(k, v);
    }
  }
  for (const c of children) {
    if (c) node.appendChild(c);
  }
  return node;
}

class ApproveRejectModal {
  constructor() {
    this.state = "IDLE";
    this.currentNodeId = null;
    this.currentPayload = null;
    // Queue of awaiting payloads that arrived while another gate's modal was
    // open or its decision was being submitted. Drained by _close().
    //
    // This prevents two race conditions when a graph has multiple gate nodes:
    //   1. A second gate's "awaiting" event arrives while the first gate's POST
    //      is in flight. Without queueing, the SECOND _open() would be wiped
    //      out by the FIRST submit's finally _close().
    //   2. Two parallel gates fire "awaiting" simultaneously. Without queueing,
    //      the second _open() would clobber the first one's currentNodeId, and
    //      the user could only approve one of them.
    this.pendingQueue = [];
    this._build();
    this._bindEvents();
  }

  _build() {
    this.elPreview = el("img", {
      className: "ar-preview-img",
      alt: "Pending preview",
    });
    this.elMeta = el("span", { className: "ar-modal-meta" });
    this.btnReject = el("button", {
      className: "ar-btn ar-btn-reject",
      type: "button",
      text: "Reject",
      onClick: () => this._submit("reject"),
    });
    this.btnApprove = el("button", {
      className: "ar-btn ar-btn-approve",
      type: "button",
      text: "Approve",
      onClick: () => this._submit("approve"),
    });

    const header = el("div", { className: "ar-modal-header" }, [
      el("span", { className: "ar-modal-title", text: "Approve / Reject" }),
      this.elMeta,
    ]);
    const previewWrap = el("div", { className: "ar-preview-wrap" }, [this.elPreview]);
    const body = el("div", { className: "ar-modal-body" }, [previewWrap]);
    const footer = el("div", { className: "ar-modal-footer" }, [
      this.btnReject,
      this.btnApprove,
    ]);
    const frame = el(
      "div",
      { className: "ar-modal-frame", role: "dialog", "aria-modal": "true" },
      [header, body, footer],
    );
    const backdrop = el("div", { className: "ar-modal-backdrop" });
    this.root = el("div", { className: "ar-modal-root" }, [backdrop, frame]);
    this.root.style.display = "none";
    document.body.appendChild(this.root);
  }

  _bindEvents() {
    api.addEventListener(AWAITING_EVENT, (event) => {
      const detail = event.detail || {};
      this._enqueue(detail);
    });
    api.addEventListener("execution_interrupted", () => {
      // The whole prompt is being torn down — drop any queued gates too.
      this.pendingQueue.length = 0;
      if (this.state !== "IDLE") {
        this._close();
      }
    });
  }

  _enqueue(payload) {
    if (this.state === "IDLE") {
      this._open(payload);
    } else {
      this.pendingQueue.push(payload);
    }
  }

  _open(payload) {
    this.currentNodeId = payload.node_id;
    this.currentPayload = payload;
    this.state = "AWAITING_DECISION";
    const url = payload.preview && payload.preview.url;
    if (url) {
      this.elPreview.src = url;
    } else {
      this.elPreview.removeAttribute("src");
    }
    this.elMeta.textContent = `node #${payload.node_id} · ${payload.type || "image"}`;
    this.btnApprove.disabled = false;
    this.btnReject.disabled = false;
    this.root.style.display = "block";
  }

  async _submit(action) {
    if (this.state !== "AWAITING_DECISION") return;
    this.state = action === "approve" ? "SUBMITTING_APPROVE" : "SUBMITTING_REJECT";
    this.btnApprove.disabled = true;
    this.btnReject.disabled = true;

    const body = {
      node_id: this.currentNodeId,
      action,
      override_seed: null,
    };

    try {
      const res = await api.fetchApi(DECISION_ROUTE, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        console.error("[ApproveReject] decision POST failed", res.status, await res.text());
      }
    } catch (err) {
      console.error("[ApproveReject] decision POST error", err);
    } finally {
      this._close();
    }
  }

  _close() {
    this.root.style.display = "none";
    this.state = "IDLE";
    this.currentNodeId = null;
    this.currentPayload = null;
    // Drain one queued awaiting payload (if any). The state-machine guard in
    // _enqueue already routed concurrent awaiting events here.
    if (this.pendingQueue.length > 0) {
      const next = this.pendingQueue.shift();
      this._open(next);
    }
  }
}

function injectStylesheet() {
  if (document.querySelector("link[data-ar-modal]")) return;
  const link = el("link", {
    rel: "stylesheet",
    type: "text/css",
    href: new URL("./modal.css", import.meta.url).toString(),
    "data-ar-modal": "1",
  });
  document.head.appendChild(link);
}

app.registerExtension({
  name: "ComfyUI.ApproveReject",
  async setup() {
    injectStylesheet();
    if (!window.__approveRejectModal) {
      window.__approveRejectModal = new ApproveRejectModal();
    }
  },
});
