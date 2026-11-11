#!/usr/bin/env python3
"""Live end-to-end proof for pool tasks: broken state must FAIL its validator, the level's
solution must make it PASS. Usage: e2e.py [--poll SECONDS] [--kind exam|drill] [--tasks t22,t30 | task-id ...]   (default: whole pool)
Exploration mode: e2e.py --level <world/level-dir> [--ns exam-tXX]  (no pool entry needed)"""
import argparse
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["EXAM_ALLOW_UNPROVEN"] = "1"      # this is the tool that produces e2e-status.json
import levels  # noqa: E402

EXPLORE_RENAMES = {
    "level-27-crossnamespace": {"backend-ns": "exam-t27-backend"},
    "level-31-pvc-pending": {"app-storage": "exam-t31-app-storage"},
    "level-32-volume-mount": {"config-storage": "exam-t32-config-storage"},
    "level-33-access-mode": {"shared-storage": "exam-t33-shared-storage"},
    "level-39-reclaim-policy": {"important-data": "exam-t39-important-data"},
}


def poll_validate(rel, ns, renames, poll):
    end = time.time() + poll
    while True:
        ok, out = levels.validate(rel, ns, renames)
        if ok or time.time() >= end:
            return ok, out
        time.sleep(5)


def prove(rel, ns, renames, cluster_objects=(), poll=90, settle=8, extra=()):
    res = {"rel": rel, "ns": ns}
    ok, msg = levels.deploy(rel, ns, renames, cluster_objects)
    res["deploy"] = (ok, msg)
    if not ok:
        res["verdict"] = "DEPLOY-FAIL"
        return res
    time.sleep(settle)
    pre_ok, pre_out = levels.validate(rel, ns, renames)
    res["pre"] = (pre_ok, pre_out[-300:])
    if pre_ok:
        res["verdict"] = "BROKEN-ALREADY-PASSES"
        return res
    s_ok, s_msg = levels.apply_solution(rel, ns, renames, extra)
    res["solution"] = (s_ok, s_msg)
    post_ok, post_out = poll_validate(rel, ns, renames, poll)
    res["post"] = (post_ok, post_out[-300:])
    res["verdict"] = "OK" if post_ok else "SOLUTION-DOES-NOT-PASS"
    return res


def main():
    levels.install_signal_cleanup()
    ap = argparse.ArgumentParser()
    ap.add_argument("tasks", nargs="*")
    ap.add_argument("--tasks", dest="task_list", default="", help="comma separated task ids, e.g. t22,t30,t45")
    ap.add_argument("--kind", choices=("exam", "drill"), default="exam",
                    help="namespace / object prefix to prove under; drill never writes e2e-status.json")
    ap.add_argument("--level")
    ap.add_argument("--ns")
    ap.add_argument("--poll", type=int, default=90)
    ap.add_argument("--write-status", action="store_true", help="record verdicts in e2e-status.json (drops failing tasks from the pool)")
    ap.add_argument("--keep", action="store_true", help="do not clean up afterwards")
    a = ap.parse_args()
    if a.kind == "drill" and a.write_status:
        ap.error("--write-status records the pool and is only valid with --kind exam")
    wanted = set(a.tasks) | {x.strip() for x in a.task_list.split(",") if x.strip()}
    jobs = []
    if a.level:
        name = a.level.rstrip("/").split("/")[-1]
        m = re.search(r"level-(\d+)", name)
        ns = a.ns or f"{a.kind}-t{int(m.group(1)):02d}"
        jobs.append((a.level, ns, {o: n.replace("exam-", a.kind + "-", 1) for o, n in EXPLORE_RENAMES.get(name, {}).items()}, (), ()))
    else:
        import pool
        for t in pool.ALL_TASKS:
            if wanted and t["id"] not in wanted:
                continue
            jobs.append((t["level"], pool.namespace(t["id"], a.kind), pool.renames_for(t, a.kind),
                         pool.cluster_objects_for(t, a.kind), t.get("solution_extra", ())))
    bad = 0
    for rel, ns, ren, co, ex in jobs:
        r = prove(rel, ns, ren, co, poll=a.poll, extra=ex)
        print(f"{r['verdict']:24} {rel}  ns={ns}", flush=True)
        if r["verdict"] != "OK":
            bad += 1
            for k in ("deploy", "pre", "solution", "post"):
                if k in r:
                    print(f"    {k}: {r[k]}", flush=True)
        if a.write_status and not a.level:
            import json, datetime
            sp = Path(__file__).resolve().parent / "e2e-status.json"
            try:
                st = json.loads(sp.read_text())
            except (OSError, ValueError):
                st = {}
            tid = ns.replace("exam-", "", 1)
            st[tid] = {"verdict": r["verdict"], "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                       "detail": "" if r["verdict"] == "OK" else str({k: r[k] for k in ("deploy", "pre", "solution", "post") if k in r})[:600]}
            sp.write_text(json.dumps(st, indent=2, sort_keys=True))
        if not a.keep:
            levels.delete_task_objects(ns, co)
    for w in levels.reset_node_state():
        print("node reset warning:", w)
    print(f"RESULT: {len(jobs) - bad}/{len(jobs)} OK")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
