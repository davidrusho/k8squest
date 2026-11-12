"use strict";
(function () {
  const $ = (id) => document.getElementById(id);
  const DEFAULT_DESKTOP_URL = "http://localhost:6080/vnc.html?autoconnect=1&resize=scale";
  const BEAT_MS = 10000;
  const LABEL = {
    not_opened: "not opened", opened: "opened", flagged: "flagged",
    passed_in_time: "passed in time", passed_over_time: "passed over time", failed: "failed",
  };

  // the server may override the desktop URL (EXAM_DESKTOP_URL) through /api/state
  const desktopUrl = () => (S && S.desktop_url) || DEFAULT_DESKTOP_URL;
  let S = null;            // last /api/state
  let current = null;      // id of the task shown
  let payload = {};        // task id -> last full task payload (text etc.)
  let verdicts = {};       // task id -> last check result shown
  let snap = null;         // timer snapshot {remaining, at, running}
  let busy = false;        // a deploy or check is in flight
  let desktopLoaded = false;
  let mode = "exam";       // "drill" | "exam"; forced to "exam" while an exam session is live
  try { if (localStorage.getItem("cka-mode") === "drill") mode = "drill"; } catch (e) { /* storage unavailable */ }
  let D = null;            // last /api/drill/state
  let dcur = null;         // drill task shown, null = picker
  let dpay = {};           // drill task id -> last payload
  let dstart = {};         // drill task id -> performance.now() when it was opened (client-side only)
  let dfilter = "all";
  let dgroup = "domain";
  try { if (localStorage.getItem("cka-drill-group") === "pattern") dgroup = "pattern"; } catch (e) { /* storage unavailable */ }
  let dbusy = false;

  // ------------------------------------------------------------------ helpers
  function el(tag, attrs, ...kids) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === "class") e.className = v;
      else if (k === "text") e.textContent = v;
      else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
      else e.setAttribute(k, v);
    }
    for (const kid of kids) if (kid != null) e.append(kid);
    return e;
  }
  // text with `code` spans, no innerHTML
  function rich(text) {
    const frag = document.createDocumentFragment();
    text.split(/(`[^`]+`)/).forEach((part) => {
      if (part.startsWith("`") && part.endsWith("`") && part.length > 2) frag.append(el("code", { text: part.slice(1, -1) }));
      else if (part) frag.append(document.createTextNode(part));
    });
    return frag;
  }
  async function api(path, body) {
    const opt = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
    const r = await fetch(path, opt);
    let data = {};
    try { data = await r.json(); } catch (e) { /* empty */ }
    if (!r.ok) throw new Error(data.error || ("HTTP " + r.status));
    return data;
  }
  function fire(path, body) {   // fire-and-forget, survives page hide
    try { fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), keepalive: true }); } catch (e) { /* ignore */ }
  }
  function fmt(sec) {
    const s = Math.max(0, Math.round(sec));
    return Math.floor(s / 60) + " min " + String(s % 60).padStart(2, "0") + " s";
  }
  const sess = () => (S && S.session) || null;
  const live = () => sess() && !sess().ended;
  const taskView = (id) => (sess() ? sess().tasks.find((t) => t.id === id) : null);

  // ------------------------------------------------------------------ timer
  function setSnap(view) {
    snap = view ? { remaining: view.remaining, at: performance.now(), running: view.running } : null;
    paintTimer();
  }
  function paintTimer() {
    const bar = $("timerbar"), txt = $("timer-text");
    bar.className = "timer";
    if (!live() || !current || !snap) {
      bar.classList.add("idle");
      txt.textContent = live() ? "Time remaining: -" : "No session running";
      return;
    }
    const rem = snap.running ? snap.remaining - (performance.now() - snap.at) / 1000 : snap.remaining;
    const budget = S.budget;
    if (rem < 0) {
      bar.classList.add("over");
      txt.textContent = "Time over by " + fmt(-rem) + ". You can still Check, but a pass will not count.";
    } else {
      bar.classList.add(rem <= budget * 0.25 ? "orange" : "green");
      txt.textContent = "Time remaining: " + fmt(rem) + (snap.running ? "" : " (paused)");
    }
  }
  setInterval(paintTimer, 500);

  // ------------------------------------------------------------------ rendering
  function renderChrome() {
    const s = sess();
    const tasks = s ? s.tasks : [];
    const idx = current ? tasks.findIndex((t) => t.id === current) : -1;
    $("task-label").textContent = live() && idx >= 0 ? "Task " + (idx + 1) + " of " + tasks.length : (s ? "Session ended" : "No session");
    $("task-select").disabled = !live() || busy;
    $("btn-next-arrow").disabled = !live() || busy || idx < 0 || idx >= tasks.length - 1;
    $("btn-flag").disabled = !live() || busy || idx < 0;
    $("btn-satisfied").disabled = !live() || busy || idx < 0;
    $("btn-end").disabled = !live() || busy;
    const v = taskView(current);
    $("btn-flag").textContent = v && v.flagged ? "Flagged. Click to remove the flag" : "Flag this to return to later";
    $("btn-flag").classList.toggle("on", !!(v && v.flagged));
    $("btn-satisfied").textContent = idx >= 0 && idx === tasks.length - 1 ? "I am satisfied, finish →" : "I am satisfied, next →";
    $("task-domain").textContent = v ? v.domain : "";
    renderList();
  }
  function renderList() {
    const ul = $("task-list");
    ul.replaceChildren();
    const s = sess();
    if (!s) return;
    s.tasks.forEach((t, i) => {
      const li = el("li", { role: "option", class: t.id === current ? "current" : "", onclick: () => { hideList(); gotoTask(t.id); } },
        el("span", { class: "n", text: "Task " + (i + 1) }),
        el("span", { class: "badge b-" + t.status, text: t.status_label }),
        el("span", { class: "dom", text: t.domain }),
        el("span", { class: "counted", title: t.ever_counted ? "Has counted in some session" : "Has never counted", text: t.ever_counted ? "✓" : "" }));
      ul.append(li);
    });
  }
  function hideList() { $("task-list").hidden = true; }

  function renderStart() {
    const sc = $("screen");
    const done = S ? S.counted_ever : 0, pool = S ? S.pool_size : 0;
    sc.replaceChildren(el("div", { class: "start" },
      el("h2", { text: "CKA practice exam" }),
      el("p", { text: "16 tasks drawn from a pool of " + pool + ", spread by the curriculum domain weights. 7.5 minutes per task. " + done + " of " + pool + " tasks have counted so far." }),
      el("div", { class: "btnrow" },
        el("button", { class: "go", id: "start-weighted", text: "Start a new session", onclick: () => startSession("weighted") }),
        el("button", { id: "start-missed", text: "New session: missed tasks first", onclick: () => startSession("missed") })),
      el("p", { text: "Starting a session resets the exam hosts (cka1 to cka3) and removes the exam namespaces from earlier sessions." })));
    $("task-domain").textContent = "";
  }

  function renderSummary() {
    const s = sess();
    const d = s.summary_detail, sm = s.summary;
    const tags = (list, cls) => el("div", { class: "taglist" }, ...(list.length ? list.map((t) => el("span", { class: "tag " + cls, title: t.domain, text: "Task " + t.n })) : [el("span", { class: "attempts", text: "none" })]));
    $("screen").replaceChildren(el("div", { class: "summary" },
      el("h2", { text: "Exam ended" }),
      el("p", { text: sm.counted.length + " of " + sm.total + " tasks counted." }),
      el("dl", { class: "sumgrid" },
        el("dt", { text: "Counted" }), el("dd", {}, tags(d.counted, "ok")),
        el("dt", { text: "Passed over time" }), el("dd", {}, tags(d.passed_over_time, "over")),
        el("dt", { text: "Missed" }), el("dd", {}, tags(d.missed, "miss"))),
      el("p", { text: "Passed over time does not count: redo those tasks within 7.5 minutes in a later session. Missed tasks were failed or never passed." }),
      el("div", { class: "btnrow" },
        el("button", { class: "go", id: "sum-missed", text: "New session: missed tasks first", onclick: () => startSession("missed") }),
        el("button", { id: "sum-weighted", text: "New session", onclick: () => startSession("weighted") }))));
  }

  function renderTask(id) {
    const p = payload[id];
    const v = taskView(id);
    const sc = $("screen");
    if (!p) { sc.replaceChildren(); return; }
    const info = el("div", { class: "infobox" }, "Solve this task on host ", el("b", { text: p.text.host }), ": ", el("code", { text: p.text.ssh }));
    const paras = p.text.body.split(/\n\s*\n/).map((t) => el("p", {}, rich(t.trim())));
    const attempts = v && v.attempts ? v.attempts + " check" + (v.attempts === 1 ? "" : "s") + " this session" : "";
    const check = el("button", { class: "check", id: "btn-check", text: "Check", onclick: () => doCheck(id) });
    check.disabled = busy;
    const kids = [info, el("div", { class: "task-text" }, ...paras), el("div", { class: "checkrow" }, check, el("span", { class: "attempts", id: "attempts", text: attempts }))];
    const ver = verdicts[id] || (p.last_output ? { verdict: v && v.status !== "failed" ? v.status : "failed", message: null, output: p.last_output, restored: true } : null);
    if (ver) kids.push(verdictBox(ver));
    sc.replaceChildren(...kids);
  }
  function verdictBox(r) {
    const head = {
      passed_in_time: "Passed. This counts.",
      passed_over_time: "Passed over time. This does not count: redo it within 7.5 minutes in a later session.",
      failed: "Not passed yet.",
    }[r.verdict] || r.verdict;
    return el("div", { class: "verdict v-" + r.verdict, id: "verdict" },
      el("div", { class: "head", text: head }),
      el("pre", { text: r.output && r.output.trim() ? r.output.trim() : "(the validator printed nothing)" }));
  }

  function busyScreen(msg) {
    $("screen").replaceChildren(el("div", { class: "busy" }, el("span", { class: "spin" }), msg));
  }
  function errorBox(msg) {
    $("screen").prepend(el("div", { class: "err", text: msg }));
  }

  function render() {
    syncMode();
    renderModes();
    if (mode === "drill") { renderDrill(); return; }
    renderChrome();
    const s = sess();
    if (!s) { renderStart(); paintTimer(); return; }
    if (s.ended) { renderSummary(); paintTimer(); return; }
    if (current && payload[current] && !busy) renderTask(current);
    paintTimer();
  }

  // ------------------------------------------------------------------ actions
  async function refresh() {
    S = await api("/api/state");
    const s = sess();
    if (!s) { current = null; snap = null; }
    else if (s.ended) { current = null; snap = null; }
    else if (!current || !taskView(current)) current = s.current && taskView(s.current) ? s.current : null;
  }

  async function startSession(mode) {
    if (live() && !window.confirm("A session is running. Start a new one and discard the current task environments?")) return;
    busy = true; renderChrome();
    busyScreen("Resetting the exam hosts and clearing old namespaces...");
    try {
      const r = await api("/api/session/start", { mode });
      payload = {}; verdicts = {}; current = null; snap = null;
      await refresh();
      busy = false;
      if (r.warnings && r.warnings.length) window.alert(r.warnings.join("\n"));
      if (live()) { await gotoTask(sess().tasks[0].id); return; }
    } catch (e) {
      busy = false; await refresh().catch(() => {}); render(); errorBox(String(e.message || e)); return;
    }
    busy = false; render();
  }

  async function gotoTask(id) {
    if (!live() || busy) return;
    const first = !taskView(id).deployed;
    busy = true; current = id; renderChrome();
    if (first) busyScreen("Preparing the environment for this task. This can take up to a minute...");
    try {
      const p = await api("/api/task/open", { id });
      payload[id] = p;
      busy = false;
      await refresh();
      current = id;
      setSnap(taskView(id));
      render();
    } catch (e) {
      busy = false;
      await refresh().catch(() => {});
      current = null; render();
      errorBox(String(e.message || e));
    }
  }

  async function doCheck(id) {
    if (busy || !live()) return;
    busy = true; renderChrome();
    const b = $("btn-check"); if (b) { b.disabled = true; b.textContent = "Checking..."; }
    try {
      const r = await api("/api/task/check", { id });
      verdicts[id] = r;
      busy = false;
      await refresh(); current = id;
      setSnap(r.task);
      render();
    } catch (e) {
      busy = false; render(); errorBox(String(e.message || e));
    }
  }

  async function toggleFlag() {
    const v = taskView(current);
    if (!v || busy) return;
    await api("/api/task/flag", { id: current, flagged: !v.flagged });
    await refresh(); render();
  }

  async function satisfiedNext() {
    const tasks = sess().tasks;
    const i = tasks.findIndex((t) => t.id === current);
    if (i < tasks.length - 1) gotoTask(tasks[i + 1].id);
    else endExam();
  }

  function modal(title, text, okLabel, onOk) {
    const bg = el("div", { class: "modal-bg" });
    const close = () => bg.remove();
    bg.append(el("div", { class: "modal" }, el("h3", { text: title }), el("div", { text }),
      el("div", { class: "btns" },
        el("button", { text: "Cancel", onclick: close }),
        el("button", { class: "danger", id: "modal-ok", text: okLabel, onclick: () => { close(); onOk(); } }))));
    document.body.append(bg);
  }
  function endExam() {
    modal("End exam", "End this session now? The clocks stop and the summary is shown. Task namespaces stay until the next session starts.", "End exam", async () => {
      try { await api("/api/session/end", {}); } catch (e) { window.alert(e.message); }
      await refresh(); render();
    });
  }


  // ------------------------------------------------------------------ drill mode
  const DBADGE = { not_tried: "b-not_opened", opened: "b-opened", solved: "b-passed_in_time", failed_in_exam: "b-failed" };

  function setMode(m) {
    mode = m;
    try { localStorage.setItem("cka-mode", m); } catch (e) { /* storage unavailable */ }
  }
  // an exam session that is live forces Mock exam mode (the server refuses drill requests then as well)
  function syncMode() {
    if (live() && mode !== "exam") setMode("exam");
    applyChrome();
  }
  // the single place that decides which mode's chrome is visible: `hidden` on every exam-only / drill-only element
  function applyChrome() {
    const drill = mode === "drill";
    document.body.classList.toggle("drill-mode", drill);
    for (const id of ["timerbar", "taskbar", "actions", "btn-end", "readme-exam"]) $(id).hidden = drill;
    for (const id of ["drillbar", "readme-drill"]) $(id).hidden = !drill;
    for (const id of ["drill-taskbar", "drill-actions"]) $(id).hidden = !drill || !dcur;
  }
  function renderModes() {
    const locked = live();
    const bd = $("mode-drill"), be = $("mode-exam");
    bd.classList.toggle("on", mode === "drill");
    be.classList.toggle("on", mode === "exam");
    bd.disabled = locked;
    bd.textContent = locked ? "\u{1F512} Drill" : "Drill";
    const tip = locked ? "End the exam to switch to Drill" : "";
    bd.title = tip;
    $("modes").title = tip;
  }
  async function switchMode(m) {
    if (m === mode) return;
    if (m === "drill") {
      if (live()) return;
      try { await refreshDrill(); } catch (e) { /* the picker shows the error */ }
      setMode("drill");
      dcur = null;
      render();
      if (!D) errorBox("Cannot load Drill state.");
    } else {
      setMode("exam");
      render();
      if (live() && current && !payload[current]) gotoTask(current);
    }
  }

  async function refreshDrill() {
    D = await api("/api/drill/state");
    if (D.exam_live) { await refresh(); }
    return D;
  }
  const dTask = (id) => (D ? D.tasks.find((t) => t.id === id) : null);
  const isKubeadm = (id) => { const t = dTask(id); return !!t && t.cluster === "kubeadm"; };

  function renderDrill() {
    const side = $("drill-side");
    if (D) {
      const solved = D.tasks.filter((t) => t.solved).length;
      side.textContent = solved + " of " + D.tasks.length + " solved";
    } else side.textContent = "";
    applyChrome();
    if (!D) { $("screen").replaceChildren(el("div", { class: "busy" }, "Loading...")); return; }
    if (dcur && dpay[dcur]) renderDrillTask(dcur); else renderPicker();
  }

  function renderPicker() {
    const pct = (a, b) => (b ? Math.round((100 * a) / b) : 0);
    const chips = [["all", "All"], ["unsolved", "Not solved"], ["failed", "Failed in an exam"]].map(([k, label]) =>
      el("button", { class: dfilter === k ? "on" : "", text: label, onclick: () => { dfilter = k; renderDrill(); } }));
    const groups = ["domain", "pattern"].map((k) =>
      el("button", { class: dgroup === k ? "on" : "", text: k === "domain" ? "By domain" : "By pattern", onclick: () => {
        dgroup = k;
        try { localStorage.setItem("cka-drill-group", k); } catch (e) { /* storage unavailable */ }
        renderDrill();
      } }));
    const kids = [el("div", { class: "filter groupsw" }, ...groups), el("div", { class: "filter" }, ...chips)];
    const keep = (t) => (dfilter === "unsolved" ? !t.solved : dfilter === "failed" ? t.failed_in_exam : true);
    let shown = 0;
    const sections = dgroup === "pattern"
      ? [...(D.patterns || []).map((p) => [p.name, D.tasks.filter((t) => t.pattern === p.id)]),
         ["Scenario tasks (no single command)", D.tasks.filter((t) => !t.pattern)]]
      : D.domains.map((dom) => [dom.name, D.tasks.filter((t) => t.domain === dom.name)]);
    for (const [name, all] of sections) {
      if (!all.length) continue;
      const rows = all.filter(keep);
      shown += rows.length;
      if (!rows.length) continue;
      const solved = all.filter((t) => t.solved).length;
      kids.push(el("div", { class: "dom-h" }, el("span", { text: name }),
        el("small", { text: solved + " of " + all.length + " solved · " + pct(solved, all.length) + "%" })));
      for (const t of rows) {
        kids.push(el("div", { class: "trow", role: "button", tabindex: "0", onclick: () => openDrill(t.id) },
          el("span", { class: "id", text: t.id }),
          el("span", { class: "nm" }, rich(t.title)),
          el("span", { class: "badge " + DBADGE[t.status], text: t.status_label })));
      }
    }
    if (!shown) kids.push(el("p", { class: "attempts", text: "No tasks match this filter." }));
    $("screen").replaceChildren(...kids);
  }

  function nextInDomain(id) {
    const t = dTask(id);
    if (!t) return null;
    // follows the picker's grouping: same pattern group in pattern view, same domain otherwise
    const same = D.tasks.filter((x) => (dgroup === "pattern" ? (x.pattern || null) === (t.pattern || null) : x.domain === t.domain));
    const i = same.findIndex((x) => x.id === id);
    return i >= 0 && i < same.length - 1 ? same[i + 1].id : null;
  }

  function paragraphs(text) {
    return text.split(/\n\s*\n/).map((t) => el("p", {}, rich(t.trim())));
  }

  function renderDrillTask(id) {
    const p = dpay[id];
    const info = el("div", { class: "infobox" }, "Solve this task on host ", el("b", { text: p.text.host }), ": ", el("code", { text: p.text.ssh }));
    const check = el("button", { class: "check", id: "btn-check", text: dbusy ? "Working..." : "Check", onclick: () => drillCheck(id) });
    check.disabled = dbusy;
    const attempts = p.attempts ? p.attempts + " check" + (p.attempts === 1 ? "" : "s") : "";
    const kids = [info, el("div", { class: "task-text" }, ...paragraphs(p.text.body)),
      el("div", { class: "checkrow" }, check, el("span", { class: "attempts", id: "attempts", text: attempts }))];
    if (p.notice) kids.splice(1, 0, el("div", { class: "infobox", id: "drill-notice", text: p.notice }));
    if (p.last_passed !== null && p.last_passed !== undefined) {
      const out = p.output_withheld ? "Press Hint 3 to also see the checker's output."
        : (p.last_output && p.last_output.trim() ? p.last_output.trim() : "(the validator printed nothing)");
      kids.push(el("div", { class: "verdict v-" + (p.last_passed ? "passed" : "failed"), id: "verdict" },
        el("div", { class: "head", text: p.last_passed ? "Passed." : "Not passed yet." }),
        el("pre", { id: "verdict-out", text: out })));
    }
    // hint ladder: each button is enabled only after the previous one was revealed
    const labels = ["Hint 1", "Hint 2", "Hint 3", "Show solution"];
    const btns = labels.map((label, i) => {
      const n = i + 1;
      const used = p.hints_revealed >= n;
      const b = el("button", { class: (used ? "used " : "") + (n === 4 ? "danger-ish" : ""), id: "hint-" + n, text: label + (used ? " ✓" : "") });
      if (used) b.setAttribute("aria-disabled", "true");
      else { b.disabled = dbusy || n !== p.hints_revealed + 1; b.onclick = () => drillHint(id, n); }
      return b;
    });
    const hints = el("div", { class: "hints" }, el("h4", { text: "Stuck?" }), el("div", { class: "hintbtns" }, ...btns));
    p.hints.forEach((h, i) => hints.append(el("div", { class: "hintcard", id: "hintcard-" + (i + 1) }, el("div", { class: "hc-t", text: "Hint " + (i + 1) }), ...paragraphs(h))));
    if (p.solution) hints.append(el("div", { class: "hintcard", id: "solution" }, el("div", { class: "hc-t", text: "Solution" }), el("pre", { text: p.solution })));
    kids.push(hints);
    if (p.debrief) {
      const det = el("details", { class: "debrief", id: "debrief" }, el("summary", { text: "Debrief" }), el("pre", { text: p.debrief }));
      if (dopen[id]) det.open = true;
      det.addEventListener("toggle", () => { dopen[id] = det.open; });
      kids.push(det);
    }
    $("screen").replaceChildren(...kids);
    $("drill-crumb").replaceChildren(document.createTextNode(p.domain + " · "), el("b", { text: id }));
    const nx = nextInDomain(id);
    $("drill-next-arrow").disabled = dbusy || !nx;
    $("drill-back").disabled = dbusy;
    $("drill-reset").disabled = dbusy;
    $("drill-next").disabled = dbusy;
    paintDrillTime();
  }
  let dopen = {};          // drill task id -> debrief section expanded

  function paintDrillTime() {
    const side = $("drill-side");
    if (!D || !dcur || dstart[dcur] == null) return;
    side.textContent = fmt((performance.now() - dstart[dcur]) / 1000) + " on this task";
  }
  setInterval(() => { if (mode === "drill" && dcur) paintDrillTime(); }, 1000);

  async function drillCall(path, body, busyMsg) {
    dbusy = true;
    if (busyMsg) { $("screen").replaceChildren(el("div", { class: "busy" }, el("span", { class: "spin" }), busyMsg)); }
    else if (dcur) renderDrillTask(dcur);
    try {
      return await api(path, body);
    } finally {
      dbusy = false;
    }
  }
  async function drillFail(e) {
    // a 409 means an exam started somewhere else: resync, which locks Drill and shows the exam
    await refresh().catch(() => {});
    render();
    errorBox(String(e.message || e));
    if (live() && !payload[current || ""]) { const s = sess(); const id = current || (s.tasks.length ? s.tasks[0].id : null); if (id) gotoTask(id); }
  }

  async function openDrill(id) {
    if (dbusy) return;
    dcur = id; applyChrome();
    try {
      const p = await drillCall("/api/drill/open", { id }, isKubeadm(id) ? "Preparing the kubeadm cluster (a reset takes a few minutes)..." : (dpay[id] ? null : "Preparing the environment for this task. This can take up to a minute..."));
      dpay[id] = p;
      if (dstart[id] == null) dstart[id] = performance.now();
      await refreshDrill();
      render();
    } catch (e) { dcur = null; await drillFail(e); }
  }
  async function drillCheck(id) {
    try {
      const r = await drillCall("/api/drill/check", { id });
      dpay[id] = r;
      await refreshDrill();
      render();
    } catch (e) { await drillFail(e); }
  }
  async function drillHint(id, n) {
    try {
      dpay[id] = await drillCall("/api/drill/hint", { id, n });
      await refreshDrill();
      render();
    } catch (e) { await drillFail(e); }
  }
  function drillReset() {
    const id = dcur;
    if (!id || dbusy) return;
    modal("Reset task", isKubeadm(id) ? "Roll the kubeadm cluster back to its clean snapshot and rebuild the starting state? This takes a few minutes and undoes every change on both VMs. Attempts, solved and revealed hints are kept." : "Delete the namespace and rebuild the broken state? Your changes to this task's objects are lost. Attempts, solved and revealed hints are kept.", "Reset", async () => {
      try {
        dpay[id] = await drillCall("/api/drill/reset", { id }, isKubeadm(id) ? "Resetting the kubeadm cluster, this takes a few minutes..." : "Rebuilding the broken state...");
        dstart[id] = performance.now();
        await refreshDrill();
        render();
      } catch (e) { await drillFail(e); }
    });
  }
  function drillBack() { dcur = null; render(); }
  function drillNext() {
    const nx = dcur ? nextInDomain(dcur) : null;
    if (nx) openDrill(nx); else drillBack();
  }

  // ------------------------------------------------------------------ tabs, dividers, menus
  function showTab(name) {
    for (const t of ["readme", "desktop"]) {
      $("pane-" + t).hidden = t !== name;
      const b = $("tab-" + t);
      b.classList.toggle("active", t === name);
      b.setAttribute("aria-selected", String(t === name));
    }
    if (name === "desktop" && !desktopLoaded) { $("desktop").src = desktopUrl(); desktopLoaded = true; }
  }

  function setPanelWidth(px) {
    const w = Math.max(340, Math.min(px, window.innerWidth - 400));
    document.documentElement.style.setProperty("--panel-w", w + "px");
    try { localStorage.setItem("cka-panel-w", String(w)); } catch (e) { /* storage unavailable */ }
  }
  function initDivider() {
    try { const w = parseInt(localStorage.getItem("cka-panel-w"), 10); if (w) setPanelWidth(w); } catch (e) { /* ignore */ }
    const d = $("divider"), shield = $("drag-shield");
    d.addEventListener("mousedown", (ev) => {
      ev.preventDefault(); d.classList.add("drag"); shield.hidden = false;
      const move = (e) => setPanelWidth(e.clientX);
      const up = () => { d.classList.remove("drag"); shield.hidden = true; window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up); };
      window.addEventListener("mousemove", move); window.addEventListener("mouseup", up);
    });
  }

  function init() {
    initDivider();
    $("tab-readme").onclick = () => showTab("readme");
    $("tab-desktop").onclick = () => showTab("desktop");
    $("btn-help").onclick = () => showTab("readme");
    $("btn-end").onclick = endExam;
    $("mode-drill").onclick = () => switchMode("drill");
    $("mode-exam").onclick = () => switchMode("exam");
    $("drill-back").onclick = drillBack;
    $("drill-next").onclick = drillNext;
    $("drill-next-arrow").onclick = drillNext;
    $("drill-reset").onclick = drillReset;
    $("btn-flag").onclick = toggleFlag;
    $("btn-satisfied").onclick = satisfiedNext;
    $("btn-next-arrow").onclick = () => { const t = sess().tasks; const i = t.findIndex((x) => x.id === current); if (i < t.length - 1) gotoTask(t[i + 1].id); };
    $("task-select").onclick = (e) => { e.stopPropagation(); $("task-list").hidden = !$("task-list").hidden; $("cog-menu").hidden = true; };
    $("btn-cog").onclick = (e) => { e.stopPropagation(); $("cog-menu").hidden = !$("cog-menu").hidden; hideList(); };
    $("cog-menu").onclick = (e) => {
      const act = e.target.getAttribute("data-act");
      if (act === "reset-width") setPanelWidth(480);
      if (act === "reload-desktop") { $("desktop").src = desktopUrl(); desktopLoaded = true; }
      if (act === "open-desktop") window.open(desktopUrl(), "_blank");
      $("cog-menu").hidden = true;
    };
    document.addEventListener("click", () => { hideList(); $("cog-menu").hidden = true; });

    // visibility drives the clock: hidden page -> hide event, visible -> show again
    function warn(msg) {
      const w = $("sync-warn");
      w.textContent = msg || "";
      w.hidden = !msg;
    }
    // ask the server to run the shown task's clock; a failure is shown, never swallowed
    async function sendShow() {
      try { const tv = await api("/api/task/event", { id: current, state: "show" }); setSnap(tv); warn(""); return tv; }
      catch (e) { warn("The timer could not be resumed: " + (e.message || e)); return null; }
    }
    document.addEventListener("visibilitychange", () => {
      if (!live() || !current || busy) return;
      const v = taskView(current);
      if (!v || !v.deployed) return;
      if (document.visibilityState === "hidden") { fire("/api/task/event", { id: current, state: "hide" }); if (snap) { snap.remaining -= (performance.now() - snap.at) / 1000; snap.running = false; } }
      else sendShow();
    });
    window.addEventListener("pagehide", () => { if (live() && current) fire("/api/task/event", { id: current, state: "hide" }); });
    setInterval(async () => {
      if (!live() || !current || busy || document.visibilityState !== "visible") return;
      const v = taskView(current);
      if (!v || !v.deployed) return;
      try {
        let tv = await api("/api/task/event", { id: current, state: "beat" });
        // the server says the clock is stopped although the page is visible: ask it to run again
        if (!tv.running && document.visibilityState === "visible") { const r = await sendShow(); if (r) tv = r; }
        else warn("");
        setSnap(tv);
      } catch (e) { warn("Cannot reach the exam server: " + (e.message || e)); }
    }, BEAT_MS);

    refresh().then(async () => {
      syncMode();
      if (mode === "drill") { try { await refreshDrill(); } catch (e) { /* picker shows loading error */ } }
      render();
      if (mode === "drill") return;
      if (live() && current) { await gotoTask(current); }
      else if (live() && sess().tasks.length) { await gotoTask(sess().tasks[0].id); }
    }).catch((e) => { $("screen").replaceChildren(el("div", { class: "err", text: "Cannot reach the exam server: " + e.message })); });
  }
  init();
})();
