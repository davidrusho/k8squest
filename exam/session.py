"""One exam session: its 16 tasks, per-task clocks, attempts, flags. Pure state, no I/O."""
import secrets
import time
from datetime import datetime, timezone

import timing
from timing import BUDGET_SECONDS, SessionClocks, TaskClock, in_time

HOSTS = ("cka1", "cka2", "cka3")

STATUS_LABELS = {
    "not_opened": "not opened",
    "opened": "opened, not checked",
    "flagged": "flagged",
    "passed_in_time": "passed in time",
    "passed_over_time": "passed over time",
    "failed": "failed",
}


def iso(now=None):
    return datetime.fromtimestamp(now if now is not None else time.time(), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def host_for(n):
    return HOSTS[(n - 1) % len(HOSTS)]


class Session:
    def __init__(self, sid, mode, tasks, started):
        self.id = sid
        self.mode = mode
        self.started = started
        self.ended = None
        # tasks: ordered list of {"n","id","host","deployed","opened","flagged","attempts":[...]}
        self.tasks = tasks
        self.clocks = SessionClocks()

    @classmethod
    def create(cls, pool_tasks, mode, now):
        sid = datetime.fromtimestamp(now, timezone.utc).strftime("s%Y%m%d-%H%M%S") + "-" + secrets.token_hex(2)
        tasks = [{"n": i, "id": t["id"], "host": host_for(i), "deployed": False, "opened": False,
                  "flagged": False, "attempts": []} for i, t in enumerate(pool_tasks, 1)]
        return cls(sid, mode, tasks, now)

    def get(self, tid):
        for t in self.tasks:
            if t["id"] == tid:
                return t
        raise KeyError(tid)

    # ---- clocks
    def show(self, tid, now):
        self.get(tid)["opened"] = True
        self.clocks.show(tid, now)

    def hide(self, now, tid=None):
        self.clocks.hide(now, tid)

    def beat(self, tid, now):
        self.clocks.beat(tid, now)

    def elapsed(self, tid, now):
        return self.clocks.elapsed(tid, now)

    def remaining(self, tid, now):
        return BUDGET_SECONDS - self.elapsed(tid, now)

    # ---- grading
    def record_attempt(self, tid, passed, output, now, elapsed=None):
        """Record a Check. `elapsed` is the clock as sampled when the request arrived (a slow validator
        must not push a pass over the budget); default: the clock at `now`."""
        el = self.elapsed(tid, now) if elapsed is None else elapsed
        it = in_time(el)
        t = self.get(tid)
        a = {"elapsed": round(el, 1), "passed": bool(passed), "in_time": bool(passed and it),
             "output": output, "ts": iso(now)}
        t["attempts"].append(a)
        return a

    def status(self, tid):
        t = self.get(tid)
        att = t["attempts"]
        if any(a["passed"] and a["in_time"] for a in att):
            return "passed_in_time"
        if any(a["passed"] for a in att):
            return "passed_over_time"
        if att:
            return "failed"
        if t["flagged"]:
            return "flagged"
        return "opened" if t["opened"] else "not_opened"

    # ---- end of exam
    def end(self, now):
        if self.ended is None:
            self.clocks.stop_all(now)
            self.ended = now

    def summary(self):
        counted = [t["id"] for t in self.tasks if self.status(t["id"]) == "passed_in_time"]
        over = [t["id"] for t in self.tasks if self.status(t["id"]) == "passed_over_time"]
        missed = [t["id"] for t in self.tasks if t["id"] not in counted and t["id"] not in over]
        return {"counted": counted, "passed_over_time": over, "missed": missed, "total": len(self.tasks)}

    # ---- persistence
    def to_dict(self):
        return {"id": self.id, "mode": self.mode, "started": self.started, "ended": self.ended,
                "tasks": self.tasks,
                "clocks": {k: c.to_dict() for k, c in self.clocks.clocks.items()},
                "current": self.clocks.current, "hidden": self.clocks.hidden}

    @classmethod
    def from_dict(cls, d):
        s = cls(d["id"], d["mode"], d["tasks"], d["started"])
        s.ended = d.get("ended")
        for k, c in d.get("clocks", {}).items():
            s.clocks.clocks[k] = TaskClock.from_dict(c)
        s.clocks.current = d.get("current")
        s.clocks.hidden = bool(d.get("hidden", False))
        # a server restart ends any running spell at its last heartbeat (+grace)
        for c in s.clocks.clocks.values():
            c.stop(c.last_beat if c.last_beat is not None else (c.running_since or 0))
        return s
