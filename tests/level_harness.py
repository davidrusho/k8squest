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
  after the reset, `heal.sh` of the level's world (if it has one) runs first, and
            setup.sh / validate.sh get K8SQUEST_CONTEXT (the world's kubectl context)
Fix step: if the level has a `solution.sh`, it is run (cwd=level dir, same env) INSTEAD of
applying solution.yaml. The engine never runs solution.sh; it is the scripted proof for
levels whose fix is a node-side or command action (docs/contributing.md).
Usage: level_harness.py [--level NAME]... [--world DIR]... [--from-world N] [--repeat N] [--keep-cluster]
  Several --level options run in the order given (to prove context switches both ways).
"""
import argparse, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))
from level_reset import (clear_leftovers, context_for, describe_failures,  # noqa: E402
                         level_env, run_world_heal, world_cluster)
from world_discovery import discover_worlds  # noqa: E402

NS = os.environ.get("K8SQUEST_NAMESPACE", "k8squest")
# world.yaml `cluster:` -> (kind cluster name, kind config file)
CLUSTERS = {
    "kind": ("k8squest", "kind/cluster.yaml"),
    "kind-multinode": ("k8squest-multinode", "kind/multinode.yaml"),
}
NS_YAML = f"apiVersion: v1\nkind: Namespace\nmetadata:\n  name: {NS}\n"
SETTLE_BROKEN = 10      # seconds to let broken state settle before asserting FAIL
FIX_TIMEOUT = 150       # seconds to wait for validate.sh to pass after the fix
SETUP_TIMEOUT = 480
# Levels whose validate.sh counts accumulated restarts need longer to turn red.
SETTLE_OVERRIDE = {"level-12-liveness": 90}
CTX = context_for("kind")   # the current world's context; set per world in main()


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


def ensure_cluster(cluster):
    """Returns (ok, why, created). Only a cluster we created is ours to delete."""
    if cluster not in CLUSTERS:
        return False, f"cluster type '{cluster}' not supported yet", False
    name, config = CLUSTERS[cluster]
    ctx = context_for(cluster)
    created = False
    if name not in run(["kind", "get", "clusters"]).stdout.split():
        r = run(["kind", "create", "cluster", "--name", name, "--config",
                 str(ROOT / config), "--wait", "180s"], timeout=600)
        if r.returncode != 0:
            return False, "kind create failed: " + r.stderr[-300:], False
        created = True
    r = run(["kubectl", "--context", ctx, "get", "nodes", "--request-timeout=10s"])
    return (r.returncode == 0), r.stderr.strip(), created


def kube_env():
    # subprocesses spawned by level scripts (setup.sh/validate.sh) use bare
    # `kubectl`, as under the engine, so make the world's context the current one.
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
    ok, msg = run_world_heal(level_path, say=lambda m: None)
    if not ok:
        return False, "world heal failed: " + msg[-200:]
    r = run(["kubectl", "apply", "-f", "-"], input=NS_YAML)
    if r.returncode:
        return False, "ns apply: " + r.stderr[-200:]
    run(["kubectl", "delete", "all", "--all", "-n", NS, "--ignore-not-found"], timeout=180)
    reset_failed = clear_leftovers(NS)   # same leftover reset the engine does after `delete all`
    warn = ("reset warnings: " + describe_failures(reset_failed)) if reset_failed else ""
    setup = level_path / "setup.sh"
    if setup.exists():
        r = run(["bash", "setup.sh"], cwd=str(level_path), timeout=SETUP_TIMEOUT,
                env={**level_env(level_path), "NAMESPACE": NS})
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
               env={**level_env(level_path), "NAMESPACE": NS}, timeout=180)


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
    sol = solution_path or (lp / "solution.sh" if (lp / "solution.sh").exists() else lp / "solution.yaml")
    if sol.suffix == ".sh":
        # scripted fix: same cwd and env as the level's own scripts
        r = run(["bash", str(sol)], cwd=str(lp), timeout=SETUP_TIMEOUT,
                env={**level_env(lp), "NAMESPACE": NS})
        if r.returncode:
            res["note"] += f"; {sol.name} rc={r.returncode}: " + (r.stderr or r.stdout).strip()[-120:]
        r = None
    elif not solution_applyable(sol):
        res["f"] = "MANUAL"
        res["note"] = (res["note"] + "; " if res["note"] else "") + "solution is comment-only"
        return res, time.time() - t0
    else:
        r = kubectl("apply", "-f", str(sol))
    if r is not None and r.returncode:
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
    """Runs the harness and puts kubectl's current context back as it was, even on failure."""
    start = run(["kubectl", "config", "current-context"]).stdout.strip()
    try:
        return _main()
    finally:
        now = run(["kubectl", "config", "current-context"]).stdout.strip()
        if start and now != start:
            run(["kubectl", "config", "use-context", start])


def _main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", action="append",
                    help="level name; repeatable; several run in the order given")
    ap.add_argument("--world", action="append", help="world directory name; repeatable")
    ap.add_argument("--from-world", type=int, metavar="N",
                    help="only worlds whose world.yaml order is >= N")
    ap.add_argument("--repeat", type=int, default=1, metavar="N",
                    help="run each selected level N times in a row (replay: the second run starts from whatever the first left)")
    ap.add_argument("--keep-cluster", action="store_true")
    ap.add_argument("--isolate", action="store_true",
                    help="delete the whole namespace between levels (diagnostic; the engine does not)")
    ap.add_argument("--solution", help="override solution file (.yaml or .sh; used to prove the harness can fail)")
    a = ap.parse_args()
    global ISOLATE, CTX
    ISOLATE = a.isolate

    worlds = discover_worlds(ROOT)
    levels = []
    for w in worlds:
        if a.world and w.dir_name not in a.world:
            continue
        if a.from_world is not None and w.order < a.from_world:
            continue
        for l in w.levels:
            if a.level and l.name not in a.level:
                continue
            levels.append((w, l))
    if a.level and len(a.level) > 1:
        # explicit order given on the command line (e.g. 7 -> 6 to exercise the context switch back)
        levels.sort(key=lambda wl: a.level.index(wl[1].name))
    if not levels:
        print("no levels selected"); return 2
    if a.repeat > 1:
        levels = [wl for wl in levels for _ in range(a.repeat)]

    rows, created_clusters = [], []
    ready = {}
    for w, l in levels:
        if w.cluster not in ready:
            ready[w.cluster] = ensure_cluster(w.cluster)
            if ready[w.cluster][0] and ready[w.cluster][2]:
                created_clusters.append(CLUSTERS[w.cluster][0])
        ok, why, _ = ready[w.cluster]
        if not ok:
            rows.append((l.name, "SKIP", "SKIP", 0, why)); continue
        if w.cluster in CLUSTERS and CTX != context_for(w.cluster):
            CTX = context_for(w.cluster)
            print(f"-- kubectl context -> {CTX} ({w.dir_name})", flush=True)
        kube_env()   # every level: the player's context follows the world, as in the engine
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

    # only clusters this run created are deleted; one that was already there is left alone
    if created_clusters and not a.keep_cluster:
        for name in created_clusters:
            run(["kind", "delete", "cluster", "--name", name], timeout=300)
    # a skipped level was not proven, so it fails the run as well
    return 1 if (fail or skip) else 0


if __name__ == "__main__":
    sys.exit(main())
