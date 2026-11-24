/* X-Ray viewer — the interactive part: diagram tabs, rendering,
   the step inspector, "show on diagram" highlighting, search, lens and theme. */
window.XR = window.XR || {};

(function (XR) {
  "use strict";

  const { esc, rich, paras, t } = XR;
  const D = XR.DATA;
  const diagrams = D.diagrams || [];
  const root = document.documentElement;
  const ui = { lens: "business", active: 0, panels: [], seq: 0, highlight: null };
  XR.ui = ui;

  /* ---------- panels ---------- */

  function buildPanels() {
    const host = document.getElementById("diagrams");
    if (!diagrams.length) { host.hidden = true; return; }
    const tabs = diagrams.map((d, i) =>
      `<button type="button" role="tab" data-tab="${i}" aria-selected="false">${esc(d.title || d.id)}` +
      `<span class="kind">${esc(t("k_" + d.kind))}</span></button>`).join("");
    const panels = diagrams.map((d, i) =>
      `<div class="dia-panel" data-panel="${i}" hidden>
         <h3 class="print-title">${esc(d.title || d.id)}</h3>
         <div class="dia-head"><span class="dsub">${rich(d.subtitle || "")}</span></div>
         <div class="legend"></div>
         <div class="diagram"><div class="stage"></div>
           <div class="hl-bar" hidden><span></span><button type="button" data-clear>${esc(t("clear"))} ✕</button></div>
         </div>
         <div class="dia-extra"></div>
       </div>`).join("");
    host.innerHTML = `<h2>${esc(t("diagrams"))}</h2><div class="tabs" role="tablist">${tabs}</div>${panels}`;

    ui.panels = diagrams.map((d, i) => {
      const el = host.querySelector(`[data-panel="${i}"]`);
      const viewport = el.querySelector(".diagram");
      const panel = {
        d, el, viewport, stage: el.querySelector(".stage"), hl: el.querySelector(".hl-bar"),
        legend: el.querySelector(".legend"), extra: el.querySelector(".dia-extra"), fitted: false, map: {}
      };
      panel.pz = XR.panZoom(viewport, {
        onClick: (under) => onDiagramClick(panel, under),
        coveredRight: () => coveredByInspector(viewport),
        wheelPans: () => host.classList.contains("expanded"),
        onExpand: (btn) => {
          const on = host.classList.toggle("expanded");
          host.querySelectorAll('[data-act="expand"]').forEach((b) => { b.textContent = t(on ? "collapse" : "expand"); });
          sizeViewport(panel);
          panel.pz.start(startNode(panel));
          if (btn) btn.blur();
        }
      });
      XR.options.decorate(panel);
      return panel;
    });
    host.querySelector(".tabs").addEventListener("click", (e) => {
      const b = e.target.closest("[data-tab]");
      if (b) activate(Number(b.dataset.tab));
    });
    host.addEventListener("click", (e) => {
      if (!e.target.closest("[data-clear]")) return;
      ui.panels.forEach((p) => XR.options.stopWalk(p));
      clearHighlight();
    });
  }

  /** How much of a viewport's right side the open inspector hides. */
  function coveredByInspector(viewport) {
    const insp = document.getElementById("inspector");
    if (!insp.classList.contains("open")) return 0;
    const v = viewport.getBoundingClientRect();
    const covered = v.right - (window.innerWidth - insp.offsetWidth);
    return covered > 0 && covered < v.width * 0.6 ? covered : 0;
  }

  function activate(i) {
    ui.active = i;
    ui.panels.forEach((p, k) => { p.el.hidden = k !== i; });
    document.querySelectorAll("[data-tab]").forEach((b) =>
      b.setAttribute("aria-selected", String(Number(b.dataset.tab) === i)));
    const panel = ui.panels[i];
    if (panel && !panel.fitted && panel.stage.querySelector("svg")) {
      sizeViewport(panel);
      panel.pz.start(startNode(panel));
      panel.fitted = true;
    }
  }

  /** The node a flow begins at, so the first view opens on the start of the story. */
  function startNode(panel) {
    const key = Object.keys(panel.map).find((k) => panel.map[k].type === "start");
    return key ? panel.stage.querySelector(`g.xr-node[data-key="${key}"]`) : null;
  }

  /** A short diagram gets a short canvas instead of floating in a tall empty one. */
  function sizeViewport(panel) {
    const expanded = document.getElementById("diagrams").classList.contains("expanded");
    const size = panel.pz.natural();
    const wanted = size ? Math.ceil(size.h) + 110 : 0;
    const roomy = window.innerHeight * 0.72;
    panel.viewport.style.height = !expanded && wanted && wanted < roomy ? `${Math.max(300, wanted)}px` : "";
  }

  /* ---------- rendering ---------- */

  function legendHtml(d) {
    return XR.legend(d).map((x) =>
      `<button type="button" class="chip fam-${x.family}${x.dashed ? " dashed" : ""}" data-pick="${esc(x.pick)}">${esc(x.label)}</button>`).join("");
  }

  function stepTable(panel, rows) {
    const body = rows.map((r, k) => (r.type === "group"
      ? `<tr class="grp"><td colspan="4">${esc(r.text)}</td></tr>`
      : `<tr class="clickable" data-step="${k}"><td class="num">${r.n}</td><td>${esc(r.from)} → ${esc(r.to)}</td>` +
        `<td>${rich(r.step.label)}${r.step.what ? `<div style="color:var(--ink-3);font-size:12.5px">${rich(r.step.what)}</div>` : ""}</td>` +
        `<td class="dev-only">${r.step.tech ? `<span class="mono">${esc(r.step.tech)}</span><br>` : ""}${XR.refsInline(r.step.refs)}</td></tr>`
    )).join("");
    panel.extra.innerHTML = `<h3 style="margin:18px 0 10px;font-size:15px">${esc(t("steps"))}</h3>` +
      `<div class="tbl-wrap"><table><thead><tr><th>#</th><th>${esc(t("st_from"))}</th><th>${esc(t("st_what"))}</th>` +
      `<th class="dev-only">${esc(t("code"))}</th></tr></thead><tbody>${body}</tbody></table></div>`;
    panel.extra.onclick = (e) => {
      const tr = e.target.closest("[data-step]");
      if (tr && !e.target.closest("[data-copy]")) openInspector(panel, rows[Number(tr.dataset.step)].step, "process");
    };
  }

  function bindNodes(panel) {
    const map = XR.clickables(panel.d);
    panel.map = map;
    let bound = 0;
    panel.stage.querySelectorAll("g.node").forEach((g) => {
      const m = /(?:flowchart|state)-(.+)-\d+$/.exec(g.id || "");
      const key = m && map[m[1]] ? m[1] : null;
      if (!key) return;
      g.classList.add("xr-node");
      g.dataset.key = key;
      bound += 1;
    });
    return { bound, expected: Object.keys(map).length };
  }

  function showError(panel, message, source) {
    panel.stage.innerHTML = "";
    const old = panel.viewport.querySelector(".dia-error");
    if (old) old.remove();
    panel.viewport.insertAdjacentHTML("afterbegin",
      `<div class="dia-error"><strong>${esc(t("render_error"))}</strong><div>${esc(message)}</div><pre>${esc(source)}</pre></div>`);
  }

  async function renderDiagrams() {
    const errors = [];
    let bound = 0;
    let expected = 0;
    if (!window.mermaid) {
      ui.panels.forEach((p) => showError(p, "Mermaid library did not load (offline or blocked CDN?).", ""));
      report(diagrams.length ? ["mermaid library missing"] : [], 0, 0);
      return;
    }
    window.mermaid.initialize(XR.mermaidConfig());
    for (const panel of ui.panels) {
      const built = XR.buildDiagram(XR.options.diagramFor(panel), ui.lens);
      ui.seq += 1;
      const id = `xr-svg-${ui.seq}`;
      const stale = panel.viewport.querySelector(".dia-error");
      if (stale) stale.remove();
      try {
        const out = await window.mermaid.render(id, built.text);
        panel.stage.innerHTML = out.svg;
        const b = bindNodes(panel);
        bound += b.bound;
        expected += b.expected;
      } catch (err) {
        const leftover = document.getElementById("d" + id);
        if (leftover) leftover.remove();
        errors.push(`${panel.d.id}: ${err && err.message ? err.message : err}`);
        showError(panel, err && err.message ? err.message : String(err), built.text);
      }
      panel.legend.innerHTML = legendHtml(panel.d);
      if (built.rows) stepTable(panel, built.rows);
      panel.fitted = false;
    }
    activate(ui.active);
    if (ui.highlight) applyHighlight(ui.highlight.targets, ui.highlight.title, false);
    XR.options.afterRender();
    report(errors, bound, expected);
  }

  /** Machine-readable render result, read by `xray.py render-check`. */
  function report(errors, bound, expected) {
    const all = errors.slice();
    if (bound !== expected) all.push(`only ${bound} of ${expected} diagram nodes are clickable`);
    root.dataset.xrayBound = `${bound}/${expected}`;
    root.dataset.xrayErrors = all.join(" | ");
    root.dataset.xrayStatus = all.length ? "error" : "ok";
  }

  /* ---------- inspector ---------- */

  function ticketText(panel, item) {
    const lines = [`[X-Ray] ${XR.meta.title} (${XR.meta.module || ""}) › ${panel.d.title || panel.d.id} › "${item.label}"`];
    if (item.what) lines.push(item.what);
    (item.refs || []).slice(0, 4).map(XR.normRef).forEach((r) =>
      lines.push(`Code: ${XR.refFull(r)}${r.symbol ? ` (${r.symbol})` : ""}`));
    if (XR.build.commit) lines.push(`X-Ray commit: ${XR.build.commit}`);
    return lines.join("\n");
  }

  function openInspector(panel, item, fallbackType) {
    const type = item.type || fallbackType;
    const family = XR.TYPE_FAMILY[type] || XR.LAYER_FAMILY[item.layer] || "slate";
    const typeLabel = item.type ? t("t_" + item.type) : (item.layer ? t("l_" + item.layer) : t("k_" + panel.d.kind));
    const section = (title, html, dev) => (html ? `<h4${dev ? ' class="dev-only"' : ""}>${esc(title)}</h4><div${dev ? ' class="dev-only"' : ""}>${html}</div>` : "");
    const switchChips = (item.switches || []).map((k) =>
      `<a class="chip fam-amber" href="#sw-${esc(k)}" style="text-decoration:none">${esc(k)}</a>`).join(" ");
    const risks = (item.risks || []).length ? `<ul>${item.risks.map((r) => `<li>${rich(r)}</li>`).join("")}</ul>` : "";
    const detail = item.detail ? ui.panels.findIndex((p) => p.d.id === item.detail) : -1;
    const drill = detail >= 0
      ? `<button type="button" class="btn" data-drill="${detail}">${esc(t("open_detail", { t: ui.panels[detail].d.title || item.detail }))} →</button>` : "";

    const el = document.getElementById("inspector");
    el.innerHTML =
      `<div class="insp-head"><div style="flex:1;min-width:0"><div class="tagline"><span class="chip fam-${family}">${esc(typeLabel)}</span>` +
      `${item.confidence === "inferred" ? `<span class="chip fam-slate dashed">${esc(t("legend_inferred"))}</span>` : ""}</div>` +
      `<h3 style="margin-top:8px">${esc(item.label)}</h3>${item.tech ? `<div class="mono dev-only" style="color:var(--ink-3);margin-top:3px;word-break:break-all">${esc(item.tech)}</div>` : ""}</div>` +
      `<button type="button" class="icon-btn" data-close aria-label="${esc(t("close"))}">✕</button></div>` +
      `<div class="insp-body">${section(t("on_screen"), item.ui ? `<p>“${esc(item.ui)}”</p>` : "")}` +
      `${section(t("what"), paras(item.what))}${drill ? `<p>${drill}</p>` : ""}${section(t("how"), paras(item.how), true)}` +
      `${item.confidence === "inferred" ? `<p style="color:var(--ink-3);font-size:13px">${esc(t("inferred_note"))}</p>` : ""}` +
      `${section(t("depends"), switchChips)}${section(t("risks"), risks)}${section(t("code"), XR.refsHtml(item.refs), true)}</div>` +
      `<div class="insp-actions"><button type="button" class="btn primary" data-ticket>${esc(t("copy_ticket"))}</button>` +
      `<button type="button" class="btn" data-link>${esc(t("copy_link"))}</button></div>`;
    el.classList.add("open");
    el.querySelector("[data-close]").onclick = closeInspector;
    el.querySelector("[data-ticket]").onclick = () => XR.copy(ticketText(panel, item));
    el.querySelector("[data-link]").onclick = () => XR.copy(stepLink(panel, item));
    const drillBtn = el.querySelector("[data-drill]");
    if (drillBtn) drillBtn.onclick = () => { closeInspector(); clearHighlight(); activate(Number(drillBtn.dataset.drill)); };
  }

  /** A link that reopens the page on this exact step. */
  function stepLink(panel, item) {
    const key = Object.keys(panel.map).find((k) => panel.map[k] === item);
    const base = location.href.split("#")[0];
    return key ? `${base}#d=${encodeURIComponent(panel.d.id)}&n=${encodeURIComponent(key)}` : base;
  }

  function closeInspector() {
    document.getElementById("inspector").classList.remove("open");
    document.querySelectorAll("g.xr-sel").forEach((g) => g.classList.remove("xr-sel"));
  }

  function onDiagramClick(panel, under) {
    const g = under.closest("g.xr-node");
    if (!g) return;
    document.querySelectorAll("g.xr-sel").forEach((x) => x.classList.remove("xr-sel"));
    g.classList.add("xr-sel");
    openInspector(panel, panel.map[g.dataset.key]);
    try { history.replaceState(null, "", `#d=${encodeURIComponent(panel.d.id)}&n=${encodeURIComponent(g.dataset.key)}`); } catch (e) { /* no history */ }
  }

  /* ---------- highlighting ---------- */

  /** Accepts "diagramId:nodeId" or a bare "nodeId"; returns panel index + rendered key. */
  function resolve(target) {
    const parts = String(target).split(":");
    const wantDiagram = parts.length > 1 ? parts[0] : null;
    const nodeId = parts[parts.length - 1];
    for (let i = 0; i < ui.panels.length; i++) {
      const p = ui.panels[i];
      if (wantDiagram && p.d.id !== wantDiagram) continue;
      const key = [XR.nid(nodeId), "s_" + nodeId.replace(/[^A-Za-z0-9_]/g, "_")].find((k) => p.map[k]);
      if (key) return { i, key };
    }
    return null;
  }

  function applyHighlight(targets, title, scroll) {
    const hits = targets.map(resolve).filter(Boolean);
    if (!hits.length) return 0;
    const i = hits.some((h) => h.i === ui.active) ? ui.active : hits[0].i;
    clearHighlight();
    activate(i);
    const panel = ui.panels[i];
    const keys = hits.filter((h) => h.i === i).map((h) => h.key);
    const svg = panel.stage.querySelector("svg");
    if (!svg) return 0;
    svg.classList.add("xr-hl");
    const els = [];
    panel.stage.querySelectorAll("g.xr-node").forEach((g) => {
      const on = keys.includes(g.dataset.key);
      g.classList.toggle("xr-on", on);
      if (on) els.push(g);
    });
    panel.hl.hidden = false;
    panel.hl.querySelector("span").textContent = t("highlighting", { t: title });
    panel.pz.focus(els);
    panel.fitted = true;
    ui.highlight = { targets, title };
    if (scroll) document.getElementById("diagrams").scrollIntoView({ block: "start" });
    return els.length;
  }

  function clearHighlight() {
    ui.highlight = null;
    XR.options.syncCleared();
    ui.panels.forEach((p) => {
      p.hl.hidden = true;
      const svg = p.stage.querySelector("svg");
      if (svg) svg.classList.remove("xr-hl");
      p.stage.querySelectorAll("g.xr-on").forEach((g) => g.classList.remove("xr-on"));
    });
  }

  /* ---------- search ---------- */

  function search(query) {
    const q = query.trim().toLowerCase();
    document.querySelectorAll("[data-q]").forEach((row) => { row.hidden = Boolean(q) && !row.dataset.q.includes(q); });
    if (!q) { clearHighlight(); return; }
    const targets = [];
    ui.panels.forEach((p) => {
      Object.keys(p.map).forEach((key) => {
        const it = p.map[key];
        const hay = [it.label, it.tech, it.what, it.how].concat(it.risks || [], it.switches || []).join(" ").toLowerCase();
        if (hay.includes(q)) targets.push(`${p.d.id}:${it.id}`);
      });
    });
    if (targets.length) applyHighlight(targets, `"${query.trim()}"`, false);
    else clearHighlight();
  }

  /* ---------- lens / theme / boot ---------- */

  function setLens(lens) {
    ui.lens = lens === "developer" ? "developer" : "business";
    document.body.dataset.lens = ui.lens;
    XR.store.set("xray-lens", ui.lens);
    document.querySelectorAll("[data-lens-btn]").forEach((b) =>
      b.setAttribute("aria-pressed", String(b.dataset.lensBtn === ui.lens)));
  }

  function isDark() {
    const explicit = root.getAttribute("data-theme");
    if (explicit) return explicit === "dark";
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  function wireTopbar() {
    document.querySelector(".brand").textContent = t(D.kind === "module" ? "brand_module" : "brand");
    document.querySelector('[data-lens-btn="business"]').textContent = t("lens_business");
    document.querySelector('[data-lens-btn="developer"]').textContent = t("lens_developer");
    const input = document.getElementById("search");
    input.placeholder = t("search");
    let timer = null;
    input.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => search(input.value), 160); });
    document.querySelectorAll("[data-lens-btn]").forEach((b) => b.addEventListener("click", () => {
      setLens(b.dataset.lensBtn);
      renderDiagrams();
    }));
    const themeBtn = document.getElementById("theme-btn");
    themeBtn.title = t("theme");
    themeBtn.addEventListener("click", () => {
      const next = isDark() ? "light" : "dark";
      root.setAttribute("data-theme", next);
      XR.store.set("xray-theme", next);
    });
    const printBtn = document.getElementById("print-btn");
    printBtn.title = t("print");
    printBtn.addEventListener("click", () => window.print());
  }

  function wireGlobal() {
    document.addEventListener("click", (e) => {
      const copy = e.target.closest("[data-copy]");
      if (copy) { XR.copy(copy.dataset.copy); return; }
      const show = e.target.closest("[data-show]");
      if (show) applyHighlight(JSON.parse(show.dataset.show), show.dataset.title, true);
    });
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      closeInspector();
      const host = document.getElementById("diagrams");
      if (host.classList.contains("expanded")) host.querySelector('[data-act="expand"]').click();
    });
    /* Re-render when the theme changes, whoever changes it (button, OS, host page). */
    let last = isDark();
    const onTheme = () => { if (isDark() !== last) { last = isDark(); renderDiagrams(); } };
    new MutationObserver(onTheme).observe(root, { attributes: true, attributeFilter: ["data-theme"] });
    if (window.matchMedia) window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", onTheme);
  }

  function openFromHash() {
    const m = /d=([^&]+)(?:&n=([^&]+))?/.exec(location.hash || "");
    if (!m) return;
    const id = decodeURIComponent(m[1]);
    const key = m[2] ? decodeURIComponent(m[2]) : "";
    const i = ui.panels.findIndex((p) => p.d.id === id);
    if (i < 0) return;
    activate(i);
    if (!ui.panels[i].map[key]) {
      /* "#d=<diagram>" opens that diagram; "&full=1" shows it alone, filling the window. */
      const host = document.getElementById("diagrams");
      if (/[&#]full=1/.test(location.hash)) {
        host.classList.add("expanded");
        sizeViewport(ui.panels[i]);
        ui.panels[i].pz.fit();
      } else {
        host.scrollIntoView({ block: "start", behavior: "instant" });
      }
      return;
    }
    const g = ui.panels[i].stage.querySelector(`g.xr-node[data-key="${key}"]`);
    document.getElementById("diagrams").scrollIntoView({ block: "start", behavior: "instant" });
    openInspector(ui.panels[i], ui.panels[i].map[key]);
    if (g) { g.classList.add("xr-sel"); ui.panels[i].pz.focus([g]); }
  }

  async function boot() {
    const savedTheme = XR.store.get("xray-theme");
    if (savedTheme && !root.getAttribute("data-theme")) root.setAttribute("data-theme", savedTheme);
    setLens(XR.store.get("xray-lens") || XR.meta.lens || "business");
    wireTopbar();
    XR.renderStatic();
    buildPanels();
    wireGlobal();
    XR.options.wireKeys();
    await renderDiagrams();
    openFromHash();
    window.addEventListener("hashchange", openFromHash);
  }

  XR.app = { applyHighlight, clearHighlight, renderDiagrams, openInspector, activate };

  boot().catch((err) => {
    root.dataset.xrayStatus = "error";
    root.dataset.xrayErrors = "viewer crashed: " + (err && err.message ? err.message : err);
  });
})(window.XR);
