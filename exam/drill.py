"""Drill mode: untimed, one task at a time, with a hint ladder. Own state (drill.json), own namespaces (drill-<id>).

Completely separate from the mock exam: nothing here reads or writes session.json, and results.json is only
read (to mark tasks that failed in an exam). Every operation refuses with Locked while an exam session is live.
"""
import re
import threading
import time
from datetime import datetime, timezone

import levels
import pool
from selection import DOMAIN_WEIGHTS

KIND = "drill"
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
OUTPUT_CAP = 4000
MAX_HINT = 4                      # 1 to 3 are hints, 4 is the solution
HINT_MISSING = "(This level has no text for this step.)"


class Conflict(Exception):
    """The request is valid but not allowed in the current state (HTTP 409)."""


class Locked(Conflict):
    """An exam session is live."""


def _iso(now):
    return datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean(out):
    """ANSI stripped and capped. Not scrubbed: what the checker prints is gated behind the hint ladder instead."""
    return ANSI.sub("", out).strip()[-OUTPUT_CAP:]


class Drill:
    def __init__(self, drillfile, results, cluster, exam_live, now=time.time, lock=None):
        self.file = drillfile
        self.results = results
        self.cluster = cluster
        self.exam_live = exam_live          # callable -> bool; called with self.lock held by the owner
        self.now = now
        self.lock = lock or threading.RLock()     # the Exam's lock, so the live check and the state change are atomic
        self.data = drillfile.load()
        self.busy = set()

    # ---- helpers
    def _rec(self, tid):
        r = self.data["tasks"].setdefault(tid, {})
        r.setdefault("opened", False)
        r.setdefault("deployed", False)
        r.setdefault("attempts", 0)
        r.setdefault("solved", False)
        r.setdefault("solved_at", None)
        r.setdefault("hints_revealed", 0)
        r.setdefault("last_output", None)
        r.setdefault("last_passed", None)
        return r

    def _save(self):
        self.file.save(self.data)

    def guard(self):
        with self.lock:
            live = self.exam_live()
        if live:
            raise Locked("An exam session is running. End the exam to use Drill.")

    def _task(self, tid):
        if tid not in pool.BY_ID:
            raise KeyError(tid)
        return pool.BY_ID[tid]

    def _failed_in_exam(self, tid):
        att = self.results.attempts(tid)
        return bool(att) and not self.results.counted(tid)

    def _status(self, rec, tid):
        if rec["solved"]:
            return "solved", "solved"
        if self._failed_in_exam(tid):
            return "failed_in_exam", "failed in exam"
        if rec["opened"]:
            return "opened", "opened"
        return "not_tried", "not tried"

    @staticmethod
    def _shown(r, out):
        """The checker's output reaches the user only after Hint 3, or after a pass. The validators print
        what is wrong and often a "how to fix" block, which is solution-level, so Hint 1 and 2 must not unlock it."""
        return out if out is not None and (r["last_passed"] or r["hints_revealed"] >= 3) else None

    def _view(self, tid):
        t = pool.BY_ID[tid]
        r = self._rec(tid)
        st, label = self._status(r, tid)
        return {"id": tid, "domain": t["domain"], "title": pool.drill_title(t), "status": st, "status_label": label,
                "failed_in_exam": self._failed_in_exam(tid), "opened": r["opened"], "deployed": r["deployed"],
                "attempts": r["attempts"], "solved": r["solved"], "solved_at": r["solved_at"],
                "hints_revealed": r["hints_revealed"], "last_output": self._shown(r, r["last_output"]),
                "output_withheld": r["last_output"] is not None and self._shown(r, r["last_output"]) is None,
                "last_passed": r["last_passed"]}

    def _texts(self, tid):
        """Everything revealed so far: hints (list of strings), solution, debrief (None until earned)."""
        t, r = pool.BY_ID[tid], self._rec(tid)
        raw = levels.level_texts(t["level"], pool.namespace(tid, KIND), pool.renames_for(t, KIND))
        n = r["hints_revealed"]
        hints = [(raw["hints"][i] or HINT_MISSING) for i in range(min(n, 3))]
        solution = None
        if n >= 4:
            solution = raw["solution"] or HINT_MISSING
            extra = pool.solution_extra_text(t, KIND)
            if extra and raw["solution"]:
                solution += "\n\n# also run:\n" + "\n".join(extra)
        debrief = None
        if r["solved"] or n >= 4:
            debrief = raw["debrief"] or HINT_MISSING
        return {"hints": hints, "solution": solution, "debrief": debrief}

    def _payload(self, tid, host="cka1"):
        v = self._view(tid)
        v.update(self._texts(tid))
        v.update({"text": pool.render_text(pool.BY_ID[tid], host, KIND), "namespace": pool.namespace(tid, KIND)})
        return v

    # ---- API
    def state(self):
        with self.lock:
            live = bool(self.exam_live())
            return {"exam_live": live,
                    "domains": [{"name": d, "weight": w} for d, w in sorted(DOMAIN_WEIGHTS.items(), key=lambda kv: -kv[1])],
                    "tasks": [self._view(t["id"]) for t in pool.POOL]}

    def _deploy(self, t):
        """Fresh broken state in the drill namespace. First clears the same task's exam leftovers (t22's node port and
        t30's ClusterIP are cluster-global), and for tasks that change node state resets it like an exam start does."""
        tid = t["id"]
        self.guard()                 # deploys are slow: re-check before EACH cluster step that no exam went live meanwhile
        self.cluster.delete_task_objects(pool.namespace(tid, "exam"), pool.cluster_objects_for(t, "exam"))
        if t.get("node_reset"):
            self.guard()
            levels.reset_node_state(self.cluster.run)
        self.guard()
        return self.cluster.deploy(t["level"], pool.namespace(tid, KIND), pool.renames_for(t, KIND),
                                   pool.cluster_objects_for(t, KIND))

    def _discard_env(self, t):
        """An exam started while this task was being built: remove what was just made."""
        try:
            self.cluster.delete_task_objects(pool.namespace(t["id"], KIND), pool.cluster_objects_for(t, KIND))
        except Exception:      # the exam start sweeps drill-* as well
            pass

    def wait_idle(self, timeout):
        """Wait for in-flight drill operations to finish. True when idle, False on timeout."""
        end = time.monotonic() + timeout
        while True:
            with self.lock:
                if not self.busy:
                    return True
            if time.monotonic() >= end:
                return False
            time.sleep(0.1)

    def open(self, tid):
        with self.lock:
            self.guard()
            t = self._task(tid)
            r = self._rec(tid)
            need = not r["deployed"]
            if need:
                if tid in self.busy:
                    raise ValueError("task is being prepared")
                self.busy.add(tid)
        if need:
            try:
                ok, msg = self._deploy(t)
                with self.lock:
                    locked = bool(self.exam_live())     # an exam started while the environment was being built
                if locked:
                    if ok:
                        self._discard_env(t)
                    raise Locked("An exam session is running. End the exam to use Drill.")
                if not ok:
                    raise RuntimeError("could not prepare the environment: " + msg)
                with self.lock:
                    r["deployed"] = True
            finally:
                with self.lock:
                    self.busy.discard(tid)
        with self.lock:
            self.guard()
            r["opened"] = True
            self._save()
            return self._payload(tid)

    def check(self, tid):
        with self.lock:
            self.guard()
            t = self._task(tid)
            r = self._rec(tid)
            if not r["deployed"]:
                raise ValueError("open the task first")
            if tid in self.busy:
                raise ValueError("a check or reset is already running")
            self.busy.add(tid)
        try:
            passed, out = self.cluster.validate(t["level"], pool.namespace(tid, KIND), pool.renames_for(t, KIND))
        finally:
            with self.lock:
                self.busy.discard(tid)
        out = _clean(out)
        with self.lock:
            self.guard()                          # the exam started during the check: discard, do not record
            r["attempts"] += 1
            r["last_output"] = out
            r["last_passed"] = bool(passed)
            if passed:
                r["solved"] = True
                r["solved_at"] = r["solved_at"] or _iso(self.now())
            self._save()
            res = self._payload(tid)
            res.update({"verdict": "passed" if passed else "failed",
                        "message": "Passed." if passed else "Not passed yet.", "output": self._shown(r, out)})
            return res

    def hint(self, tid, n):
        if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= MAX_HINT:
            raise ValueError("n must be an integer from 1 to 4")
        with self.lock:
            self.guard()
            self._task(tid)
            r = self._rec(tid)
            if n > r["hints_revealed"] + 1:
                raise Conflict("Reveal the earlier hints first.")
            if n > r["hints_revealed"]:
                r["hints_revealed"] = n
                self._save()
            return self._payload(tid)

    def reset(self, tid):
        """Fresh broken state: deploy() deletes the drill namespace and the task's drill-prefixed cluster-scoped
        objects, then rebuilds. attempts, solved and hints_revealed are kept."""
        with self.lock:
            self.guard()
            t = self._task(tid)
            r = self._rec(tid)
            if tid in self.busy:
                raise ValueError("a check or reset is already running")
            self.busy.add(tid)
        try:
            ok, msg = self._deploy(t)
            with self.lock:
                locked = bool(self.exam_live())
            if locked:
                if ok:
                    self._discard_env(t)
                raise Locked("An exam session is running. End the exam to use Drill.")
            with self.lock:
                if not ok:
                    r["deployed"] = False
                    self._save()
                    raise RuntimeError("could not rebuild the environment: " + msg)
                r["deployed"] = True
                r["opened"] = True
                r["last_output"] = None
                r["last_passed"] = None
                self._save()
                return self._payload(tid)
        finally:
            with self.lock:
                self.busy.discard(tid)

    def clear_deployed(self):
        """An exam start removes every drill namespace: forget which tasks were deployed."""
        with self.lock:
            changed = False
            for r in self.data["tasks"].values():
                if r.get("deployed"):
                    r["deployed"] = False
                    changed = True
            if changed:
                self._save()
