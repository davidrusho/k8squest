#!/usr/bin/env python3
# Added 2026 by David Rusho; see CHANGES.md
"""
Shared level reset for the engine, engine/reset.py and tests/level_harness.py.

`kubectl delete all` leaves behind quotas, limit ranges, network policies, RBAC,
service accounts, config maps, secrets and PVCs in the namespace, plus node taints
and labels that earlier levels set. clear_leftovers() removes them so a level
starts from the same state no matter which level was played before it.
"""

import json
import os
import platform
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
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

# World 8 (`cluster: lima`) builds its own kubeadm cluster on two Lima virtual machines.
# The context always exists (a placeholder pointing at the forwarded API port) so the
# levels that start before any cluster exists have a context to select; the cluster's
# real credentials replace the placeholder once the level scripts have a cluster.
LIMA_CONTEXT = "k8squest-lima"
LIMA_API_HOST_PORT = 16443    # lima/node.yaml forwards the guest's 6443 here
# name, CPUs, memory in GiB (kubeadm's preflight wants 2 CPUs and 1700 MB or more)
LIMA_INSTANCES = (("k8squest-cp", 2, 3), ("k8squest-worker", 2, 2.5))
# The game marks the machines it creates with this Lima template parameter (lima/node.yaml `param:`;
# https://lima-vm.io/docs/ "param: Key: value"). A machine with the same name and no marker is somebody
# else's and is never used: World 8 runs kubeadm reset, deletes files and flushes firewall rules in it.
LIMA_MARKER_KEY, LIMA_MARKER_VALUE = "k8squest_world", "8"
LIMA_MIN_VERSION = (2, 0, 0)  # lima/node.yaml: minimumLimaVersion
LIMA_MIN_MEM_KIB = 8 * 1024 * 1024

# Contexts the game runs on: the engine's expected one (K8S_CLUSTER_TYPE, as in
# engine.py), the k3s name, the multi-node kind cluster and the World 8 cluster, so a
# k3s setup is not refused.
KNOWN_CONTEXTS = ("kind-k8squest", "k3s-k8squest", MULTINODE_CONTEXT, LIMA_CONTEXT)


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
    if cluster == "lima":
        return LIMA_CONTEXT
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
    (kind/multinode.yaml). `lima`: creates and starts the two Lima machines of World 8
    (lima/node.yaml) after a preflight, and makes sure the kubectl context exists; the
    levels build the Kubernetes cluster on them. `kind`: the cluster is created by
    install.sh, so only the context is switched. Returns (ok, message)."""
    try:
        ctx = context_for(cluster)
    except ValueError as e:
        return False, str(e)
    if cluster == "lima":
        if shutil.which("kubectl") is None:
            return False, "kubectl not found on PATH (World 8 needs kubectl and Lima installed)"
        problem = lima_preflight()
        if problem:
            return False, problem
        ok, why = ensure_lima_instances(repo_root, say=say)
        if not ok:
            return False, why
        ok, why = ensure_lima_context(ctx)
        if not ok:
            return False, why
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


# ---------------------------------------------------------------- World 8: Lima machines

def _lima_version(text):
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", text or "")
    return tuple(int(x) for x in m.groups()) if m else None


def lima_preflight(system=None, kvm_path="/dev/kvm", meminfo_path="/proc/meminfo", machine=None):
    """Returns a message saying what is missing when this host cannot run the World 8
    virtual machines, else None. On macOS Lima uses the system hypervisor, so only the
    limactl version is checked there; on Linux it needs QEMU, a usable /dev/kvm and RAM."""
    system = system or platform.system()
    machine = machine or platform.machine()
    if shutil.which("limactl") is None:
        return ("limactl not found on PATH. World 8 runs on two Lima virtual machines; install Lima "
                f"{'.'.join(map(str, LIMA_MIN_VERSION))} or newer "
                "(macOS: brew install lima; Linux: https://lima-vm.io/docs/installation/).")
    have = _lima_version(_run(["limactl", "--version"], timeout=30).stdout)
    if have is None or have < LIMA_MIN_VERSION:
        return (f"limactl is older than {'.'.join(map(str, LIMA_MIN_VERSION))} "
                f"(found {'.'.join(map(str, have)) if have else 'an unreadable version'}); "
                "World 8's machines need Lima 2.0 or newer. Upgrade Lima and start the level again.")
    if system != "Linux":
        return None
    qemu = "qemu-system-aarch64" if machine in ("aarch64", "arm64") else "qemu-system-x86_64"
    if shutil.which(qemu) is None:
        return (f"{qemu} not found on PATH. On Linux Lima runs its machines with QEMU; install it "
                "(Debian/Ubuntu: sudo apt install qemu-system qemu-utils).")
    if not Path(kvm_path).exists():
        return (f"{kvm_path} does not exist, so this host cannot run hardware-accelerated virtual machines "
                "and World 8's two machines would be unusably slow. Enable virtualization in the firmware, "
                "or on a cloud or virtual host turn on nested virtualization.")
    if not os.access(kvm_path, os.R_OK | os.W_OK):
        return (f"{kvm_path} is not readable and writable by this user. Add yourself to the kvm group "
                "(sudo usermod -aG kvm $USER), then log in again and start the level again.")
    try:
        for line in Path(meminfo_path).read_text().splitlines():
            if line.startswith("MemTotal:"):
                kib = int(line.split()[1])
                if kib < LIMA_MIN_MEM_KIB:
                    return (f"this host has {kib // 1024} MiB of RAM; World 8's two machines use "
                            f"{sum(m for _, _, m in LIMA_INSTANCES):g} GiB between them and need a host with 8 GiB or more.")
    except (OSError, ValueError):
        pass
    return None


def lima_instances():
    """{instance name: (status, created by this game)} from `limactl list --json`, or None when it
    cannot be read. "Created by this game" means the instance carries the lima/node.yaml marker param."""
    r = _run(["limactl", "list", "--json"], timeout=60)
    if r.returncode != 0:
        return None
    out = {}
    for line in r.stdout.splitlines():
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        param = (obj.get("config") or {}).get("param") or {}
        out[obj.get("name", "")] = (obj.get("status", ""), param.get(LIMA_MARKER_KEY) == LIMA_MARKER_VALUE)
    return out


def lima_status():
    """{instance name: status}, or None when `limactl list` cannot be read."""
    inst = lima_instances()
    return None if inst is None else {n: st for n, (st, _) in inst.items()}


def ensure_lima_instances(repo_root, say=print):
    """Create (from lima/node.yaml) and start the World 8 machines that are missing or
    stopped. Existing machines are reused as they are. Returns (ok, message)."""
    inst = lima_instances()
    if inst is None:
        return False, "could not read the Lima machine list (limactl list failed)"
    status = {n: st for n, (st, _) in inst.items()}
    for name, _cpus, _mem in LIMA_INSTANCES:
        if name in inst and not inst[name][1]:
            return False, (f"a Lima machine named {name} exists but this game did not create it (it has no "
                           f"{LIMA_MARKER_KEY} marker), and World 8 would run kubeadm reset, delete files and flush "
                           f"firewall rules inside it. Delete it if you do not need it (limactl delete -f {name}), or "
                           f"keep it under another name (limactl stop {name}; limactl clone {name} <new-name>; "
                           f"limactl delete -f {name}), then start the level again.")
    node_yaml = Path(repo_root) / "lima" / "node.yaml"
    todo = []
    for name, cpus, mem in LIMA_INSTANCES:
        have = status.get(name)
        if have == "Running":
            continue
        if have not in (None, "Stopped"):
            return False, (f"the Lima machine {name} is in state {have}. Delete it so the game can create it "
                           f"again: limactl delete -f {name}")
        todo.append((name, cpus, mem, have))
    if not todo:
        return True, ""
    if any(have is None for *_, have in todo):
        say("World 8 runs on two Lima virtual machines (Ubuntu 26.04, "
            f"{sum(m for _, _, m in LIMA_INSTANCES):g} GiB of RAM between them) that do not exist yet. "
            "Creating and starting them takes about a minute; the first level then installs the "
            "Kubernetes packages (a few more minutes).")

    def bring_up(item):
        name, cpus, mem, have = item
        if have is None:
            r = _run(["limactl", "create", "--tty=false", f"--name={name}", f"--cpus={cpus}",
                      f"--memory={mem:g}", str(node_yaml)], timeout=900)
            if r.returncode:
                return f"limactl create {name} failed: " + _tail(r.stderr or r.stdout, 300)
        r = _run(["limactl", "start", name], timeout=900)
        if r.returncode:
            return f"limactl start {name} failed: " + _tail(r.stderr or r.stdout, 300)
        return ""

    with ThreadPoolExecutor(max_workers=len(todo)) as pool:
        errors = [e for e in pool.map(bring_up, todo) if e]
    return (not errors), "; ".join(errors)


def delete_lima_instances(names=None):
    """Delete the named World 8 machines (default: both). The harness passes only the ones it created."""
    names = [n for n, _, _ in LIMA_INSTANCES] if names is None else list(names)
    if not names:
        return subprocess.CompletedProcess([], 0, "", "")
    return _run(["limactl", "delete", "-f", *names], timeout=300)


def ensure_lima_context(ctx=LIMA_CONTEXT):
    """Make sure the kubectl context exists. Before a level has built a cluster it is a
    placeholder that points at the forwarded API port and has no credentials, so kubectl
    answers 'connection refused' there (true: there is no cluster yet). Never touches a
    context that already exists. Returns (ok, message)."""
    r = _run(["kubectl", "config", "get-contexts", "-o", "name"])
    if r.returncode == 0 and ctx in r.stdout.split():
        return True, ""
    steps = (["kubectl", "config", "set-cluster", ctx, f"--server=https://127.0.0.1:{LIMA_API_HOST_PORT}",
              "--tls-server-name=kubernetes"],
             ["kubectl", "config", "set-context", ctx, f"--cluster={ctx}"])
    for step in steps:
        r = _run(step)
        if r.returncode:
            return False, f"could not create the kubectl context {ctx}: " + _tail(r.stderr)
    return True, ""


def world_has_api(cluster):
    """False only for a `lima` world whose cluster has not been built yet (levels 71 and 72
    start before `kubeadm init`), where there is no API server to apply a namespace to."""
    if cluster != "lima":
        return True
    r = _run(["kubectl", "--context", LIMA_CONTEXT, "get", "--raw", "/readyz", "--request-timeout=5s"], timeout=30)
    return r.returncode == 0


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
    failed = []
    if world_has_api(cluster):   # a World 8 level can start before any cluster exists
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
