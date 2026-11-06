"""Per-task clock and in-time accounting.

A task's clock runs only while that task is the one shown (and the page is visible). The UI posts
show / hide / heartbeat events; elapsed time is computed here, never trusted from the browser.
A clock that stops hearing heartbeats is capped at last_beat + GRACE, so a closed tab or a sleeping
laptop cannot keep charging time.
"""

BUDGET_SECONDS = 120 * 60 / 16      # 450.0 s = 7.5 min per task
GRACE_SECONDS = 30.0                # max silence from the UI before the clock stops counting


def in_time(elapsed, budget=BUDGET_SECONDS):
    """A pass counts only if it lands within the budget (450 s is still in time)."""
    return elapsed <= budget


class TaskClock:
    def __init__(self, accumulated=0.0, running_since=None, last_beat=None):
        self.accumulated = float(accumulated)
        self.running_since = running_since
        self.last_beat = last_beat

    @property
    def running(self):
        return self.running_since is not None

    def _bank_gap(self, now):
        """After a silence longer than GRACE, charge only last_beat + GRACE and restart the spell now."""
        if (self.running_since is not None and self.last_beat is not None
                and now - self.last_beat > GRACE_SECONDS):
            self.accumulated += max(0.0, self.last_beat + GRACE_SECONDS - self.running_since)
            self.running_since = now

    def start(self, now):
        if self.running_since is None:
            self.running_since = now
        else:
            self._bank_gap(now)
        self.last_beat = now

    def beat(self, now):
        if self.running_since is not None:
            self._bank_gap(now)
            self.last_beat = now

    def _end(self, now):
        # never count past the last heartbeat plus grace
        return min(now, (self.last_beat if self.last_beat is not None else now) + GRACE_SECONDS)

    def stop(self, now):
        if self.running_since is not None:
            self.accumulated += max(0.0, self._end(now) - self.running_since)
            self.running_since = None

    def elapsed(self, now):
        if self.running_since is None:
            return self.accumulated
        return self.accumulated + max(0.0, self._end(now) - self.running_since)

    def to_dict(self):
        return {"accumulated": self.accumulated, "running_since": self.running_since,
                "last_beat": self.last_beat}

    @classmethod
    def from_dict(cls, d):
        return cls(d.get("accumulated", 0.0), d.get("running_since"), d.get("last_beat"))


class SessionClocks:
    """One clock per task; at most one runs at a time."""

    def __init__(self):
        self.clocks = {}
        self.current = None
        self.hidden = False      # explicit hide: a late beat must not restart the clock

    def clock(self, tid):
        return self.clocks.setdefault(tid, TaskClock())

    def show(self, tid, now):
        if self.current is not None and self.current != tid:
            self.clock(self.current).stop(now)
        self.current = tid
        self.hidden = False
        self.clock(tid).start(now)

    def hide(self, now, tid=None):
        """Stop the shown task's clock; with `tid`, only if that is the task shown."""
        if self.current is None or (tid is not None and tid != self.current):
            return
        self.hidden = True
        self.clock(self.current).stop(now)

    def beat(self, tid, now):
        if tid != self.current:
            return
        c = self.clock(tid)
        if c.running:
            c.beat(now)
        elif not self.hidden:
            c.start(now)      # e.g. the server restarted and stopped every clock

    def elapsed(self, tid, now):
        return self.clock(tid).elapsed(now)

    def stop_all(self, now):
        for c in self.clocks.values():
            c.stop(now)
        self.current = None
