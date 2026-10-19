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
import subprocess

# Node taint / label keys that levels 45, 46 and 50 set on the node
NODE_TAINT_KEYS = ("dedicated",)
NODE_LABEL_KEYS = ("accelerator",)


def _run(args, timeout=120, **kw):
    try:
        return subprocess.run(args, capture_output=True, text=True,
                              errors="replace", timeout=timeout, **kw)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 124, "", f"timeout after {timeout}s")


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

# Contexts the game runs on: the engine's expected one (K8S_CLUSTER_TYPE, as in
# engine.py) plus both known names, so a k3s setup is not refused.
KNOWN_CONTEXTS = ("kind-k8squest", "k3s-k8squest")


def expected_context():
    """The kubectl context the engine expects (same rule as engine.get_expected_context)."""
    if os.environ.get("K8S_CLUSTER_TYPE", "kind") == "k3s":
        return "k3s-k8squest"
    return "kind-k8squest"


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
    r = _run(["kubectl", "apply", "-f", "-"], input=NAMESPACE_YAML.format(ns=namespace))
    if r.returncode:
        return False, "namespace apply failed: " + r.stderr.strip()
    _run(["kubectl", "delete", "all", "--all", "-n", namespace, "--ignore-not-found"], timeout=180)
    failed = clear_leftovers(namespace)
    setup = level_path / "setup.sh"
    if setup.exists():
        r = _run(["bash", "setup.sh"], cwd=str(level_path), timeout=600)
        ok, msg = r.returncode == 0, (r.stderr or r.stdout).strip()
    else:
        r = _run(["kubectl", "apply", "-f", str(level_path / "broken.yaml")])
        ok, msg = r.returncode == 0, r.stderr.strip()
    if failed:
        msg = (msg + "; " if msg else "") + "reset warnings: " + describe_failures(failed)
    return ok, msg
