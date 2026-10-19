#!/usr/bin/env python3
# Added 2026 by David Rusho; see CHANGES.md
"""
Shared level reset for the engine, engine/reset.py and tests/level_harness.py.

`kubectl delete all` leaves behind quotas, limit ranges, network policies, RBAC,
service accounts, config maps, secrets and PVCs in the namespace, plus node taints
and labels that earlier levels set. clear_leftovers() removes them so a level
starts from the same state no matter which level was played before it.
"""

import os
import shutil
import subprocess
from pathlib import Path

# Node taint / label keys that levels 45, 46 and 50 set on the node
NODE_TAINT_KEYS = ("dedicated",)
NODE_LABEL_KEYS = ("accelerator",)


def _run(args, timeout=120, **kw):
    try:
        return subprocess.run(args, capture_output=True, text=True,
                              errors="replace", timeout=timeout, **kw)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 124, "", f"timeout after {timeout}s")
    except FileNotFoundError:
        # a missing binary is a normal "not installed" answer, not a traceback in the TUI
        return subprocess.CompletedProcess(args, 127, "", f"{args[0]} not found on PATH")


def _tail(text, n=160):
    text = (text or "").strip()
    return text[-n:]


def _delete_except(kind, namespace, keep):
    """Delete every object of `kind` in the namespace except the names in `keep`.
    Returns a list of (step, stderr tail) for what failed."""
    listed = _run(["kubectl", "get", kind, "-n", namespace, "-o", "name"])
    if listed.returncode != 0:
        return [(f"list {kind}", _tail(listed.stderr))]
    names = [n for n in listed.stdout.split()
             if n.split("/", 1)[-1] not in keep]
    if not names:
        return []
    r = _run(["kubectl", "delete", "-n", namespace, "--ignore-not-found", *names])
    return [(f"delete {kind}", _tail(r.stderr))] if r.returncode else []


# Created by install.sh from rbac/k8squest-rbac.yaml: the player's own access, not level state
PLAYER_SERVICEACCOUNT = "k8squest-player"
PLAYER_ROLE = "k8squest-player-role"
PLAYER_ROLEBINDING = "k8squest-player-binding"

# The cluster each world.yaml `cluster:` value runs on. This is the ONE place that
# maps a cluster type to a kubectl context; the engine, engine/reset.py,
# tests/level_harness.py and the level scripts (through K8SQUEST_CONTEXT) all use it.
MULTINODE_CLUSTER = "k8squest-multinode"
MULTINODE_CONTEXT = "kind-" + MULTINODE_CLUSTER

# Contexts the game runs on: the engine's expected one (K8S_CLUSTER_TYPE, as in
# engine.py), the k3s name, and the multi-node kind cluster, so a k3s setup is not refused.
KNOWN_CONTEXTS = ("kind-k8squest", "k3s-k8squest", MULTINODE_CONTEXT)


def expected_context():
    """The kubectl context the engine expects for a `cluster: kind` world (same rule as
    engine.get_expected_context)."""
    if os.environ.get("K8S_CLUSTER_TYPE", "kind") == "k3s":
        return "k3s-k8squest"
    return "kind-k8squest"


def context_for(cluster):
    """The kubectl context a world with `cluster: <cluster>` runs on."""
    if cluster == "kind":
        return expected_context()
    if cluster == "kind-multinode":
        return MULTINODE_CONTEXT
    raise ValueError(f"no kubectl context is defined for cluster type {cluster!r}")


def world_cluster(level_path):
    """The `cluster:` value of the world.yaml next to a level directory ('kind' if unreadable)."""
    try:
        for line in (Path(level_path).parent / "world.yaml").read_text(errors="replace").splitlines():
            if line.startswith("cluster:"):
                return line.split(":", 1)[1].split("#")[0].strip().strip("\"'")
    except OSError:
        pass
    return "kind"


def level_env(level_path):
    """Environment for a level's setup.sh / validate.sh: K8SQUEST_CONTEXT is the context
    the level's world runs on (worlds/_shared/lib.sh require_game_context checks it)."""
    try:
        ctx = context_for(world_cluster(level_path))
    except ValueError:
        ctx = expected_context()
    return {**os.environ, "K8SQUEST_CONTEXT": ctx}


# kind's known-issues page: the game cluster (1 node) plus the World 7 cluster (3 nodes)
# need more inotify instances than the Linux default of 128.
INOTIFY_LIMIT_FILE = "/proc/sys/fs/inotify/max_user_instances"
INOTIFY_MIN_INSTANCES = 512


def inotify_preflight(limit_file=None):
    """Returns an error message when this Linux host's inotify instance limit is too low
    for a second kind cluster, else None. Skipped when the file is missing (macOS,
    Docker Desktop) or unreadable."""
    path = limit_file or INOTIFY_LIMIT_FILE
    try:
        have = int(Path(path).read_text().strip())
    except (OSError, ValueError):
        return None
    if have >= INOTIFY_MIN_INSTANCES:
        return None
    return (f"fs.inotify.max_user_instances is {have}; World 7 needs at least {INOTIFY_MIN_INSTANCES} "
            "to run next to the main cluster (otherwise pods fail with 'too many open files'). "
            "See https://kind.sigs.k8s.io/docs/user/known-issues/#pod-errors-due-to-too-many-open-files . "
            f"Now: sudo sysctl fs.inotify.max_user_instances={INOTIFY_MIN_INSTANCES} . "
            "Persistent: echo 'fs.inotify.max_user_instances = "
            f"{INOTIFY_MIN_INSTANCES}' | sudo tee /etc/sysctl.d/90-kind-inotify.conf && sudo sysctl --system")


MULTINODE_NODES = (MULTINODE_CLUSTER + "-control-plane", MULTINODE_CLUSTER + "-worker", MULTINODE_CLUSTER + "-worker2")


def multinode_nodes_problem():
    """A message when the multinode cluster exists but a node container is missing or not
    running (the heal step cannot repair that), else None."""
    bad = []
    for node in MULTINODE_NODES:
        r = _run(["docker", "inspect", "-f", "{{.State.Running}}", node], timeout=30)
        if r.returncode != 0 or r.stdout.strip() != "true":
            bad.append(node)
    if not bad:
        return None
    return (f"the cluster {MULTINODE_CLUSTER} exists but its node container(s) {', '.join(bad)} are missing or not running. "
            f"Delete it with `kind delete cluster --name {MULTINODE_CLUSTER}` and start the level again.")


def cluster_exists(kind_name):
    r = _run(["kind", "get", "clusters"], timeout=60)
    return r.returncode == 0 and kind_name in r.stdout.split()


def ensure_world_cluster(cluster, repo_root, say=print):
    """Make the world's cluster exist and make its context the current one.

    `kind-multinode`: creates the kind cluster k8squest-multinode on first use
    (kind/multinode.yaml). `kind`: the cluster is created by install.sh, so only the
    context is switched. Returns (ok, message)."""
    try:
        ctx = context_for(cluster)
    except ValueError as e:
        return False, str(e)
    for tool in (["kubectl"] + (["kind", "docker"] if cluster == "kind-multinode" else [])):
        if shutil.which(tool) is None:
            return False, f"{tool} not found on PATH (World 7 needs kubectl, kind and docker installed)"
    if cluster == "kind-multinode" and cluster_exists(MULTINODE_CLUSTER):
        problem = multinode_nodes_problem()
        if problem:
            return False, problem
    if cluster == "kind-multinode" and not cluster_exists(MULTINODE_CLUSTER):
        problem = inotify_preflight()
        if problem:
            return False, problem
        say("This world runs on a 3-node kind cluster that does not exist yet. "
            "Creating it (about 30-60 seconds): kind create cluster --name "
            f"{MULTINODE_CLUSTER} --config kind/multinode.yaml --wait 180s")
        r = _run(["kind", "create", "cluster", "--name", MULTINODE_CLUSTER, "--config",
                  str(Path(repo_root) / "kind" / "multinode.yaml"), "--wait", "180s"], timeout=600)
        if r.returncode:
            return False, "kind create cluster failed: " + _tail(r.stderr or r.stdout, 300)
        # the namespace and the player's RBAC that install.sh sets up on the main cluster
        r = _run(["kubectl", "--context", ctx, "apply", "-f", "-"], input=NAMESPACE_YAML.format(ns="k8squest"))
        if r.returncode:
            return False, "the cluster was created but the k8squest namespace could not be applied: " + _tail(r.stderr)
        rbac = Path(repo_root) / "rbac" / "k8squest-rbac.yaml"
        if rbac.exists():
            r = _run(["kubectl", "--context", ctx, "apply", "-f", str(rbac)])
            if r.returncode:
                return False, "the cluster was created but the player RBAC could not be applied: " + _tail(r.stderr)
    current = _run(["kubectl", "config", "current-context"]).stdout.strip()
    if current != ctx:
        r = _run(["kubectl", "config", "use-context", ctx])
        if r.returncode:
            return False, f"could not switch kubectl to context {ctx}: " + _tail(r.stderr)
        say(f"kubectl context switched: {current or 'none'} -> {ctx}")
    return True, ""


def run_world_heal(level_path, say=print):
    """Run the world's optional heal.sh before a level starts, so a fault an earlier
    level left behind (a stopped kubelet, a broken API server) cannot block the reset
    that follows. Returns (ok, message); ok when the world has no heal.sh."""
    heal = Path(level_path).parent / "heal.sh"
    if not heal.exists():
        return True, ""
    r = _run(["bash", heal.name], cwd=str(heal.parent), timeout=600, env=level_env(level_path))
    return (r.returncode == 0), (r.stderr or r.stdout).strip()[-400:]


def on_game_cluster():
    """Node edits are cluster-wide, so only make them on the game's own cluster
    (or when K8SQUEST_ALLOW_CONTEXT=1, matching World 6's require_game_context)."""
    if os.environ.get("K8SQUEST_ALLOW_CONTEXT") == "1":
        return True
    ctx = _run(["kubectl", "config", "current-context"]).stdout.strip()
    return ctx in KNOWN_CONTEXTS or ctx == expected_context()


def clear_leftovers(namespace="k8squest"):
    """Remove what `kubectl delete all` leaves in the namespace, and node taints/labels.

    Returns a list of (step, stderr tail) for every step that failed, [] when all
    worked. A taint or label that is already absent counts as success."""
    failed = []
    for kind in ("resourcequotas", "limitranges", "networkpolicies", "secrets",
                 "persistentvolumeclaims"):
        r = _run(["kubectl", "delete", kind, "--all", "-n", namespace, "--ignore-not-found"])
        if r.returncode:
            failed.append((f"delete {kind}", _tail(r.stderr)))
    failed += _delete_except("roles", namespace, keep={PLAYER_ROLE})
    failed += _delete_except("rolebindings", namespace, keep={PLAYER_ROLEBINDING})
    failed += _delete_except("serviceaccounts", namespace, keep={"default", PLAYER_SERVICEACCOUNT})
    failed += _delete_except("configmaps", namespace, keep={"kube-root-ca.crt"})
    if not on_game_cluster():
        failed.append(("node taints/labels", "skipped: kubectl context is not the game cluster"))
        return failed
    for verb, keys in (("taint", NODE_TAINT_KEYS), ("label", NODE_LABEL_KEYS)):
        for key in keys:
            r = _run(["kubectl", verb, "nodes", "--all", f"{key}-"])
            if r.returncode and "not found" not in r.stderr:
                failed.append((f"{verb} {key}-", _tail(r.stderr)))
    return failed


def describe_failures(failed):
    return "; ".join(f"{step}: {err}" if err else step for step, err in failed)


NAMESPACE_YAML = "apiVersion: v1\nkind: Namespace\nmetadata:\n  name: {ns}\n"


def deploy_level(level_path, namespace="k8squest"):
    """Reset and deploy a level exactly as the engine does. Returns (ok, message)."""
    cluster = world_cluster(level_path)
    try:
        ok, msg = ensure_world_cluster(cluster, Path(__file__).resolve().parent.parent, say=lambda m: None)
    except Exception as e:  # never let a missing kind binary crash the reset tool
        ok, msg = False, str(e)
    if not ok:
        return False, msg
    ok, msg = run_world_heal(level_path, say=lambda m: None)
    if not ok:
        return False, "world heal failed: " + msg
    r = _run(["kubectl", "apply", "-f", "-"], input=NAMESPACE_YAML.format(ns=namespace))
    if r.returncode:
        return False, "namespace apply failed: " + r.stderr.strip()
    _run(["kubectl", "delete", "all", "--all", "-n", namespace, "--ignore-not-found"], timeout=180)
    failed = clear_leftovers(namespace)
    setup = level_path / "setup.sh"
    if setup.exists():
        r = _run(["bash", "setup.sh"], cwd=str(level_path), timeout=900, env=level_env(level_path))
        ok, msg = r.returncode == 0, (r.stderr or r.stdout).strip()
    else:
        r = _run(["kubectl", "apply", "-f", str(level_path / "broken.yaml")])
        ok, msg = r.returncode == 0, r.stderr.strip()
    if failed:
        msg = (msg + "; " if msg else "") + "reset warnings: " + describe_failures(failed)
    return ok, msg
