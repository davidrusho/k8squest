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
STALE_NODE = "The node no longer holds this task's setup. Press Reset task, then redo it."
DIRTY = "?"                       # node_owner value: the node may hold changes nobody owns
NODE_CLEARED = "The node held another task's changes; it was reset before this check."
NODE_REBUILT = "This task's node setup was rebuilt, because the node was reset since you last worked on it."
NODE_UNDONE = "Node changes from this task were undone."


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
        self.data.setdefault("node_epoch", 0)     # bumped every time the shared node is reset
        self.data.setdefault("node_owner", None)  # the node_dependent task whose setup the node holds, or None
        self.busy = set()
        self.node_lock = threading.Lock()         # serialises every node-touching sequence; never taken while holding self.lock

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
        r.setdefault("notice", None)
        return r

    def _save(self):
        self.file.save(self.data)

    def guard(self):
        with self.lock:
            live = self.exam_live()
        if live:
            raise Locked("An exam session is running. End the exam to use Drill.")

    def _task(self, tid):
        if tid not in pool.DRILL_BY_ID:
            raise KeyError(tid)
        return pool.DRILL_BY_ID[tid]

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
        t = pool.DRILL_BY_ID[tid]
        r = self._rec(tid)
        st, label = self._status(r, tid)
        return {"id": tid, "domain": t["domain"], "title": pool.drill_title(t), "status": st, "status_label": label,
                "pattern": t.get("pattern"), "source": t.get("source", "exam"),
                "failed_in_exam": self._failed_in_exam(tid), "opened": r["opened"], "deployed": r["deployed"],
                "attempts": r["attempts"], "solved": r["solved"], "solved_at": r["solved_at"],
                "hints_revealed": r["hints_revealed"], "last_output": self._shown(r, r["last_output"]),
                "output_withheld": r["last_output"] is not None and self._shown(r, r["last_output"]) is None,
                "last_passed": r["last_passed"], "notice": r.get("notice")}

    def _texts(self, tid):
        """Everything revealed so far: hints (list of strings), solution, debrief (None until earned)."""
        t, r = pool.DRILL_BY_ID[tid], self._rec(tid)
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
        v.update({"text": pool.render_text(pool.DRILL_BY_ID[tid], host, KIND), "namespace": pool.namespace(tid, KIND)})
        return v

    # ---- API
    def state(self):
        with self.lock:
            live = bool(self.exam_live())
            used = {t.get("pattern") for t in pool.DRILL_POOL}
            return {"exam_live": live,
                    "domains": [{"name": d, "weight": w} for d, w in sorted(DOMAIN_WEIGHTS.items(), key=lambda kv: -kv[1])],
                    "patterns": [p for p in pool.PATTERNS if p["id"] in used],
                    "tasks": [self._view(t["id"]) for t in pool.DRILL_POOL]}

    @staticmethod
    def _warn_text(warns):
        return "Node reset warning: " + "; ".join(warns) if warns else ""

    def _set_node(self, owner, bump=False):
        with self.lock:
            if bump:
                self.data["node_epoch"] = self.data.get("node_epoch", 0) + 1
            self.data["node_owner"] = owner
            self._save()
            return self.data["node_epoch"]

    def _reset_node(self):
        """Reset the shared node (labels, taints, cordon), bump the node epoch and clear the owner. The caller holds
        node_lock. The epoch bump and DIRTY ("?") are persisted BEFORE the kubectl work, so a crash in the middle leaves
        the node marked unknown; the owner becomes None only when the reset finished without warnings.
        Returns (warnings, new epoch)."""
        epoch = self._set_node(DIRTY, bump=True)
        warns = levels.reset_node_state(self.cluster.run)
        if not warns:
            self._set_node(None)
        return warns, epoch

    def node_mark_dirty(self):
        """An exam start is about to reset the node: bump the epoch and mark the node unknown first."""
        with self.node_lock:
            self._set_node(DIRTY, bump=True)

    def node_mark_clean(self):
        """The exam start's node reset finished without warnings."""
        with self.node_lock:
            self._set_node(None)

    def _deploy(self, t):
        """Fresh broken state in the drill namespace. First clears the same task's exam leftovers (t22's node port and
        t30's ClusterIP are cluster-global), then resets node labels, taints and cordons like an exam start does, for EVERY
        task: a node change left by an abandoned task must not leak into the next one. The whole sequence runs under
        node_lock, so two deploys cannot interleave their reset and setup. Returns (ok, message, reset warnings, node
        epoch at the reset)."""
        tid = t["id"]
        with self.node_lock:
            self.guard()             # deploys are slow: re-check before EACH cluster step that no exam went live meanwhile
            self.cluster.delete_task_objects(pool.namespace(tid, "exam"), pool.cluster_objects_for(t, "exam"))
            self.guard()
            warns, epoch = self._reset_node()
            self._set_node(DIRTY)       # the setup may half-change the node
            self.guard()
            ok, msg = self.cluster.deploy(t["level"], pool.namespace(tid, KIND), pool.renames_for(t, KIND),
                                          pool.cluster_objects_for(t, KIND))
            if ok:
                self._set_node(tid if t.get("node_dependent") else None)    # a failed setup keeps DIRTY
            return ok, msg, warns, epoch

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
                ok, msg, warns, epoch = self._deploy(t)
                with self.lock:
                    locked = bool(self.exam_live())     # an exam started while the environment was being built
                if locked:
                    if ok:
                        self._discard_env(t)
                    raise Locked("An exam session is running. End the exam to use Drill.")
                if not ok:
                    raise RuntimeError("could not prepare the environment: " + (self._warn_text(warns) + " " if warns else "") + msg)
                with self.lock:
                    r["deployed"] = True
                    r["epoch"] = epoch
                    r["notice"] = self._warn_text(warns) or None
            finally:
                with self.lock:
                    self.busy.discard(tid)
        else:
            self._sync_node_on_open(t)
        with self.lock:
            self.guard()
            r["opened"] = True
            self._save()
            return self._payload(tid)

    def _sync_node_on_open(self, t):
        """Opening an already-deployed task. A node task whose setup was wiped is rebuilt; any other task is graded
        against a clean node, so the node is reset when a different task still owns it."""
        tid = t["id"]
        with self.node_lock:
            with self.lock:
                self.guard()
                r = self._rec(tid)
                owner = self.data.get("node_owner")
                stale = bool(t.get("node_dependent")) and (r.get("epoch") != self.data.get("node_epoch", 0) or owner != tid)
                clear = not stale and owner is not None and owner != tid
                if clear:
                    if tid in self.busy:
                        raise ValueError("a check or reset is already running")
                    self.busy.add(tid)
            if clear:
                try:
                    self.guard()
                    warns, _ = self._reset_node()
                    if warns:
                        with self.lock:
                            r["notice"] = self._warn_text(warns)
                            self._save()
                finally:
                    with self.lock:
                        self.busy.discard(tid)
        if stale:
            self._rebuild(t, NODE_REBUILT)

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
            with self.node_lock:
                notice = None
                if t.get("node_dependent"):
                    with self.lock:
                        if self.data.get("node_owner") != tid or r.get("epoch") != self.data.get("node_epoch", 0):
                            raise Conflict(STALE_NODE)      # refused: the validator is not run and no attempt is counted
                else:
                    with self.lock:
                        foreign = self.data.get("node_owner") is not None      # another task's (or unknown) node changes
                    if foreign:
                        self.guard()
                        warns, _ = self._reset_node()
                        notice = NODE_CLEARED + ((" " + self._warn_text(warns)) if warns else "")
                self.guard()
                passed, out = self.cluster.validate(t["level"], pool.namespace(tid, KIND), pool.renames_for(t, KIND))
                if passed and t.get("node_dependent"):
                    # a node task changes the node the K8sQuest game shares: put it back, and say so
                    self.guard()
                    warns, _ = self._reset_node()
                    notice = NODE_UNDONE + ((" " + self._warn_text(warns)) if warns else "")
            out = _clean(out)
            with self.lock:
                self.guard()                          # the exam started during the check: discard, do not record
                if notice is not None:
                    r["notice"] = notice
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
        finally:
            with self.lock:
                self.busy.discard(tid)

    def hint(self, tid, n):
        if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= MAX_HINT:
            raise ValueError("n must be an integer from 1 to 4")
        with self.lock:
            self.guard()
            t = self._task(tid)
            r = self._rec(tid)
            if n > r["hints_revealed"] + 1:
                raise Conflict("Reveal the earlier hints first.")
            undo = False
            if n > r["hints_revealed"]:
                undo = n == MAX_HINT and bool(t.get("node_dependent"))
                if undo and tid in self.busy:
                    raise ValueError("a check or reset is already running")
                r["hints_revealed"] = n
                self._save()
            if not undo:
                return self._payload(tid)
            self.busy.add(tid)
        try:
            with self.node_lock:
                with self.lock:
                    owns = self.data.get("node_owner") == tid      # another task owns the node: not this task's to undo
                if owns:
                    self.guard()
                    warns, _ = self._reset_node()         # the solution was shown: do not leave the shared node changed
                    with self.lock:
                        r["notice"] = NODE_UNDONE + ((" " + self._warn_text(warns)) if warns else "")
                        self._save()
        finally:
            with self.lock:
                self.busy.discard(tid)
        with self.lock:
            return self._payload(tid)

    def reset(self, tid):
        """Fresh broken state: deploy() deletes the drill namespace and the task's drill-prefixed cluster-scoped
        objects, then rebuilds. attempts, solved and hints_revealed are kept."""
        with self.lock:
            self.guard()
            t = self._task(tid)
        self._rebuild(t)
        with self.lock:
            return self._payload(tid)

    def _rebuild(self, t, notice=None):
        tid = t["id"]
        with self.lock:
            self.guard()
            r = self._rec(tid)
            if tid in self.busy:
                raise ValueError("a check or reset is already running")
            self.busy.add(tid)
        try:
            ok, msg, warns, epoch = self._deploy(t)
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
                    raise RuntimeError("could not rebuild the environment: " + (self._warn_text(warns) + " " if warns else "") + msg)
                r["deployed"] = True
                r["epoch"] = epoch
                r["notice"] = ((notice + " ") if notice else "") + self._warn_text(warns) or None
                r["opened"] = True
                r["last_output"] = None
                r["last_passed"] = None
                self._save()
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
