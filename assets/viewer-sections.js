/* X-Ray viewer — everything around the diagrams: header, key numbers,
   troubleshooting, switches, narrative sections, glossary, sources. */
window.XR = window.XR || {};

(function (XR) {
  "use strict";

  const { esc, rich, paras, t } = XR;
  const D = XR.DATA;

  const card = (id, title, sub, body) =>
    `<section class="card" id="${id}"><h2>${esc(title)}</h2>${sub ? `<p class="sub">${rich(sub)}</p>` : ""}${body}</section>`;
  const table = (heads, rows) =>
    `<div class="tbl-wrap"><table><thead><tr>${heads.map((h) => `<th${h.cls ? ` class="${h.cls}"` : ""}>${esc(h.label)}</th>`).join("")}` +
    `</tr></thead><tbody>${rows.join("")}</tbody></table></div>`;
  const searchText = (obj) => esc(JSON.stringify(obj).toLowerCase());
  const showBtn = (nodes, title) => (nodes && nodes.length
    ? `<button type="button" class="link-btn" data-show="${esc(JSON.stringify(nodes))}" data-title="${esc(title)}">${esc(t("show"))} →</button>`
    : "");
  const inferredChip = (x) => (x.confidence === "inferred"
    ? ` <span class="chip fam-slate dashed" style="margin-left:4px">${esc(t("legend_inferred"))}</span>` : "");
  const switchMeta = (x) => {
    const bits = [x.kind, x.scope].filter(Boolean).map(esc).join(" · ");
    return bits ? `<div style="font-size:12px;color:var(--ink-3);margin-top:3px">${bits}</div>` : "";
  };
  const devRefs = (refs) => (refs && refs.length ? `<div class="dev-only" style="margin-top:5px">${XR.refsInline(refs)}</div>` : "");

  function hero() {
    const m = XR.meta;
    const b = XR.build;
    const badges = [];
    if (b.verified) badges.push(`<span class="badge ok">✓ ${esc(t("verified", { n: b.refsVerified }))}</span>`);
    else badges.push(`<span class="badge warn">${esc(t("unverified"))}</span>`);
    badges.push(`<span class="badge" title="${esc(t("depth_hint"))}">${esc(t("depth_" + (m.depth || "quick")))}</span>`);
    if (b.commit) badges.push(`<span class="badge mono">${esc(t("commit", { c: b.commit }))}</span>`);
    if (b.generatedAt) badges.push(`<span class="badge">${esc(t("generated", { d: b.generatedAt }))}</span>`);
    if (b.files) badges.push(`<span class="badge dev-only">${esc(t("files_tracked", { n: Object.keys(b.files).length }))}</span>`);
    const pill = [m.module, m.package].filter(Boolean).join(" · ");
    return `${pill ? `<div class="pill">${esc(pill)}</div>` : ""}<h1>${esc(m.title)}</h1>` +
      `<div class="summary">${paras(m.summary)}</div><div class="meta-row">${badges.join("")}</div>` +
      (m.scope ? `<p class="scope"><strong>${esc(t("scope"))}:</strong> ${rich(m.scope)}</p>` : "");
  }

  function stats() {
    /* Counts describe the main (first) flow; drill-down flows would double-count. */
    const main = (D.diagrams || []).find((d) => d.kind === "flow");
    const nodes = main ? main.nodes : [];
    const count = (types) => nodes.filter((n) => types.includes(n.type)).length;
    const list = [
      ["stat_steps", count(["action", "process", "screen", "external", "store"])],
      ["stat_decisions", count(["decision"])],
      ["stat_failures", count(["error"])],
      ["stat_switches", (D.switches || []).length],
      ["stat_external", count(["external"])],
      ["stat_findings", (D.findings || []).length],
      ["stat_tests", (D.tests || []).length]
    ];
    return list.filter((s) => s[1] > 0).map((s) =>
      `<div class="g stat" title="${esc(t(s[0] + "_hint"))}"><div class="k">${esc(t(s[0]))}</div><div class="v">${s[1]}</div></div>`);
  }

  function glance() {
    const facts = (D.glance || []).map((g) =>
      `<div class="g"><div class="k">${esc(g.label)}</div><div class="v">${rich(g.value)}</div></div>`);
    return facts.concat(stats()).join("");
  }

  const SEVERITY_ORDER = { high: 0, medium: 1, low: 2 };
  /** Most severe first; rows of equal severity keep the author's order. */
  const bySeverity = (items) => items.map((x, i) => [x, i])
    .sort((a, b) => (SEVERITY_ORDER[a[0].severity || "medium"] - SEVERITY_ORDER[b[0].severity || "medium"]) || (a[1] - b[1]))
    .map((pair) => pair[0]);

  function troubleshooting() {
    const items = bySeverity(D.troubleshooting || []);
    if (!items.length) return "";
    const rows = items.map((x) =>
      `<tr data-q="${searchText(x)}"><td><span class="sev ${esc(x.severity || "medium")}"></span>${rich(x.symptom)}</td>` +
      `<td>${rich(x.cause)}${inferredChip(x)}</td><td>${rich(x.check || "")}${devRefs(x.refs)}</td>` +
      `<td>${showBtn(x.nodes, x.symptom)}</td></tr>`);
    return card("troubleshooting", t("troubleshooting"), t("troubleshooting_sub"),
      table([{ label: t("symptom") }, { label: t("cause") }, { label: t("check") }, { label: "" }], rows));
  }

  function switches() {
    const items = D.switches || [];
    if (!items.length) return "";
    const rows = items.map((x) =>
      `<tr id="sw-${esc(x.key)}" data-q="${searchText(x)}"><td><code>${esc(x.key)}</code>${switchMeta(x)}</td>` +
      `<td>${rich(x.effect)}${devRefs(x.refs)}</td><td>${rich(x.default == null ? "—" : String(x.default))}</td>` +
      `<td>${showBtn(x.nodes, x.key)}</td></tr>`);
    return card("switches", t("switches"), t("switches_sub"),
      table([{ label: t("sw_key") }, { label: t("sw_effect") }, { label: t("sw_default") }, { label: "" }], rows));
  }

  function findings() {
    const items = bySeverity(D.findings || []);
    if (!items.length) return "";
    const rows = items.map((x) =>
      `<tr data-q="${searchText(x)}"><td><span class="sev ${esc(x.severity || "medium")}"></span><strong>${rich(x.title)}</strong></td>` +
      `<td>${rich(x.detail)}${inferredChip(x)}${devRefs(x.refs)}</td><td>${showBtn(x.nodes, x.title)}</td></tr>`);
    return card("findings", t("findings"), t("findings_sub"),
      table([{ label: t("f_title") }, { label: t("f_detail") }, { label: "" }], rows));
  }

  function caveats() {
    const items = D.caveats || [];
    if (!items.length) return "";
    return `<div class="callout warn" style="margin-bottom:22px"><h3>${esc(t("caveats"))}</h3>` +
      `<ul class="plain">${items.map((x) => (typeof x === "string"
        ? `<li>${rich(x)}</li>` : `<li>${rich(x.text)}${devRefs(x.refs)}</li>`)).join("")}</ul></div>`;
  }

  function dataPoints() {
    const items = D.data || [];
    if (!items.length) return "";
    const rows = items.map((x) =>
      `<tr data-q="${searchText(x)}"><td><strong>${rich(x.name)}</strong></td><td>${esc(x.kind || "")}</td>` +
      `<td>${esc(t("dir_" + (x.direction || "read")))}${x.boundary ? `<div style="margin-top:4px"><span class="chip fam-rose">${esc(x.boundary)}</span></div>` : ""}</td>` +
      `<td>${rich(x.what || "")}${devRefs(x.refs)}</td></tr>`);
    return card("data", t("data"), t("data_sub"),
      table([{ label: t("d_name") }, { label: t("d_kind") }, { label: t("d_dir") }, { label: t("d_detail") }], rows));
  }

  function tests() {
    if (!Array.isArray(D.tests)) return "";
    const body = D.tests.length
      ? `<ul class="plain">${D.tests.map((x) =>
        `<li><span class="mono">${esc(x.path)}</span>${x.covers ? ` — ${rich(x.covers)}` : ""}</li>`).join("")}</ul>`
      : `<div class="callout warn">${esc(t("tests_none"))}</div>`;
    return `<div class="dev-only">${card("tests", t("tests"), t("tests_sub"), body)}</div>`;
  }

  function glossary() {
    const items = D.glossary || [];
    if (!items.length) return "";
    return card("glossary", t("glossary"), "",
      `<dl class="gloss">${items.map((x) => `<dt>${esc(x.term)}</dt><dd>${rich(x.meaning)}</dd>`).join("")}</dl>`);
  }

  function openQuestions() {
    const items = D.openQuestions || [];
    if (!items.length) return "";
    return card("open-questions", t("open_questions"), t("open_questions_sub"),
      `<ul class="plain">${items.map((x) => `<li>${rich(x)}</li>`).join("")}</ul>`);
  }

  function sources() {
    const byPath = {};
    XR.allRefs().forEach((r) => {
      byPath[r.path] = byPath[r.path] || [];
      if (r.line && !byPath[r.path].includes(r.line)) byPath[r.path].push(r.line);
    });
    const paths = Object.keys(byPath).sort();
    if (!paths.length) return "";
    const body = paths.map((p) =>
      `<div class="src-file"><div class="p" data-copy="${esc(p)}">${esc(p)}</div>` +
      `<div class="l">${byPath[p].sort((a, b) => a - b).map((l) => `:${l}`).join("  ") || "&nbsp;"}</div></div>`).join("");
    return `<div class="dev-only">${card("sources", t("sources"), t("sources_sub"), body)}</div>`;
  }

  const GENERIC = {
    cards: (s) => `<div class="grid">${(s.items || []).map((x) =>
      `<div class="tile${x.tone ? " tone-" + esc(x.tone) : ""}"><h3>${esc(x.title)}</h3>${paras(x.text)}${devRefs(x.refs)}</div>`).join("")}</div>`,
    links: (s) => `<div class="grid">${(s.items || []).map((x) => (x.href
      ? `<a class="tile tone-blue" href="${esc(x.href)}"><h3>${esc(x.title)}</h3>${paras(x.text)}</a>`
      : `<div class="tile"><h3>${esc(x.title)}</h3>${paras(x.text)}<p><span class="chip fam-slate dashed">${esc(t("planned"))}</span></p></div>`)).join("")}</div>`,
    steps: (s) => `<div class="steps">${(s.items || []).map((x) =>
      `<div class="st"><div>${x.meta ? `<div class="m dev-only">${esc(x.meta)}</div>` : ""}<h3>${esc(x.title)}</h3>${paras(x.text)}` +
      `${x.bullets && x.bullets.length ? `<ul>${x.bullets.map((b) => `<li>${rich(b)}</li>`).join("")}</ul>` : ""}${devRefs(x.refs)}</div></div>`).join("")}</div>`,
    table: (s) => table((s.columns || []).map((c) => ({ label: c })),
      (s.rows || []).map((r) => `<tr data-q="${searchText(r)}">${r.map((c) => `<td>${rich(c)}</td>`).join("")}</tr>`)),
    callout: (s) => `<div class="callout ${esc(s.tone || "info")}">${paras(s.text)}</div>`,
    prose: (s) => `<div class="prose">${paras(s.text)}</div>`,
    layers: (s) => `<div class="layers">${(s.items || []).map((x) =>
      `<div class="ly"><div class="n fam-${esc(XR.LAYER_FAMILY[x.layer] || x.tone || "slate")}">${esc(x.name)}</div>` +
      `<div class="d">${paras(x.text)}${devRefs(x.refs)}</div></div>`).join("")}</div>`
  };

  function generic(placement) {
    return (D.sections || []).filter((s) => (s.placement || "bottom") === placement).map((s, i) => {
      const render = GENERIC[s.type];
      if (!render) return "";
      return card(`sec-${placement}-${i}`, s.title || "", s.subtitle || "", render(s) + devRefs(s.refs));
    }).join("");
  }

  XR.renderStatic = function () {
    document.title = XR.meta.title ? `${XR.meta.title} · X-Ray` : document.title;
    document.querySelector(".doc-title").textContent = XR.meta.title || "";
    document.getElementById("hero").innerHTML = hero();
    document.getElementById("glance").innerHTML = glance();
    document.getElementById("top-sections").innerHTML = caveats() + generic("top");
    document.getElementById("bottom-sections").innerHTML =
      troubleshooting() + findings() + switches() + generic("bottom") + dataPoints() + tests() + glossary() + openQuestions() + sources();
    const spent = XR.build.usage;
    const fmt = (n) => (n >= 1e6 ? (n / 1e6).toFixed(1) + "M" : n >= 1e3 ? Math.round(n / 1e3) + "k" : String(n || 0));
    const produced = spent && spent.tokens ? " " + t("produced_with", {
      calls: spent.apiCalls, out: fmt(spent.tokens.output), cached: fmt(spent.tokens.cacheRead),
      model: (spent.models || []).join(", ") || "?" }) : "";
    document.getElementById("footer").textContent = t("footer") + produced;
  };
})(window.XR);
