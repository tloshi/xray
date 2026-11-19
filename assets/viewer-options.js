/* X-Ray viewer — per-diagram options: focus modes, layout direction,
   legend filtering, the step-by-step walkthrough, image export and keyboard
   shortcuts. Everything here drives the highlight machinery in viewer-app.js
   through XR.app, so there is one code path for "show these nodes". */
window.XR = window.XR || {};

(function (XR) {
  "use strict";

  const { esc, t } = XR;
  const DIRECTED = ["flow", "components", "state"];
  const EXPORT_SCALE = 2;

  const nodesOf = (d) => (d.kind === "flow" ? d.nodes : d.kind === "components" ? d.components : d.states || []);
  const target = (d, item) => `${d.id}:${item.id}`;

  /* ---------- focus modes ---------- */

  function focusTargets(d, mode) {
    if (d.kind !== "flow") return [];
    const byId = {};
    d.nodes.forEach((n) => { byId[n.id] = n; });
    if (mode === "main") {
      const on = new Set(d.nodes.filter((n) => n.type === "start").map((n) => n.id));
      d.edges.filter((e) => e.kind === "main").forEach((e) => { on.add(e.from); on.add(e.to); });
      return [...on].map((id) => target(d, byId[id]));
    }
    if (mode === "problems") {
      const on = new Set(d.nodes.filter((n) => n.type === "error").map((n) => n.id));
      d.edges.filter((e) => on.has(e.to)).forEach((e) => on.add(e.from));
      return [...on].filter((id) => byId[id]).map((id) => target(d, byId[id]));
    }
    if (mode === "decisions") return d.nodes.filter((n) => n.type === "decision").map((n) => target(d, n));
    return [];
  }

  function availableModes(d) {
    if (d.kind !== "flow") return [];
    const modes = ["all"];
    if (d.edges.some((e) => e.kind === "main")) modes.push("main");
    if (d.nodes.some((n) => n.type === "error")) modes.push("problems");
    if (d.nodes.some((n) => n.type === "decision")) modes.push("decisions");
    return modes.length > 1 ? modes : [];
  }

  function setFocus(panel, mode) {
    stopWalk(panel);
    if (mode === "all") { XR.app.clearHighlight(); return; }
    XR.app.applyHighlight(focusTargets(panel.d, mode), t("focus_" + mode), false);
    markFocus(panel, mode);
  }

  function markFocus(panel, mode) {
    panel.el.querySelectorAll("[data-focus]").forEach((b) =>
      b.setAttribute("aria-pressed", String(b.dataset.focus === mode)));
  }

  /* ---------- legend filter ---------- */

  function legendTargets(d, pick) {
    const [kind, value] = pick.split(":");
    return nodesOf(d).filter((n) =>
      (kind === "type" && n.type === value) || (kind === "layer" && n.layer === value) ||
      (kind === "inferred" && n.confidence === "inferred")).map((n) => target(d, n));
  }

  /* ---------- walkthrough ---------- */

  /** Reading order: follow edges from each start, main path first, each node once. */
  function walkOrder(d) {
    const order = [];
    const seen = new Set();
    const out = {};
    d.edges.forEach((e) => { (out[e.from] = out[e.from] || []).push(e); });
    const visit = (id) => {
      if (seen.has(id)) return;
      seen.add(id);
      order.push(id);
      const next = (out[id] || []).slice().sort((a, b) => (b.kind === "main") - (a.kind === "main"));
      next.forEach((e) => visit(e.to));
    };
    d.nodes.filter((n) => n.type === "start").forEach((n) => visit(n.id));
    d.nodes.forEach((n) => visit(n.id));
    return order.map((id) => d.nodes.find((n) => n.id === id)).filter(Boolean);
  }

  function showStep(panel) {
    const w = panel.walk;
    const node = w.order[w.i];
    XR.app.applyHighlight([target(panel.d, node)], node.label, false);
    XR.app.openInspector(panel, node);
    panel.walkBar.hidden = false;
    panel.viewport.classList.add("walking");
    panel.walkBar.querySelector("span").textContent = t("walk_step", { i: w.i + 1, n: w.order.length });
    panel.walkBar.querySelector("[data-prev]").disabled = w.i === 0;
    panel.walkBar.querySelector("[data-next]").disabled = w.i === w.order.length - 1;
  }

  function startWalk(panel) {
    const order = walkOrder(panel.d);
    if (!order.length) return;
    panel.walk = { order, i: 0 };
    showStep(panel);
  }

  function stepWalk(panel, delta) {
    if (!panel.walk) return;
    const i = panel.walk.i + delta;
    if (i < 0 || i >= panel.walk.order.length) return;
    panel.walk = { order: panel.walk.order, i };
    showStep(panel);
  }

  function stopWalk(panel) {
    if (!panel || !panel.walk) return;
    panel.walk = null;
    panel.walkBar.hidden = true;
    panel.viewport.classList.remove("walking");
  }

  /* ---------- export ---------- */

  function download(blob, name) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  }

  function fileName(panel, ext) {
    const slug = (s) => String(s || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    return [slug(XR.meta.module), slug(XR.meta.title), slug(panel.d.id)].filter(Boolean).join("-") + "." + ext;
  }

  /** Renders the diagram again with plain SVG text labels, so the file opens anywhere. */
  async function exportSvg(panel) {
    const built = XR.buildDiagram(XR.options.diagramFor(panel), XR.ui.lens, { plain: true });
    const init = '%%{init: {"htmlLabels": false, "flowchart": {"htmlLabels": false}} }%%\n';
    XR.ui.seq += 1;
    const id = `xr-export-${XR.ui.seq}`;
    const out = await window.mermaid.render(id, init + built.text);
    const doc = new DOMParser().parseFromString(out.svg, "image/svg+xml");
    const svg = doc.documentElement;
    const box = (svg.getAttribute("viewBox") || "").split(/\s+/).map(Number);
    const width = Math.ceil(box[2] || 1200);
    const height = Math.ceil(box[3] || 800);
    svg.setAttribute("width", String(width));
    svg.setAttribute("height", String(height));
    svg.removeAttribute("style");
    svg.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    return { text: new XMLSerializer().serializeToString(svg), width, height };
  }

  function rasterize(svg) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        try {
          const canvas = document.createElement("canvas");
          canvas.width = svg.width * EXPORT_SCALE;
          canvas.height = svg.height * EXPORT_SCALE;
          const ctx = canvas.getContext("2d");
          ctx.fillStyle = XR.palette().surface || "#ffffff";
          ctx.fillRect(0, 0, canvas.width, canvas.height);
          ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
          canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("empty image"))), "image/png");
        } catch (err) { reject(err); }
      };
      img.onerror = () => reject(new Error("image could not be decoded"));
      img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg.text);
    });
  }

  async function exportDiagram(panel, format) {
    if (!window.mermaid) return;
    try {
      const svg = await exportSvg(panel);
      if (format === "svg") {
        download(new Blob([svg.text], { type: "image/svg+xml" }), fileName(panel, "svg"));
      } else {
        try {
          download(await rasterize(svg), fileName(panel, "png"));
        } catch (err) {
          download(new Blob([svg.text], { type: "image/svg+xml" }), fileName(panel, "svg"));
          XR.toast(t("export_fallback"));
          return;
        }
      }
      XR.toast(t("exported"));
    } catch (err) {
      XR.toast(t("export_failed"));
    }
  }

  /* ---------- wiring ---------- */

  function controlsHtml(d) {
    const modes = availableModes(d);
    const focus = modes.length
      ? `<div class="seg sm" role="group">${modes.map((m) =>
        `<button type="button" data-focus="${m}" aria-pressed="${m === "all"}">${esc(t("focus_" + m))}</button>`).join("")}</div>`
      : "";
    const dir = DIRECTED.includes(d.kind)
      ? `<button type="button" class="icon-btn sm" data-dir title="${esc(t("layout_title"))}">⇅ ${esc(t("layout"))}</button>` : "";
    const walk = d.kind === "flow"
      ? `<button type="button" class="icon-btn sm" data-walk title="${esc(t("walk_title"))}">▶ ${esc(t("walk"))}</button>` : "";
    return `<div class="opts">${focus}${dir}${walk}` +
      `<button type="button" class="icon-btn sm" data-export="png" title="${esc(t("export_title"))}">PNG</button>` +
      `<button type="button" class="icon-btn sm" data-export="svg" title="${esc(t("export_title"))}">SVG</button></div>`;
  }

  XR.options = {
    /** The diagram data with this panel's view options applied. */
    diagramFor(panel) {
      return panel.direction ? { ...panel.d, direction: panel.direction } : panel.d;
    },

    decorate(panel) {
      panel.el.querySelector(".dia-head").insertAdjacentHTML("beforeend", controlsHtml(panel.d));
      panel.viewport.insertAdjacentHTML("beforeend",
        `<div class="walk-bar" hidden><button type="button" data-prev aria-label="${esc(t("prev"))}">◀</button><span></span>` +
        `<button type="button" data-next aria-label="${esc(t("next"))}">▶</button>` +
        `<button type="button" data-stop aria-label="${esc(t("close"))}">✕</button></div>`);
      panel.walkBar = panel.viewport.querySelector(".walk-bar");
      panel.walk = null;

      panel.el.addEventListener("click", (e) => {
        const focus = e.target.closest("[data-focus]");
        if (focus) { setFocus(panel, focus.dataset.focus); return; }
        if (e.target.closest("[data-dir]")) {
          const current = panel.direction || panel.d.direction || (panel.d.kind === "state" ? "LR" : "TB");
          panel.direction = current === "TB" ? "LR" : "TB";
          XR.app.renderDiagrams();
          return;
        }
        if (e.target.closest("[data-walk]")) { startWalk(panel); return; }
        const exp = e.target.closest("[data-export]");
        if (exp) { exportDiagram(panel, exp.dataset.export); return; }
        if (e.target.closest("[data-prev]")) { stepWalk(panel, -1); return; }
        if (e.target.closest("[data-next]")) { stepWalk(panel, 1); return; }
        if (e.target.closest("[data-stop]")) { stopWalk(panel); XR.app.clearHighlight(); return; }
        const chip = e.target.closest("[data-pick]");
        if (chip) {
          stopWalk(panel);
          XR.app.applyHighlight(legendTargets(panel.d, chip.dataset.pick), chip.textContent, false);
        }
      });
    },

    /** Called whenever highlighting is cleared, to reset the focus buttons. */
    syncCleared() {
      XR.ui.panels.forEach((p) => markFocus(p, "all"));
    },

    stopWalk,

    wireKeys() {
      document.addEventListener("keydown", (e) => {
        const typing = /^(input|textarea|select)$/i.test((e.target && e.target.tagName) || "");
        const panel = XR.ui.panels[XR.ui.active];
        if (e.key === "/" && !typing) { e.preventDefault(); document.getElementById("search").focus(); return; }
        if (typing || !panel || e.metaKey || e.ctrlKey || e.altKey) return;
        if (e.key === "+" || e.key === "=") panel.pz.zoom(1.25);
        else if (e.key === "-") panel.pz.zoom(1 / 1.25);
        else if (e.key === "0") panel.pz.fit();
        else if (e.key === "ArrowRight" && panel.walk) { e.preventDefault(); stepWalk(panel, 1); }
        else if (e.key === "ArrowLeft" && panel.walk) { e.preventDefault(); stepWalk(panel, -1); }
        else if (e.key === "Escape" && panel.walk) { stopWalk(panel); XR.app.clearHighlight(); }
      });
    }
  };
})(window.XR);
