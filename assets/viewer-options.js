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
  /* Auto-play: how long a step stays on screen at normal speed, in milliseconds. */
  const PLAY_BASE_MS = 2600;
  const PLAY_MS_PER_CHAR = 22;
  const PLAY_MAX_MS = 7000;
  const PLAY_SPEEDS = [1, 2, 0.5];
  const GLIDE_MS = 480;

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

  /** The arrow that leads into a step from one already shown, so the eye can follow the move. */
  function incomingEdge(panel, w) {
    const node = w.order[w.i];
    const shown = w.order.slice(0, w.i).map((n) => n.id);
    const into = panel.d.edges.filter((e) => e.to === node.id && shown.includes(e.from));
    if (!into.length) return null;
    const previous = shown[shown.length - 1];
    const edge = into.find((e) => e.from === previous) ||
      into.sort((a, b) => shown.indexOf(b.from) - shown.indexOf(a.from))[0];
    const svg = panel.stage.querySelector("svg");
    if (!svg) return null;
    /* Mermaid names an arrow L_<from>_<to>_<number>; the number differs between its versions. */
    const stem = `L_${XR.nid(edge.from)}_${XR.nid(edge.to)}_`;
    const named = new RegExp(`(^|-)${stem}\\d+$`);
    return [...svg.querySelectorAll(`path[id*="${stem}"]`)].find((p) => named.test(p.id)) || null;
  }

  function markEdge(panel) {
    panel.stage.querySelectorAll(".xr-edge-on").forEach((el) => el.classList.remove("xr-edge-on"));
    const edge = panel.walk ? incomingEdge(panel, panel.walk) : null;
    if (edge) edge.classList.add("xr-edge-on");
  }

  const stepMs = (w) => Math.min(PLAY_MAX_MS, PLAY_BASE_MS + String(w.order[w.i].what || "").length * PLAY_MS_PER_CHAR) / w.speed;

  /** While playing, waits for the current step's reading time and then moves on; stops at the last step. */
  function schedule(panel) {
    clearTimeout(panel.walkTimer);
    const w = panel.walk;
    const meter = panel.walkBar.querySelector(".walk-meter");
    meter.classList.remove("run");
    if (!w || !w.playing) return;
    const ms = stepMs(w);
    meter.style.animationDuration = `${ms}ms`;
    void meter.offsetWidth; /* restart the CSS animation */
    meter.classList.add("run");
    panel.walkTimer = setTimeout(() => {
      if (!panel.walk || !panel.walk.playing) return;
      if (panel.walk.i >= panel.walk.order.length - 1) setPlaying(panel, false);
      else goTo(panel, panel.walk.i + 1);
    }, ms);
  }

  function showStep(panel) {
    const w = panel.walk;
    const node = w.order[w.i];
    const stage = panel.stage;
    /* Frame the step with no transition running, so the geometry that is measured is the settled one
       even when steps follow each other quickly; then replay the move from the old view as a glide. */
    clearTimeout(panel.glideTimer);
    panel.viewport.classList.remove("gliding");
    panel.viewport.classList.add("walking");
    const from = stage.style.transform;
    XR.app.applyHighlight([target(panel.d, node)], node.label, false);
    XR.app.openInspector(panel, node);
    const to = stage.style.transform;
    if (from && from !== to) {
      stage.style.transform = from;
      void stage.offsetWidth;
      panel.viewport.classList.add("gliding");
      stage.style.transform = to;
      panel.glideTimer = setTimeout(() => panel.viewport.classList.remove("gliding"), GLIDE_MS);
    }
    markEdge(panel);
    refreshBar(panel);
  }

  /** The step counter and the buttons; no effect on the diagram, so it is safe while the reader is panning. */
  function refreshBar(panel) {
    const w = panel.walk;
    const bar = panel.walkBar;
    bar.hidden = false;
    bar.querySelector("span").textContent = t("walk_step", { i: w.i + 1, n: w.order.length });
    bar.querySelector("[data-prev]").disabled = w.i === 0;
    bar.querySelector("[data-next]").disabled = w.i === w.order.length - 1;
    const play = bar.querySelector("[data-play]");
    play.textContent = w.playing ? "❚❚" : "▶";
    play.setAttribute("aria-label", t(w.playing ? "pause" : "play"));
    play.title = t(w.playing ? "pause" : "play_title");
    play.setAttribute("aria-pressed", String(w.playing));
    bar.querySelector("[data-speed]").textContent = `${w.speed}×`;
  }

  function goTo(panel, i) {
    panel.walk = { ...panel.walk, i };
    showStep(panel);
    schedule(panel);
  }

  function startWalk(panel) {
    const order = walkOrder(panel.d);
    if (!order.length) return;
    panel.walk = { order, i: 0, playing: false, speed: panel.walkSpeed || PLAY_SPEEDS[0] };
    showStep(panel);
  }

  /** A step taken by hand; it pauses auto-play, so the reader keeps control. */
  function stepWalk(panel, delta) {
    if (!panel.walk) return;
    const i = panel.walk.i + delta;
    if (i < 0 || i >= panel.walk.order.length) return;
    panel.walk = { ...panel.walk, playing: false };
    goTo(panel, i);
  }

  function setPlaying(panel, on) {
    if (!panel.walk) return;
    const atEnd = panel.walk.i >= panel.walk.order.length - 1;
    panel.walk = { ...panel.walk, playing: on };
    if (on && atEnd) { goTo(panel, 0); return; }
    refreshBar(panel);
    schedule(panel);
  }

  function nextSpeed(panel) {
    if (!panel.walk) return;
    const speed = PLAY_SPEEDS[(PLAY_SPEEDS.indexOf(panel.walk.speed) + 1) % PLAY_SPEEDS.length];
    panel.walkSpeed = speed;
    panel.walk = { ...panel.walk, speed };
    refreshBar(panel);
    schedule(panel);
  }

  function stopWalk(panel) {
    if (!panel || !panel.walk) return;
    clearTimeout(panel.walkTimer);
    clearTimeout(panel.glideTimer);
    panel.walk = null;
    markEdge(panel);
    panel.walkBar.hidden = true;
    panel.walkBar.querySelector(".walk-meter").classList.remove("run");
    panel.viewport.classList.remove("walking", "gliding");
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
        `<div class="walk-bar" hidden><button type="button" data-prev aria-label="${esc(t("prev"))}">←</button><span></span>` +
        `<button type="button" data-next aria-label="${esc(t("next"))}">→</button><i class="walk-sep"></i>` +
        `<button type="button" data-play aria-pressed="false"></button>` +
        `<button type="button" class="wide" data-speed title="${esc(t("speed"))}" aria-label="${esc(t("speed"))}"></button>` +
        `<button type="button" data-stop aria-label="${esc(t("close"))}">✕</button><i class="walk-meter"></i></div>`);
      panel.walkBar = panel.viewport.querySelector(".walk-bar");
      panel.walk = null;
      /* Touching the diagram itself means the reader wants to look around: pause. */
      panel.viewport.addEventListener("pointerdown", (e) => {
        if (panel.walk && panel.walk.playing && !e.target.closest(".walk-bar")) setPlaying(panel, false);
      });

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
        if (e.target.closest("[data-play]")) { setPlaying(panel, !panel.walk.playing); return; }
        if (e.target.closest("[data-speed]")) { nextSpeed(panel); return; }
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

    /** Called after the diagrams were drawn again (lens, theme, layout): the arrow mark must be put back. */
    afterRender() {
      XR.ui.panels.forEach((p) => { if (p.walk) markEdge(p); });
    },

    wireKeys() {
      /* A hidden page should not keep playing to nobody. */
      document.addEventListener("visibilitychange", () => {
        if (document.hidden) XR.ui.panels.forEach((p) => { if (p.walk && p.walk.playing) setPlaying(p, false); });
      });
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
        else if (e.key === " " && panel.walk && !(e.target.closest && e.target.closest("button, a"))) { e.preventDefault(); setPlaying(panel, !panel.walk.playing); }
        else if (e.key === "Escape" && panel.walk) { stopWalk(panel); XR.app.clearHighlight(); }
      });
    }
  };
})(window.XR);
