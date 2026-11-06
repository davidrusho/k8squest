#!/usr/bin/env python3
"""CKA exam practice server. Python 3 standard library only. Binds 127.0.0.1:6081.

Serves the UI in ui/ and a JSON API (all POST bodies are JSON):
  GET  /api/state                    current session (or null) + persistent per-task status
  POST /api/session/start  {mode}    mode: "weighted" | "missed"; resets hosts, removes exam-* namespaces
  POST /api/task/open      {id}      first open in a session deploys the broken state
  POST /api/task/event     {id, state: "show"|"hide"|"beat"}   visibility / heartbeat events
  POST /api/task/check     {id}      run the validator, record the attempt
  POST /api/task/flag      {id, flagged}
  POST /api/session/end
"""
import json
import mimetypes
import os
import re
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import levels  # noqa: E402
import pool  # noqa: E402
import selection  # noqa: E402
import timing  # noqa: E402
from session import STATUS_LABELS, Session  # noqa: E402
from store import Results, SessionFile  # noqa: E402

HOST, PORT = "127.0.0.1", int(os.environ.get("EXAM_PORT", "6081"))
UI_DIR = Path(__file__).resolve().parent / "ui"
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
HOSTS_RESET = ["sudo", "-n", "/usr/local/sbin/cka-hosts-reset"]
OUTPUT_CAP = 4000


class Exam:
    """All mutable state behind one lock. Slow cluster work (deploy, validate) runs outside it."""

    def __init__(self, results=None, sessionfile=None, now=time.time, cluster=levels, do_reset=True):
        self.lock = threading.RLock()
        self.now = now
        self.cluster = cluster
        self.do_reset = do_reset
        self.results = results or Results()
        self.sessionfile = sessionfile or SessionFile()
        self.session = self._load_session()
        self.busy = set()

    # ---- helpers
    def _load_session(self):
        """The persisted session, or None when it is unreadable or names a task that left the pool."""
        d = self.sessionfile.load()
        if not isinstance(d, dict):
            return None
        try:
            sess = Session.from_dict(d)
        except (KeyError, TypeError, ValueError, AttributeError):
            return None
        if any(t.get("id") not in pool.BY_ID for t in sess.tasks):
            return None
        return sess

    def _save(self):
        if self.session:
            self.sessionfile.save(self.session.to_dict())

    def _task_view(self, st):
        s = self.session
        now = self.now()
        tid = st["id"]
        status = s.status(tid)
        return {"n": st["n"], "id": tid, "host": st["host"], "domain": pool.BY_ID[tid]["domain"],
                "status": status, "status_label": STATUS_LABELS[status], "flagged": st["flagged"],
                "ever_counted": self.results.counted(tid), "attempts": len(st["attempts"]),
                "elapsed": round(s.elapsed(tid, now), 1), "remaining": round(s.remaining(tid, now), 1),
                "deployed": st["deployed"], "running": s.clocks.clock(tid).running}

    def state(self):
        with self.lock:
            s = self.session
            out = {"budget": timing.BUDGET_SECONDS, "pool_size": len(pool.POOL),
                   "counted_ever": len(self.results.counted_ids()), "session": None}
            if s:
                out["session"] = {"id": s.id, "mode": s.mode, "ended": s.ended is not None,
                                  "current": s.clocks.current,
                                  "tasks": [self._task_view(t) for t in s.tasks],
                                  "summary": s.summary() if s.ended else None}
                if s.ended:
                    out["session"]["summary_detail"] = self._summary_detail()
            return out

    def _summary_detail(self):
        s = self.session
        sm = s.summary()
        n = {t["id"]: t["n"] for t in s.tasks}
        f = lambda ids: [{"id": i, "n": n[i], "domain": pool.BY_ID[i]["domain"]} for i in ids]
        return {k: f(sm[k]) for k in ("counted", "passed_over_time", "missed")}

    # ---- session
    def start(self, mode):
        if mode not in ("weighted", "missed"):
            raise ValueError("mode must be weighted or missed")
        warnings = []
        with self.lock:
            if self.session and not self.session.ended:
                self.session.end(self.now())
            tasks = selection.select_session(pool.POOL, self.results.counted_ids(), mode)
            sess = Session.create(tasks, mode, self.now())
        if self.do_reset:
            r = self.cluster.run(HOSTS_RESET, timeout=60)
            if r.returncode:
                warnings.append("cka-hosts-reset failed: " + (r.stderr or r.stdout).strip()[-200:])
        warnings += self._remove_exam_namespaces()
        warnings += levels.reset_node_state(self.cluster.run)
        with self.lock:
            self.session = sess
            self._save()
        return {"warnings": warnings}

    def _remove_exam_namespaces(self):
        warn = []
        r = self.cluster.run(["kubectl", "get", "ns", "-o", "name"], timeout=30)
        if r.returncode:
            warn.append("could not list namespaces: " + (r.stderr or r.stdout).strip()[-200:])
        names = [n.split("/", 1)[1] for n in r.stdout.split() if n.startswith("namespace/exam-")]
        for ns in names:
            r = self.cluster.run(["kubectl", "delete", "namespace", ns, "--wait=false", "--ignore-not-found"], timeout=60)
            if r.returncode:
                warn.append(f"could not delete namespace {ns}: " + (r.stderr or r.stdout).strip()[-200:])
        for t in pool.POOL:
            for obj in t.get("cluster_objects", ()):
                r = self.cluster.run(["kubectl", "delete", obj, "--ignore-not-found", "--wait=false"], timeout=60)
                if r.returncode:
                    warn.append(f"could not delete {obj}: " + (r.stderr or r.stdout).strip()[-200:])
        return warn

    def end(self):
        with self.lock:
            if not self.session:
                raise ValueError("no session")
            self.session.end(self.now())
            self._save()

    # ---- tasks
    def _live(self, tid):
        if not self.session or self.session.ended:
            raise ValueError("no running session")
        self.session.get(tid)

    def open_task(self, tid):
        with self.lock:
            self._live(tid)
            sid = self.session.id
            st = self.session.get(tid)
            need_deploy = not st["deployed"]
            if need_deploy and tid in self.busy:
                raise ValueError("task is being prepared")
            if need_deploy:
                self.busy.add(tid)
        err = None
        if need_deploy:
            # no clock runs while the environment is prepared
            try:
                with self.lock:
                    self.session.hide(self.now())
                t = pool.BY_ID[tid]
                ok, msg = self.cluster.deploy(t["level"], pool.namespace(tid), t.get("renames", {}),
                                              t.get("cluster_objects", ()))
                err = None if ok else msg
            finally:
                with self.lock:
                    self.busy.discard(tid)
        with self.lock:
            if not self.session or self.session.id != sid or self.session.ended:
                raise ValueError("the session changed while the task was being prepared")
            if err is None:
                st["deployed"] = True
                self.session.show(tid, self.now())
            self._save()
            if err:
                raise RuntimeError("could not prepare the environment: " + err)
            return self.task_payload(tid)

    def task_payload(self, tid):
        st = self.session.get(tid)
        t = pool.BY_ID[tid]
        v = self._task_view(st)
        v.update({"text": pool.render_text(t, st["host"]), "host": st["host"],
                  "namespace": pool.namespace(tid),
                  "last_output": st["attempts"][-1]["output"] if st["attempts"] else None})
        v["total"] = len(self.session.tasks)
        return v

    def event(self, tid, state):
        with self.lock:
            self._live(tid)
            now = self.now()
            if state == "show":
                if not self.session.get(tid)["deployed"]:
                    raise ValueError("task not opened yet")
                self.session.show(tid, now)
            elif state == "hide":
                self.session.hide(now, tid)
            elif state == "beat":
                self.session.beat(tid, now)
            else:
                raise ValueError("bad state")
            self._save()
            return self._task_view(self.session.get(tid))

    def check(self, tid):
        with self.lock:
            self._live(tid)
            st = self.session.get(tid)
            if not st["deployed"]:
                raise ValueError("open the task first")
            if tid in self.busy:
                raise ValueError("a check is already running")
            self.busy.add(tid)
            # the clock is read when the request arrives: validators can sleep for many seconds
            sid = self.session.id
            asked_elapsed = self.session.elapsed(tid, self.now())
        try:
            t = pool.BY_ID[tid]
            passed, out = self.cluster.validate(t["level"], pool.namespace(tid), t.get("renames", {}))
        finally:
            with self.lock:
                self.busy.discard(tid)
        out = ANSI.sub("", out)[-OUTPUT_CAP:]
        with self.lock:
            if not self.session or self.session.id != sid or self.session.ended:
                raise ValueError("the session ended or changed while the check ran; the result was discarded")
            now = self.now()
            a = self.session.record_attempt(tid, passed, out, now, elapsed=asked_elapsed)
            self.results.record(tid, self.session.id, a["elapsed"], a["passed"], a["in_time"], a["ts"])
            self._save()
            if not passed:
                verdict = "failed"
                msg = "Not yet. The check did not pass."
            elif a["in_time"]:
                verdict = "passed_in_time"
                msg = "Passed within the time budget. This counts."
            else:
                verdict = "passed_over_time"
                msg = ("Passed over time. This does not count; redo it within %.1f minutes in a "
                       "later session." % (timing.BUDGET_SECONDS / 60))
            return {"verdict": verdict, "message": msg, "output": out, "task": self._task_view(st)}

    def flag(self, tid, flagged):
        if not isinstance(flagged, bool):
            raise ValueError("flagged must be true or false")
        with self.lock:
            self._live(tid)
            self.session.get(tid)["flagged"] = bool(flagged)
            self._save()
            return self._task_view(self.session.get(tid))


EXAM = None


MAX_BODY = 64 * 1024
# a tunnel that maps the server to another local port needs its origin listed here (comma separated)
EXTRA_ORIGINS = {o.strip() for o in os.environ.get("EXAM_EXTRA_ORIGINS", "").split(",") if o.strip()}


class Handler(BaseHTTPRequestHandler):
    server_version = "cka-exam"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.log_date_time_string(), fmt % args))

    def _allowed_origins(self):
        port = self.server.server_address[1]
        return {f"http://localhost:{port}", f"http://127.0.0.1:{port}"} | EXTRA_ORIGINS

    def _host_ok(self):
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        if host not in ("localhost", "127.0.0.1"):
            return False
        origin = self.headers.get("Origin")
        # a browser sends Origin on every cross-site request; curl and same-origin GETs may omit it
        return origin is None or origin in self._allowed_origins()

    def _send(self, code, body, ctype="application/json"):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _guard(self, fn):
        try:
            return fn()
        except Exception as e:  # never kill the page: answer JSON 500 and log
            sys.stderr.write("internal error: %r\n" % (e,))
            try:
                return self._send(500, {"error": "internal error: %s" % type(e).__name__})
            except OSError:
                return None

    def do_GET(self):
        self._guard(self._get)

    def do_POST(self):
        self._guard(self._post)

    def _get(self):
        if not self._host_ok():
            return self._send(403, {"error": "bad host or origin"})
        path = urlparse(self.path).path
        if path == "/api/state":
            return self._send(200, EXAM.state())
        rel = "index.html" if path == "/" else path.lstrip("/")
        f = (UI_DIR / rel).resolve()
        if UI_DIR.resolve() not in f.parents or not f.is_file():
            return self._send(404, {"error": "not found"})
        ctype = mimetypes.guess_type(str(f))[0] or "application/octet-stream"
        self._send(200, f.read_bytes(), ctype + ("; charset=utf-8" if ctype.startswith("text/") or "javascript" in ctype else ""))

    def _read_body(self):
        """Returns (dict, None) or (None, (status, message))."""
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None, (400, "bad Content-Length")
        if n < 0:
            return None, (400, "bad Content-Length")
        if n > MAX_BODY:
            return None, (413, "body too large")
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return None, (400, "bad json")
        if not isinstance(body, dict):
            return None, (400, "body must be a JSON object")
        return body, None

    def _post(self):
        if not self._host_ok():
            return self._send(403, {"error": "bad host or origin"})
        media = (self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if media != "application/json":
            return self._send(415, {"error": "Content-Type must be application/json"})
        body, err = self._read_body()
        if err:
            return self._send(err[0], {"error": err[1]})
        path = urlparse(self.path).path
        try:
            if path == "/api/session/start":
                return self._send(200, EXAM.start(body.get("mode", "weighted")))
            if path == "/api/session/end":
                EXAM.end()
                return self._send(200, EXAM.state())
            tid = body.get("id")
            if not isinstance(tid, str):
                return self._send(400, {"error": "id must be a string"})
            if path == "/api/task/open":
                return self._send(200, EXAM.open_task(tid))
            if path == "/api/task/event":
                return self._send(200, EXAM.event(tid, body.get("state")))
            if path == "/api/task/check":
                return self._send(200, EXAM.check(tid))
            if path == "/api/task/flag":
                return self._send(200, EXAM.flag(tid, body.get("flagged")))
            return self._send(404, {"error": "not found"})
        except KeyError:
            return self._send(404, {"error": "unknown task"})
        except ValueError as e:
            return self._send(400, {"error": str(e)})
        except RuntimeError as e:
            return self._send(502, {"error": str(e)})


def main():
    global EXAM
    levels.install_signal_cleanup()
    EXAM = Exam()
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"CKA exam server on http://{HOST}:{PORT}/  (pool: {len(pool.POOL)} tasks)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
