/* X-Ray viewer — turns structured diagram data into Mermaid source.
   The agent never writes Mermaid by hand (except for kind "raw"): it describes
   nodes, edges and steps, and this file handles ids, escaping, shapes, colours
   and the two audience lenses. That is what keeps diagrams from breaking. */
window.XR = window.XR || {};

(function (XR) {
  "use strict";

  const FAMILIES = ["green", "blue", "slate", "amber", "rose", "violet", "teal", "screen"];

  XR.NODE_TYPES = ["start", "action", "process", "screen", "decision", "external", "store", "end", "error", "unknown"];
  XR.TYPE_FAMILY = {
    start: "green", end: "green", action: "blue", process: "slate", decision: "amber",
    error: "rose", external: "violet", store: "teal", screen: "screen", unknown: "slate"
  };
  XR.LAYER_ORDER = ["user", "ui", "viewmodel", "domain", "data", "shared", "device", "backend", "external"];
  XR.LAYER_FAMILY = {
    user: "slate", ui: "blue", viewmodel: "amber", domain: "green", data: "teal",
    shared: "slate", device: "slate", backend: "violet", external: "rose"
  };
  const COMPONENT_SHAPE = {
    fragment: "screen", activity: "screen", screen: "screen", dialog: "screen",
    store: "store", database: "store", external: "external", api: "external", backend: "external"
  };

  const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  /** Reads the active theme's colours from the CSS tokens. */
  XR.palette = function () {
    const fam = {};
    FAMILIES.forEach((f) => {
      fam[f] = { bg: cssVar(`--c-${f}-bg`), bd: cssVar(`--c-${f}-bd`), fg: cssVar(`--c-${f}-fg`) };
    });
    return {
      ink: cssVar("--ink"), ink2: cssVar("--ink-2"), ink3: cssVar("--ink-3"),
      line: cssVar("--line"), line2: cssVar("--line-2"),
      surface: cssVar("--surface"), surface2: cssVar("--surface-2"), fam
    };
  };

  const safe = (s) => String(s).replace(/[^A-Za-z0-9_]/g, "_");
  XR.nid = (id) => "n_" + safe(id);
  const gid = (id) => "g_" + safe(id);
  const pid = (id) => "p_" + safe(id);

  /** Escapes text for a Mermaid label using Mermaid's own #entity; syntax. */
  const MM_ENTITY = { "#": "#35;", "&": "#amp;", "<": "#lt;", ">": "#gt;", '"': "#quot;", ";": "#59;" };
  function mmEsc(s) {
    /* One pass, so an entity produced for one character is never re-escaped. */
    return String(s == null ? "" : s).replace(/`/g, "").replace(/[#&<>";]/g, (c) => MM_ENTITY[c]);
  }

  function wrap(text, width) {
    const words = String(text == null ? "" : text).split(/\s+/).filter(Boolean);
    const lines = [];
    let cur = "";
    words.forEach((w) => {
      if (cur && (cur + " " + w).length > width) { lines.push(cur); cur = w; }
      else { cur = cur ? cur + " " + w : w; }
    });
    if (cur) lines.push(cur);
    return lines;
  }
  const mmLabel = (text, width) => wrap(text, width).map(mmEsc).join("<br/>");

  /** Breaks a long Class.method identifier onto two lines at the last dot. */
  function techLabel(tech) {
    const s = String(tech);
    const dot = s.lastIndexOf(".");
    if (s.length <= 34 || dot <= 0) return mmEsc(s);
    return mmEsc(s.slice(0, dot)) + "<br/>" + mmEsc(s.slice(dot));
  }

  /** plain = no HTML spans, for exports rendered with SVG text labels. */
  function nodeText(item, lens, width, plain) {
    const main = mmLabel(item.label, width);
    if (lens !== "developer" || !item.tech) return main;
    return plain ? `${main}<br/>${techLabel(item.tech)}` : `${main}<br/><span class='tech'>${techLabel(item.tech)}</span>`;
  }

  function shaped(shape, id, label) {
    switch (shape) {
      case "start": case "end": case "error": case "unknown": return `${id}(["${label}"])`;
      case "decision": return `${id}{"${label}"}`;
      case "external": return `${id}[["${label}"]]`;
      case "store": return `${id}[("${label}")]`;
      case "screen": return `${id}{{"${label}"}}`;
      default: return `${id}["${label}"]`;
    }
  }

  function classDefs(P, families) {
    const out = families.map((f) =>
      `  classDef c_${f} fill:${P.fam[f].bg},stroke:${P.fam[f].bd},color:${P.fam[f].fg},stroke-width:1.6px`);
    out.push("  classDef inferred stroke-dasharray:6 4");
    return out;
  }

  function classLines(assign) {
    return Object.keys(assign).map((cls) => `  class ${assign[cls].join(",")} ${cls}`);
  }

  function edgeLine(e, kind) {
    const arrow = kind === "optional" ? "-.->" : kind === "main" ? "==>" : "-->";
    const label = e.label ? `|"${mmLabel(e.label, 24)}"|` : "";
    return `  ${XR.nid(e.from)} ${arrow}${label} ${XR.nid(e.to)}`;
  }

  function flowText(d, lens, P, plain) {
    const L = [`flowchart ${d.direction || "TB"}`];
    const groups = d.groups || [];
    const typeOf = {};
    const byGroup = {};
    groups.forEach((g) => { byGroup[g.id] = []; });
    const loose = [];
    d.nodes.forEach((n) => {
      typeOf[n.id] = n.type;
      (n.group && byGroup[n.group] ? byGroup[n.group] : loose).push(n);
    });
    /* A diamond grows with its widest line, so decisions wrap tighter. */
    const line = (n) => "  " + shaped(n.type, XR.nid(n.id), nodeText(n, lens, n.type === "decision" ? 20 : 28, plain));

    loose.forEach((n) => L.push(line(n)));
    groups.forEach((g) => {
      L.push(`  subgraph ${gid(g.id)}["${mmLabel(g.title, 24)}"]`);
      L.push(`    direction ${g.direction || d.direction || "TB"}`);
      byGroup[g.id].forEach((n) => L.push("  " + line(n)));
      L.push("  end");
    });

    const errorEdges = [];
    d.edges.forEach((e, i) => {
      const kind = e.kind || (typeOf[e.to] === "error" ? "error" : "");
      L.push(edgeLine(e, kind));
      if (kind === "error") errorEdges.push(i);
    });

    const assign = {};
    const used = [];
    d.nodes.forEach((n) => {
      const fam = XR.TYPE_FAMILY[n.type] || "slate";
      if (!used.includes(fam)) used.push(fam);
      (assign["c_" + fam] = assign["c_" + fam] || []).push(XR.nid(n.id));
      if (n.confidence === "inferred" || n.type === "unknown") (assign.inferred = assign.inferred || []).push(XR.nid(n.id));
    });
    L.push(...classDefs(P, used), ...classLines(assign));
    groups.forEach((g) => L.push(
      `  style ${gid(g.id)} fill:${P.surface},stroke:${P.line2},stroke-dasharray:4 4,color:${P.ink2}`));
    if (errorEdges.length) L.push(`  linkStyle ${errorEdges.join(",")} stroke:${P.fam.rose.bd},stroke-width:1.8px`);
    return L.join("\n");
  }

  function componentsText(d, lens, P, plain) {
    const L = [`flowchart ${d.direction || "TB"}`];
    const declared = (d.layers || []).map((l) => l.id);
    const present = d.components.map((c) => c.layer).filter((l, i, a) => l && a.indexOf(l) === i);
    const order = declared.length ? declared
      : XR.LAYER_ORDER.filter((l) => present.includes(l)).concat(present.filter((l) => !XR.LAYER_ORDER.includes(l)));
    const title = (id) => {
      const found = (d.layers || []).find((l) => l.id === id);
      return found && found.title ? found.title : XR.t("l_" + id);
    };
    const famOf = (layer) => XR.LAYER_FAMILY[layer] || "slate";
    const line = (c) => "  " + shaped(COMPONENT_SHAPE[c.kind] || "rect", XR.nid(c.id), nodeText(c, lens, 26, plain));

    d.components.filter((c) => !order.includes(c.layer)).forEach((c) => L.push(line(c)));
    order.forEach((layer) => {
      L.push(`  subgraph ${gid(layer)}["${mmEsc(title(layer))}"]`);
      L.push(`    direction ${d.layerDirection || "LR"}`);
      d.components.filter((c) => c.layer === layer).forEach((c) => L.push("  " + line(c)));
      L.push("  end");
    });
    (d.links || []).forEach((e) => L.push(edgeLine(e, e.kind || "")));

    const assign = {};
    const used = [];
    d.components.forEach((c) => {
      const fam = famOf(c.layer);
      if (!used.includes(fam)) used.push(fam);
      (assign["c_" + fam] = assign["c_" + fam] || []).push(XR.nid(c.id));
      if (c.confidence === "inferred") (assign.inferred = assign.inferred || []).push(XR.nid(c.id));
    });
    L.push(...classDefs(P, used), ...classLines(assign));
    order.forEach((layer) => L.push(
      `  style ${gid(layer)} fill:${P.surface},stroke:${P.fam[famOf(layer)].bd},stroke-dasharray:4 4,color:${P.ink2}`));
    return L.join("\n");
  }

  function hexToRgba(hex, alpha) {
    const m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex);
    if (!m) return `rgba(120,130,150,${alpha})`;
    return `rgba(${parseInt(m[1], 16)},${parseInt(m[2], 16)},${parseInt(m[3], 16)},${alpha})`;
  }

  const seqEsc = (s) => mmEsc(String(s == null ? "" : s).replace(/\s*\n\s*/g, " "));

  /** Returns the Mermaid source plus the flattened rows for the step table. */
  function sequenceBuild(d, lens, P) {
    const L = ["sequenceDiagram", "  autonumber"];
    const rows = [];
    const byId = {};
    const nameOf = (p) => (lens === "developer" && p.tech ? p.tech : p.label);
    d.participants.forEach((p) => { byId[p.id] = p; });

    let i = 0;
    const ps = d.participants;
    while (i < ps.length) {
      const layer = ps[i].layer;
      let j = i;
      while (j < ps.length && ps[j].layer === layer) j++;
      const decl = ps.slice(i, j).map((p) =>
        `${p.type === "actor" ? "actor" : "participant"} ${pid(p.id)} as ${seqEsc(nameOf(p))}`);
      if (layer && layer !== "user") {
        const fam = P.fam[XR.LAYER_FAMILY[layer] || "slate"];
        L.push(`  box ${hexToRgba(fam.bd, 0.1)} ${seqEsc(XR.t("l_" + layer))}`);
        decl.forEach((x) => L.push("    " + x));
        L.push("  end");
      } else {
        decl.forEach((x) => L.push("  " + x));
      }
      i = j;
    }

    let n = 0;
    const ARROW = { sync: "->>", reply: "-->>", async: "-)", fail: "-x" };
    const block = (keyword, when, steps, indent) => {
      L.push(`${indent}${keyword} ${seqEsc(when || "")}`);
      rows.push({ type: "group", text: `${keyword}: ${when || ""}` });
      emit(steps || [], indent + "  ");
    };
    function emit(steps, indent) {
      steps.forEach((s) => {
        if (s.alt) {
          s.alt.forEach((b, k) => block(k === 0 ? "alt" : "else", b.when, b.steps, indent));
          L.push(`${indent}end`);
        } else if (s.opt) {
          block("opt", s.opt.when, s.opt.steps, indent);
          L.push(`${indent}end`);
        } else if (s.loop) {
          block("loop", s.loop.when, s.loop.steps, indent);
          L.push(`${indent}end`);
        } else if (s.note) {
          const over = (s.note.over || []).map(pid).join(",");
          L.push(`${indent}Note over ${over}: ${wrap(s.note.text, 34).map(mmEsc).join("<br/>")}`);
        } else {
          n += 1;
          const text = lens === "developer" && s.tech
            ? `${seqEsc(s.label)}<br/>${seqEsc(s.tech)}` : seqEsc(s.label);
          L.push(`${indent}${pid(s.from)}${ARROW[s.kind] || ARROW.sync}${pid(s.to)}: ${text}`);
          rows.push({
            type: "msg", n, step: s,
            from: nameOf(byId[s.from] || { label: s.from }), to: nameOf(byId[s.to] || { label: s.to })
          });
        }
      });
    }
    emit(d.steps || [], "  ");
    return { text: L.join("\n"), rows };
  }

  const stEsc = (s) => String(s == null ? "" : s).replace(/"/g, "'").replace(/:/g, " –").replace(/\s*\n\s*/g, " ");

  function stateText(d, lens, P) {
    const sid = (id) => "s_" + safe(id);
    const L = ["stateDiagram-v2", `  direction ${d.direction || "LR"}`];
    d.states.forEach((s) => L.push(`  state "${stEsc(s.label)}" as ${sid(s.id)}`));
    d.states.filter((s) => s.initial).forEach((s) => L.push(`  [*] --> ${sid(s.id)}`));
    (d.transitions || []).forEach((t) => {
      const label = lens === "developer" && t.tech ? `${t.label || ""} (${t.tech})` : t.label;
      L.push(`  ${sid(t.from)} --> ${sid(t.to)}${label ? ": " + stEsc(label) : ""}`);
    });
    d.states.filter((s) => s.final).forEach((s) => L.push(`  ${sid(s.id)} --> [*]`));
    const used = [];
    d.states.forEach((s) => { const f = s.color || "blue"; if (!used.includes(f) && P.fam[f]) used.push(f); });
    used.forEach((f) => L.push(
      `  classDef c_${f} fill:${P.fam[f].bg},stroke:${P.fam[f].bd},color:${P.fam[f].fg},stroke-width:1.6px`));
    d.states.forEach((s) => { const f = s.color || "blue"; if (P.fam[f]) L.push(`  class ${sid(s.id)} c_${f}`); });
    return L.join("\n");
  }

  /** Items a reader can click in a diagram, keyed by the id Mermaid renders. */
  XR.clickables = function (d) {
    const map = {};
    if (d.kind === "flow") d.nodes.forEach((n) => { map[XR.nid(n.id)] = n; });
    if (d.kind === "components") d.components.forEach((c) => { map[XR.nid(c.id)] = c; });
    if (d.kind === "state") d.states.forEach((s) => { map["s_" + safe(s.id)] = s; });
    return map;
  };

  XR.legend = function (d) {
    if (d.kind === "flow") {
      const items = XR.NODE_TYPES.filter((ty) => d.nodes.some((n) => n.type === ty))
        .map((ty) => ({ family: XR.TYPE_FAMILY[ty], label: XR.t("t_" + ty), pick: "type:" + ty, dashed: ty === "unknown" }));
      if (d.nodes.some((n) => n.confidence === "inferred")) {
        items.push({ family: "slate", label: XR.t("legend_inferred"), dashed: true, pick: "inferred" });
      }
      return items;
    }
    if (d.kind === "components") {
      const layers = d.components.map((c) => c.layer).filter((l, i, a) => l && a.indexOf(l) === i);
      return layers.map((l) => {
        const found = (d.layers || []).find((x) => x.id === l);
        return { family: XR.LAYER_FAMILY[l] || "slate", label: found && found.title ? found.title : XR.t("l_" + l), pick: "layer:" + l };
      });
    }
    return [];
  };

  /**
   * @param {object} d diagram data
   * @param {string} lens "business" or "developer"
   * @param {{plain?: boolean}} [opts] plain = export-safe labels
   * @returns {{text: string, rows?: Array}} Mermaid source for one diagram.
   */
  XR.buildDiagram = function (d, lens, opts) {
    const P = XR.palette();
    const plain = Boolean(opts && opts.plain);
    if (d.kind === "flow") return { text: flowText(d, lens, P, plain) };
    if (d.kind === "components") return { text: componentsText(d, lens, P, plain) };
    if (d.kind === "sequence") return sequenceBuild(d, lens, P);
    if (d.kind === "state") return { text: stateText(d, lens, P) };
    return { text: String(d.mermaid || "") };
  };

  XR.mermaidConfig = function () {
    const P = XR.palette();
    return {
      startOnLoad: false, theme: "base", securityLevel: "loose",
      flowchart: { curve: "basis", nodeSpacing: 42, rankSpacing: 52, htmlLabels: true, padding: 12, useMaxWidth: false },
      sequence: { useMaxWidth: false, mirrorActors: false, messageMargin: 40, boxMargin: 8, wrap: false },
      state: { useMaxWidth: false },
      themeVariables: {
        fontFamily: "Inter, Segoe UI, system-ui, Helvetica, Arial, sans-serif", fontSize: "14px",
        background: P.surface, primaryColor: P.fam.blue.bg, primaryBorderColor: P.fam.blue.bd,
        primaryTextColor: P.ink, secondaryColor: P.surface2, tertiaryColor: P.surface2,
        lineColor: P.ink3, textColor: P.ink, mainBkg: P.fam.blue.bg, nodeBorder: P.fam.blue.bd,
        clusterBkg: P.surface, clusterBorder: P.line2, titleColor: P.ink2,
        edgeLabelBackground: P.surface,
        actorBkg: P.fam.blue.bg, actorBorder: P.fam.blue.bd, actorTextColor: P.fam.blue.fg, actorLineColor: P.line2,
        signalColor: P.ink2, signalTextColor: P.ink, labelBoxBkgColor: P.surface2, labelBoxBorderColor: P.line2,
        labelTextColor: P.ink, loopTextColor: P.ink2, noteBkgColor: P.fam.amber.bg, noteBorderColor: P.fam.amber.bd,
        noteTextColor: P.fam.amber.fg, sequenceNumberColor: P.surface,
        transitionColor: P.ink3, stateLabelColor: P.ink
      }
    };
  };
})(window.XR);
