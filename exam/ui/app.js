"use strict";
(function () {
  const $ = (id) => document.getElementById(id);
  const DESKTOP_URL = "http://localhost:6080/vnc.html?autoconnect=1&resize=scale";
  const BEAT_MS = 10000;
  const LABEL = {
    not_opened: "not opened", opened: "opened", flagged: "flagged",
    passed_in_time: "passed in time", passed_over_time: "passed over time", failed: "failed",
  };

  let S = null;            // last /api/state
  let current = null;      // id of the task shown
  let payload = {};        // task id -> last full task payload (text etc.)
  let verdicts = {};       // task id -> last check result shown
  let snap = null;         // timer snapshot {remaining, at, running}
  let busy = false;        // a deploy or check is in flight
  let desktopLoaded = false;

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

  // ------------------------------------------------------------------ tabs, dividers, menus
  function showTab(name) {
    for (const t of ["readme", "desktop"]) {
      $("pane-" + t).hidden = t !== name;
      const b = $("tab-" + t);
      b.classList.toggle("active", t === name);
      b.setAttribute("aria-selected", String(t === name));
    }
    if (name === "desktop" && !desktopLoaded) { $("desktop").src = DESKTOP_URL; desktopLoaded = true; }
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
    $("btn-flag").onclick = toggleFlag;
    $("btn-satisfied").onclick = satisfiedNext;
    $("btn-next-arrow").onclick = () => { const t = sess().tasks; const i = t.findIndex((x) => x.id === current); if (i < t.length - 1) gotoTask(t[i + 1].id); };
    $("task-select").onclick = (e) => { e.stopPropagation(); $("task-list").hidden = !$("task-list").hidden; $("cog-menu").hidden = true; };
    $("btn-cog").onclick = (e) => { e.stopPropagation(); $("cog-menu").hidden = !$("cog-menu").hidden; hideList(); };
    $("cog-menu").onclick = (e) => {
      const act = e.target.getAttribute("data-act");
      if (act === "reset-width") setPanelWidth(480);
      if (act === "reload-desktop") { $("desktop").src = DESKTOP_URL; desktopLoaded = true; }
      if (act === "open-desktop") window.open(DESKTOP_URL, "_blank");
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
      render();
      if (live() && current) { await gotoTask(current); }
      else if (live() && sess().tasks.length) { await gotoTask(sess().tasks[0].id); }
    }).catch((e) => { $("screen").replaceChildren(el("div", { class: "err", text: "Cannot reach the exam server: " + e.message })); });
  }
  init();
})();
