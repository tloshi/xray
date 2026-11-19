/* X-Ray viewer — shared helpers: data access, translation, safe HTML. */
window.XR = window.XR || {};

(function (XR) {
  "use strict";

  XR.DATA = JSON.parse(document.getElementById("xray-data").textContent);
  XR.meta = XR.DATA.meta || {};
  XR.build = XR.DATA._build || {};
  XR.lang = XR.I18N[XR.meta.lang] ? XR.meta.lang : "en";

  /** Translates a viewer label, filling {placeholders}. */
  XR.t = function (key, vars) {
    const table = XR.I18N[XR.lang];
    let text = table[key] != null ? table[key] : (XR.I18N.en[key] != null ? XR.I18N.en[key] : key);
    Object.keys(vars || {}).forEach((k) => { text = text.replace(`{${k}}`, vars[k]); });
    return text;
  };

  const ENT = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  XR.esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ENT[c]);

  /** Escapes, then allows `code` and **bold** only. Content never injects raw HTML. */
  XR.rich = (s) => XR.esc(s)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");

  XR.paras = (s) => String(s == null ? "" : s).split(/\n{2,}/).filter(Boolean)
    .map((p) => `<p>${XR.rich(p).replace(/\n/g, "<br>")}</p>`).join("");

  XR.normRef = function (r) {
    if (typeof r !== "string") return r;
    const m = /^(.*?)(?::(\d+))?$/.exec(r);
    const path = m[1];
    return { path, line: m[2] ? Number(m[2]) : null, name: path.split("/").pop() };
  };
  XR.refLoc = (r) => `${r.name || String(r.path).split("/").pop()}${r.line ? ":" + r.line : ""}`;
  XR.refFull = (r) => `${r.path}${r.line ? ":" + r.line : ""}`;

  /** Code references as rows; clicking a location copies path:line. */
  XR.refsHtml = function (refs) {
    return (refs || []).map(XR.normRef).map((r) =>
      `<div class="ref"><span class="loc" data-copy="${XR.esc(XR.refFull(r))}" title="${XR.esc(XR.refFull(r))}">` +
      `${XR.esc(XR.refLoc(r))}</span>${r.symbol ? `<span class="sym">${XR.esc(r.symbol)}</span>` : ""}</div>`
    ).join("");
  };
  XR.refsInline = function (refs) {
    return (refs || []).map(XR.normRef).map((r) =>
      `<span class="ref-inline" data-copy="${XR.esc(XR.refFull(r))}" title="${XR.esc(XR.refFull(r))}">` +
      `${XR.esc(XR.refLoc(r))}</span>`).join(" · ");
  };

  XR.store = {
    get(key) { try { return window.localStorage.getItem(key); } catch (e) { return null; } },
    set(key, value) { try { window.localStorage.setItem(key, value); } catch (e) { /* storage unavailable */ } }
  };

  let toastTimer = null;
  XR.toast = function (text) {
    const el = document.getElementById("toast");
    el.textContent = text;
    el.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove("show"), 1400);
  };

  XR.copy = function (text) {
    const done = () => XR.toast(XR.t("copied"));
    const fallback = () => {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); done(); } catch (e) { XR.toast(text); }
      ta.remove();
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, fallback);
    } else {
      fallback();
    }
  };

  /** Every code reference in the document, wherever it is attached. */
  XR.allRefs = function () {
    const found = [];
    const walk = (value) => {
      if (Array.isArray(value)) { value.forEach(walk); return; }
      if (!value || typeof value !== "object") return;
      Object.keys(value).forEach((key) => {
        if (key === "_build") return;
        if (key === "refs" && Array.isArray(value[key])) value[key].forEach((r) => found.push(XR.normRef(r)));
        else walk(value[key]);
      });
    };
    walk(XR.DATA);
    return found;
  };
})(window.XR);
