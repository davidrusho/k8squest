#!/usr/bin/env python3
"""Break/fix harness for K8sQuest levels.

For each level: reset the namespace exactly as engine/engine.py deploy_mission
does, deploy the broken state, assert validate.sh FAILS, apply solution.yaml,
assert validate.sh PASSES (retried up to a timeout).

Engine lines mirrored (engine/engine.py):
  ~896-905  `kubectl apply -f -` of Namespace k8squest (idempotent)
  ~912-916  `kubectl delete all --all -n k8squest --ignore-not-found`, then
            engine/level_reset.py clear_leftovers (quotas, RBAC, config, PVCs, taints)
  ~922-935  if setup.sh exists: `bash setup.sh` with cwd=level dir, and broken.yaml
            is NOT applied by the engine (setup.sh must do it); else
            `kubectl apply -f broken.yaml`
  ~967-976  validate: `bash validate.sh`, cwd=level dir, env NAMESPACE=k8squest
            (pass == exit code 0)
Usage: level_harness.py [--level NAME] [--world DIR] [--keep-cluster]
"""
import argparse, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))
from level_reset import clear_leftovers, describe_failures  # noqa: E402
from world_discovery import discover_worlds  # noqa: E402

NS = os.environ.get("K8SQUEST_NAMESPACE", "k8squest")
CLUSTER = "k8squest"
NS_YAML = f"apiVersion: v1\nkind: Namespace\nmetadata:\n  name: {NS}\n"
SETTLE_BROKEN = 10      # seconds to let broken state settle before asserting FAIL
FIX_TIMEOUT = 150       # seconds to wait for validate.sh to pass after the fix
SETUP_TIMEOUT = 240
# Levels whose validate.sh counts accumulated restarts need longer to turn red.
SETTLE_OVERRIDE = {"level-12-liveness": 90}
CTX = f"kind-{CLUSTER}"


def run(cmd, **kw):
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    kw.setdefault("errors", "replace")
    try:
        return subprocess.run(cmd, **kw)
    except subprocess.TimeoutExpired as e:
        return subprocess.CompletedProcess(cmd, 124, "", f"timeout after {e.timeout}s")


def kubectl(*a, **kw):
    return run(["kubectl", "--context", CTX, *a], **kw)


def ensure_cluster(kind):
    """Returns (ok, why, created). Only a cluster we created is ours to delete."""
    if kind != "kind":
        return False, f"cluster type '{kind}' not supported yet", False
    created = False
    if CLUSTER not in run(["kind", "get", "clusters"]).stdout.split():
        r = run(["kind", "create", "cluster", "--name", CLUSTER, "--config",
                 str(ROOT / "kind" / "cluster.yaml"), "--wait", "180s"], timeout=600)
        if r.returncode != 0:
            return False, "kind create failed: " + r.stderr[-300:], False
        created = True
    r = kubectl("get", "nodes", "--request-timeout=10s")
    return (r.returncode == 0), r.stderr.strip(), created


def kube_env():
    # subprocesses spawned by level scripts (setup.sh/validate.sh) use bare
    # `kubectl`, as under the engine, so make our context the current one.
    run(["kubectl", "config", "use-context", CTX])


def isolate():
    """Optional (--isolate): also delete the whole namespace between levels
    (diagnostic; the engine does not)."""
    run(["kubectl", "delete", "namespace", NS, "--ignore-not-found", "--wait=true"], timeout=240)


ISOLATE = False


def _w(warn):
    return f"; {warn}" if warn else ""


def reset(level_path):
    """Mirror engine deploy_mission. Returns (ok, note)."""
    if ISOLATE:
        isolate()
    r = run(["kubectl", "apply", "-f", "-"], input=NS_YAML)
    if r.returncode:
        return False, "ns apply: " + r.stderr[-200:]
    run(["kubectl", "delete", "all", "--all", "-n", NS, "--ignore-not-found"], timeout=180)
    reset_failed = clear_leftovers(NS)   # same leftover reset the engine does after `delete all`
    warn = ("reset warnings: " + describe_failures(reset_failed)) if reset_failed else ""
    setup = level_path / "setup.sh"
    if setup.exists():
        r = run(["bash", "setup.sh"], cwd=str(level_path), timeout=SETUP_TIMEOUT)
        if r.returncode:
            return False, "setup.sh failed: " + (r.stderr or r.stdout)[-200:]
        if "broken.yaml" not in setup.read_text(errors="replace"):
            return True, "setup.sh never applies broken.yaml (engine skips it)" + _w(warn)
        return True, warn
    r = run(["kubectl", "apply", "-f", str(level_path / "broken.yaml")])
    if r.returncode:
        # the engine aborts here ("Deployment failed", returns False); the
        # harness records it and carries on so the fix path is still tested
        return True, "ENGINE ABORTS (broken apply rc!=0): " + r.stderr.strip()[-110:] + _w(warn)
    return True, warn


def validate(level_path):
    return run(["bash", "validate.sh"], cwd=str(level_path),
               env={**os.environ, "NAMESPACE": NS}, timeout=120)


def solution_applyable(path):
    for line in path.read_text(errors="replace").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            return True
    return False


def run_level(level, solution_path=None):
    """Returns dict(b, f, secs, note). b/f in PASS-expected strings."""
    t0 = time.time()
    res = {"b": "-", "f": "-", "note": ""}
    lp = level.path
    ok, note = reset(lp)
    if not ok:
        res.update(b="ERR", note=note)
        return res, time.time() - t0
    res["note"] = note
    time.sleep(SETTLE_OVERRIDE.get(level.name, SETTLE_BROKEN))
    v = validate(lp)
    res["b"] = "ok" if v.returncode != 0 else "FAIL(passes broken)"
    sol = solution_path or (lp / "solution.yaml")
    if not solution_applyable(sol):
        res["f"] = "MANUAL"
        res["note"] = (res["note"] + "; " if res["note"] else "") + "solution is comment-only"
        return res, time.time() - t0
    r = kubectl("apply", "-f", str(sol))
    if r.returncode:
        # immutable-field errors: the hints tell players to delete + re-apply,
        # which is what `replace --force` does
        r2 = kubectl("replace", "--force", "-f", str(sol), timeout=240)
        res["note"] += "; apply rejected -> replace --force" + (
            "" if r2.returncode == 0 else f" failed: {r2.stderr.strip()[-120:]}")
    deadline = time.time() + FIX_TIMEOUT
    while True:
        v = validate(lp)
        if v.returncode == 0:
            res["f"] = "ok"
            break
        if time.time() > deadline:
            res["f"] = "FAIL"
            tail = (v.stdout.strip().splitlines() or [""])[-1][:100]
            res["note"] += f"; validate: {tail}"
            break
        time.sleep(4)
    return res, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level")
    ap.add_argument("--world")
    ap.add_argument("--keep-cluster", action="store_true")
    ap.add_argument("--isolate", action="store_true",
                    help="delete the whole namespace between levels (diagnostic; the engine does not)")
    ap.add_argument("--solution", help="override solution file (used to prove the harness can fail)")
    a = ap.parse_args()
    global ISOLATE
    ISOLATE = a.isolate

    worlds = discover_worlds(ROOT)
    levels = []
    for w in worlds:
        if a.world and w.dir_name != a.world:
            continue
        for l in w.levels:
            if a.level and l.name != a.level:
                continue
            levels.append((w, l))
    if not levels:
        print("no levels selected"); return 2

    rows, cluster_created = [], False
    ready = {}
    for w, l in levels:
        if w.cluster not in ready:
            ready[w.cluster] = ensure_cluster(w.cluster)
            if w.cluster == "kind" and ready[w.cluster][0]:
                cluster_created = ready[w.cluster][2]
                kube_env()
        ok, why, _ = ready[w.cluster]
        if not ok:
            rows.append((l.name, "SKIP", "SKIP", 0, why)); continue
        sp = Path(a.solution) if a.solution else None
        res, secs = run_level(l, sp)
        rows.append((l.name, res["b"], res["f"], int(secs), res["note"]))
        print(f"{l.name:40} {res['b']:8} {res['f']:8} {int(secs):4}s {res['note']}", flush=True)

    print()
    print(f"{'level':40} | {'broken->fail':12} | {'fixed->pass':11} | secs | note")
    for r in rows:
        print(f"{r[0]:40} | {r[1]:12} | {r[2]:11} | {r[3]:4} | {r[4]}")
    # an engine abort, or a setup.sh that never deploys the broken state, means
    # the player never sees the intended scenario, so neither counts as ok
    ok = sum(1 for r in rows if r[1] == "ok" and r[2] == "ok"
             and "ENGINE ABORTS" not in r[4] and "never applies broken.yaml" not in r[4])
    man = sum(1 for r in rows if r[2] == "MANUAL" and r[1] == "ok")
    skip = sum(1 for r in rows if r[1] == "SKIP")
    fail = len(rows) - ok - man - skip
    print(f"{len(rows)} levels: {ok} ok, {fail} fail, {man} manual, {skip} skip")

    if cluster_created and not a.keep_cluster:
        run(["kind", "delete", "cluster", "--name", CLUSTER], timeout=300)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
