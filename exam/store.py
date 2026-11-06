"""Persistent results (every attempt of every task) and the live session, as JSON files."""
import json
import os
import tempfile
from pathlib import Path

DATA_DIR = Path(os.environ.get("CKA_EXAM_DATA", Path.home() / ".local/share/cka-exam"))


def _load(path, default):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def _save(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f, indent=2)
    os.replace(tmp, path)


class Results:
    """results.json: {"tasks": {task_id: {"attempts": [{session, elapsed, passed, in_time, ts}]}}}"""

    def __init__(self, path=None):
        self.path = Path(path) if path else DATA_DIR / "results.json"
        self.data = _load(self.path, {"tasks": {}})
        self.data.setdefault("tasks", {})

    def record(self, task_id, session_id, elapsed, passed, in_time, ts):
        t = self.data["tasks"].setdefault(task_id, {"attempts": []})
        t["attempts"].append({"session": session_id, "elapsed": round(elapsed, 1),
                              "passed": bool(passed), "in_time": bool(passed and in_time), "ts": ts})
        _save(self.path, self.data)

    def attempts(self, task_id):
        return self.data["tasks"].get(task_id, {}).get("attempts", [])

    def counted(self, task_id):
        """True when some attempt passed within the time budget."""
        return any(a["passed"] and a["in_time"] for a in self.attempts(task_id))

    def counted_ids(self):
        return {tid for tid in self.data["tasks"] if self.counted(tid)}


class SessionFile:
    def __init__(self, path=None):
        self.path = Path(path) if path else DATA_DIR / "session.json"

    def load(self):
        return _load(self.path, None)

    def save(self, obj):
        _save(self.path, obj)
