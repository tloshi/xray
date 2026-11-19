/* Feature X-Ray viewer — pan / zoom for a diagram viewport.
   Zooms only the diagram, never the page. A press that does not move is
   reported as a click, because pointer capture swallows native click events
   on the SVG nodes underneath. */
window.XR = window.XR || {};

(function (XR) {
  "use strict";

  const MIN = 0.15;
  const MAX = 5;
  const CLICK_SLOP = 5;
  /* The first view shows the whole diagram unless that would shrink it below
     WHOLE_MIN; then it shows the beginning at a readable size instead. */
  const WHOLE_MIN = 0.5;
  const READABLE = 0.62;
  const START_MAX = 0.9;

  /**
   * @param {HTMLElement} viewport element containing a .stage
   * @param {{onClick: function(Element, PointerEvent): void, onExpand: function(): void,
   *          coveredRight: function(): number, wheelPans: function(): boolean}} handlers
   *          coveredRight = px hidden by an overlay; wheelPans = may a plain wheel pan the diagram
   */
  XR.panZoom = function (viewport, handlers) {
    const stage = viewport.querySelector(".stage");
    let scale = 1;
    let x = 0;
    let y = 0;

    viewport.insertAdjacentHTML("beforeend",
      `<div class="toolbar">
         <button type="button" data-act="out" title="Zoom out">−</button>
         <span class="zoom-level">100%</span>
         <button type="button" data-act="in" title="Zoom in">+</button>
         <button type="button" data-act="fit">${XR.t("fit")}</button>
         <button type="button" data-act="expand">${XR.t("expand")}</button>
       </div>
       <div class="hint">${XR.t("hint")}</div>`);
    const level = viewport.querySelector(".zoom-level");
    const toolbar = viewport.querySelector(".toolbar");

    const apply = () => {
      stage.style.transform = `translate(${x}px, ${y}px) scale(${scale})`;
      level.textContent = `${Math.round(scale * 100)}%`;
    };
    const zoomAt = (factor, px, py) => {
      const next = Math.min(MAX, Math.max(MIN, scale * factor));
      const ratio = next / scale;
      x = px - (px - x) * ratio;
      y = py - (py - y) * ratio;
      scale = next;
      apply();
    };
    const zoomCenter = (factor) => zoomAt(factor, viewport.clientWidth / 2, viewport.clientHeight / 2);
    const local = (cx, cy) => {
      const r = viewport.getBoundingClientRect();
      return [cx - r.left, cy - r.top];
    };

    /** Frames a rectangle given in unscaled stage coordinates. */
    const frame = (rect, maxScale) => {
      if (!rect || !rect.w || !rect.h || !viewport.clientWidth) return;
      const pad = 36;
      const width = viewport.clientWidth - handlers.coveredRight();
      scale = Math.max(MIN, Math.min(
        (width - pad * 2) / rect.w, (viewport.clientHeight - pad * 2) / rect.h, maxScale));
      x = (width - rect.w * scale) / 2 - rect.x * scale;
      y = (viewport.clientHeight - rect.h * scale) / 2 - rect.y * scale;
      apply();
    };
    const stageRect = (els) => {
      const s = stage.getBoundingClientRect();
      let x0 = Infinity; let y0 = Infinity; let x1 = -Infinity; let y1 = -Infinity;
      els.forEach((el) => {
        const r = el.getBoundingClientRect();
        x0 = Math.min(x0, r.left); y0 = Math.min(y0, r.top);
        x1 = Math.max(x1, r.right); y1 = Math.max(y1, r.bottom);
      });
      if (!isFinite(x0)) return null;
      return { x: (x0 - s.left) / scale, y: (y0 - s.top) / scale, w: (x1 - x0) / scale, h: (y1 - y0) / scale };
    };
    const fit = () => {
      const svg = stage.querySelector("svg");
      if (svg) frame(stageRect([svg]), 1.25);
    };
    /** Unscaled size of the rendered diagram. */
    const natural = () => {
      const svg = stage.querySelector("svg");
      const rect = svg ? stageRect([svg]) : null;
      return rect ? { w: rect.w, h: rect.h } : null;
    };
    /**
     * First view: the whole diagram if it stays readable, otherwise its beginning
     * at a readable size. `anchor` is the element the story starts at (a flow's
     * start node); without one the top-left corner is shown.
     */
    const start = (anchor) => {
      const svg = stage.querySelector("svg");
      const rect = svg ? stageRect([svg]) : null;
      if (!rect || !rect.w || !rect.h || !viewport.clientWidth) return;
      const pad = 28;
      const width = viewport.clientWidth - handlers.coveredRight();
      const height = viewport.clientHeight;
      const fitW = (width - pad * 2) / rect.w;
      const fitH = (height - pad * 2) / rect.h;
      if (Math.min(fitW, fitH) >= WHOLE_MIN) { frame(rect, 1.25); return; }
      const at = anchor ? stageRect([anchor]) : null;
      const next = Math.min(START_MAX, Math.max(READABLE, Math.max(fitW, fitH)));
      /* Along one axis: centre the diagram if it fits, else put the anchor (or
         the leading edge) in view without scrolling past either end. */
      const place = (size, origin, room, wanted) => {
        if (size * next <= room - pad * 2) return (room - size * next) / 2 - origin * next;
        const lead = pad - origin * next;
        const trail = room - pad - (origin + size) * next;
        return Math.max(trail, Math.min(lead, wanted));
      };
      const wantX = at ? width / 2 - (at.x + at.w / 2) * next : pad - rect.x * next;
      const wantY = at ? pad + 24 - at.y * next : pad - rect.y * next;
      scale = next;
      x = place(rect.w, rect.x, width, wantX);
      y = place(rect.h, rect.y, height, wantY);
      apply();
    };
    const focus = (els) => {
      const rect = stageRect(els);
      if (rect) frame({ x: rect.x - 60, y: rect.y - 60, w: rect.w + 120, h: rect.h + 120 }, 1.1);
    };

    viewport.addEventListener("wheel", (e) => {
      const zooming = e.ctrlKey || e.metaKey;
      /* A plain wheel belongs to the page: scrolling past a diagram must not drag it away. */
      if (!zooming && !handlers.wheelPans()) return;
      e.preventDefault();
      viewport.classList.add("touched");
      const unit = e.deltaMode === 1 ? 16 : 1;
      if (zooming) {
        const [px, py] = local(e.clientX, e.clientY);
        zoomAt(Math.exp(-e.deltaY * unit * 0.01), px, py);
      } else {
        x -= e.deltaX * unit;
        y -= e.deltaY * unit;
        apply();
      }
    }, { passive: false });

    let gestureStart = 1;
    viewport.addEventListener("gesturestart", (e) => { e.preventDefault(); gestureStart = scale; });
    viewport.addEventListener("gesturechange", (e) => {
      e.preventDefault();
      const [px, py] = local(e.clientX, e.clientY);
      zoomAt((gestureStart * e.scale) / scale, px, py);
    });
    viewport.addEventListener("gestureend", (e) => e.preventDefault());

    const pointers = new Map();
    let pinch = 0;
    let travel = 0;
    viewport.addEventListener("pointerdown", (e) => {
      if (toolbar.contains(e.target) || e.target.closest(".hl-bar, .walk-bar, .dia-error")) return;
      viewport.setPointerCapture(e.pointerId);
      pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      travel = 0;
      viewport.classList.add("dragging", "touched");
      if (pointers.size === 2) {
        const [a, b] = [...pointers.values()];
        pinch = Math.hypot(a.x - b.x, a.y - b.y);
      }
    });
    viewport.addEventListener("pointermove", (e) => {
      const prev = pointers.get(e.pointerId);
      if (!prev) return;
      const cur = { x: e.clientX, y: e.clientY };
      pointers.set(e.pointerId, cur);
      if (pointers.size === 1) {
        travel += Math.abs(cur.x - prev.x) + Math.abs(cur.y - prev.y);
        x += cur.x - prev.x;
        y += cur.y - prev.y;
        apply();
      } else if (pointers.size === 2) {
        const [a, b] = [...pointers.values()];
        const dist = Math.hypot(a.x - b.x, a.y - b.y);
        const [px, py] = local((a.x + b.x) / 2, (a.y + b.y) / 2);
        if (pinch > 0) zoomAt(dist / pinch, px, py);
        pinch = dist;
        travel = CLICK_SLOP + 1;
      }
    });
    const release = (e) => {
      if (!pointers.has(e.pointerId)) return;
      const wasSingle = pointers.size === 1;
      pointers.delete(e.pointerId);
      pinch = 0;
      if (pointers.size === 0) viewport.classList.remove("dragging");
      if (e.type === "pointerup" && wasSingle && travel <= CLICK_SLOP) {
        const under = document.elementFromPoint(e.clientX, e.clientY);
        if (under && viewport.contains(under)) handlers.onClick(under, e);
      }
    };
    viewport.addEventListener("pointerup", release);
    viewport.addEventListener("pointercancel", release);

    toolbar.addEventListener("click", (e) => {
      const btn = e.target.closest("button");
      const act = btn && btn.dataset.act;
      if (act === "in") zoomCenter(1.25);
      if (act === "out") zoomCenter(1 / 1.25);
      if (act === "fit") fit();
      if (act === "expand") handlers.onExpand(btn);
    });

    return { fit, start, natural, focus, zoom: zoomCenter };
  };
})(window.XR);
