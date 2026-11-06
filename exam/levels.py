"""Deploy and validate K8sQuest levels under a per-task namespace.

Level files are never edited. A level directory is copied to a temp directory, every text
file in the copy has `k8squest` (as a whole token) rewritten to the task namespace, and
cluster-scoped / secondary names listed in the task's `renames` are rewritten too. The copy is
then deployed the same way engine/level_reset.py deploy_level() does it: namespace, then
setup.sh if the level has one (cwd = level dir), otherwise `kubectl apply -f broken.yaml`.
"""
import atexit
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORLDS = REPO / "worlds"
KUBE_CONTEXT = os.environ.get("EXAM_KUBE_CONTEXT", "kind-k8squest")
TEXT_SUFFIXES = {".yaml", ".yml", ".sh", ".txt", ".md", ".json", ""}

# `k8squest` as a whole token. Not when it is part of a longer identifier (k8squest-player,
# k8squest-control-plane, /tmp/k8squest-data); a DNS label `x.k8squest.svc` does match.
# Also not a hidden directory (~/.k8squest/work).
_NS_RE = re.compile(r"(?<!\w)(?<!\w-)(?<!/\.)k8squest(?![\w-])")


def _token_re(name):
    # a whole name: not part of a longer identifier, DNS name or path component
    # DNS names count: api-service.<name>.svc is a use of the namespace name
    return re.compile(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])")


def rewrite_text(text, namespace, renames=None):
    """Rewrite the namespace token, then each old->new name in `renames` (longest first)."""
    text = _NS_RE.sub(namespace, text)
    for old in sorted(renames or {}, key=len, reverse=True):
        text = _token_re(old).sub(renames[old], text)
    return text


def level_dir(rel):
    p = (WORLDS / rel).resolve()
    if WORLDS.resolve() not in p.parents or not p.is_dir():
        raise ValueError(f"no such level: {rel}")
    return p


def materialize(rel, namespace, renames=None, dest=None):
    """Copy level `rel` (e.g. 'world-1-basics/level-1-pods') into a temp tree that keeps the repo
    layout (<tmp>/worlds/_shared, <tmp>/worlds/<world>/{_shared,world.yaml,<level>}) so a setup.sh
    that sources ../_shared/lib.sh still works, with the namespace / renames applied to every text
    file. Returns the Path of the level copy. Caller removes it with cleanup()."""
    src = level_dir(rel)
    root = Path(dest) if dest else Path(tempfile.mkdtemp(prefix="exam-lvl-"))
    wroot = root / "worlds"
    wdir = wroot / src.parent.name
    wdir.mkdir(parents=True)
    if (WORLDS / "_shared").is_dir():
        shutil.copytree(WORLDS / "_shared", wroot / "_shared")
    if (src.parent / "_shared").is_dir():
        shutil.copytree(src.parent / "_shared", wdir / "_shared")
    for extra in ("world.yaml", "heal.sh"):
        if (src.parent / extra).is_file():
            shutil.copy2(src.parent / extra, wdir / extra)
    out = wdir / src.name
    shutil.copytree(src, out, symlinks=False)
    for f in wroot.rglob("*"):
        if f.is_file() and f.suffix in TEXT_SUFFIXES:
            try:
                t = f.read_text()
            except UnicodeDecodeError:
                continue
            n = rewrite_text(t, namespace, renames)
            if n != t:
                f.write_text(n)
    return out


def cleanup(path):
    shutil.rmtree(Path(path).parents[2], ignore_errors=True)


_PINNED = {}
_HANDLERS = {"installed": False}


def _cleanup_pinned():
    """Remove the temp kubeconfig (and forget it, so a later call builds a fresh one)."""
    d = _PINNED.pop("dir", None)
    _PINNED.pop("path", None)
    if d:
        shutil.rmtree(d, ignore_errors=True)


atexit.register(_cleanup_pinned)


def install_signal_cleanup():
    """Make SIGTERM and SIGHUP exit normally, so atexit removes the temp kubeconfig."""
    import signal
    if _HANDLERS["installed"]:
        return
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, lambda signum, frame: sys.exit(128 + signum))
    _HANDLERS["installed"] = True


def pinned_kubeconfig():
    """Path of a private kubeconfig that holds only KUBE_CONTEXT, with it as current-context.

    Level scripts call a bare `kubectl`; exporting this file as KUBECONFIG makes that kubectl use the game
    cluster even if something else switches the current-context of the user's own kubeconfig. The file
    carries credentials: it lives in a 0700 temp dir, is removed at exit and on SIGTERM/SIGHUP (see
    install_signal_cleanup), and is never printed. Raises RuntimeError when it cannot be built; failures
    are not cached, so the next call tries again."""
    if _PINNED.get("path"):
        return _PINNED["path"]
    try:
        r = subprocess.run(["kubectl", "config", "view", "--minify", "--flatten", "--context", KUBE_CONTEXT],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        raise RuntimeError(f"could not build a kubeconfig pinned to {KUBE_CONTEXT}: {type(e).__name__}") from None
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError(f"could not build a kubeconfig pinned to {KUBE_CONTEXT} "
                           f"(kubectl config view exited {r.returncode}); is the context present?")
    d = tempfile.mkdtemp(prefix="exam-kc-")
    os.chmod(d, 0o700)
    p = os.path.join(d, "config")
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(r.stdout)
    _PINNED["dir"], _PINNED["path"] = d, p
    return p


def kenv(namespace=None):
    env = {**os.environ, "K8SQUEST_CONTEXT": KUBE_CONTEXT, "KUBECONFIG": pinned_kubeconfig()}
    if namespace:
        env["NAMESPACE"] = namespace      # some level scripts read ${NAMESPACE:-...} from the environment
    return env


def run(args, timeout=120, cwd=None, input=None, env=None):
    """Run a command. Every kubectl is pinned with --context, and children get the pinned kubeconfig."""
    args = list(args)
    if args and args[0] == "kubectl" and "--context" not in args:
        args[1:1] = ["--context", KUBE_CONTEXT]
    try:
        return subprocess.run(args, capture_output=True, text=True, errors="replace",
                              timeout=timeout, cwd=cwd, input=input, env=env if env is not None else kenv())
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 124, "", f"timeout after {timeout}s")
    except FileNotFoundError:
        return subprocess.CompletedProcess(args, 127, "", f"{args[0]} not found")


def _check_deletable(namespace, cluster_objects):
    """Validate every argument before anything is deleted."""
    if not isinstance(namespace, str) or not namespace.startswith("exam-"):
        raise ValueError(f"refusing to delete namespace {namespace!r}: not an exam namespace")
    for obj in cluster_objects:
        if not isinstance(obj, str) or "/" not in obj or not obj.split("/", 1)[1].startswith("exam-"):
            raise ValueError(f"refusing to delete {obj!r}: not an exam-prefixed object")


def delete_task_objects(namespace, cluster_objects=()):
    """Delete the task namespace (waiting for it to go) and its cluster-scoped objects."""
    cluster_objects = list(cluster_objects)
    _check_deletable(namespace, cluster_objects)      # before any kubectl runs
    run(["kubectl", "delete", "namespace", namespace, "--ignore-not-found", "--wait=true",
         "--timeout=150s"], timeout=170)
    for obj in cluster_objects:        # e.g. "pv/exam-t31-app-storage"
        run(["kubectl", "delete", obj, "--ignore-not-found", "--wait=true", "--timeout=90s"], timeout=110)


# Node state some tasks leave behind (t45's setup labels the node). Removed at session start so a
# solved state cannot carry into the next session. Taints are deliberately not touched.
NODE_LABEL_KEYS = ("accelerator", "gpu-type")


def reset_node_state(runner=None):
    """Remove the two exam node labels from every node and uncordon every node, kubectl pinned to the
    context. Returns a list of warning strings, empty when everything worked."""
    runner = runner or run
    warn = []
    r = runner(["kubectl", "get", "nodes", "-o", "name"], timeout=30)
    if r.returncode:
        return ["could not list nodes: " + (r.stderr or r.stdout).strip()[-200:]]
    for node in r.stdout.split():
        r = runner(["kubectl", "label", node] + [f"{k}-" for k in NODE_LABEL_KEYS], timeout=30)
        # removing a label that is not there is fine
        if r.returncode and "not found" not in (r.stderr or ""):
            warn.append(f"could not remove node labels from {node}: " + (r.stderr or r.stdout).strip()[-200:])
        r = runner(["kubectl", "uncordon", node], timeout=30)
        if r.returncode:
            warn.append(f"could not uncordon {node}: " + (r.stderr or r.stdout).strip()[-200:])
    return warn


def deploy(rel, namespace, renames=None, cluster_objects=()):
    """Fresh namespace + broken state. Returns (ok, message)."""
    delete_task_objects(namespace, cluster_objects)
    r = run(["kubectl", "create", "namespace", namespace])
    if r.returncode:
        return False, "namespace create failed: " + r.stderr.strip()[-300:]
    lvl = materialize(rel, namespace, renames)
    try:
        setup = lvl / "setup.sh"
        if setup.exists():
            r = run(["bash", "setup.sh", namespace], cwd=str(lvl), timeout=300, env=kenv(namespace))
        else:
            r = run(["kubectl", "apply", "-f", str(lvl / "broken.yaml")], timeout=120)
        ok = r.returncode == 0
        return ok, (r.stderr or r.stdout).strip()[-400:]
    finally:
        cleanup(lvl)


def validate(rel, namespace, renames=None, timeout=120):
    """Run the namespace-rewritten validate.sh. Returns (passed, output)."""
    lvl = materialize(rel, namespace, renames)
    try:
        r = run(["bash", "validate.sh"], cwd=str(lvl), timeout=timeout, env=kenv(namespace))
        out = (r.stdout or "") + (("\n" + r.stderr) if r.stderr.strip() else "")
        return r.returncode == 0, out.strip()
    finally:
        cleanup(lvl)


def apply_solution(rel, namespace, renames=None, extra=()):
    """Apply the level's solution.yaml (rewritten). Used by the e2e proof only.
    Falls back to `replace --force` when apply is refused (immutable fields)."""
    lvl = materialize(rel, namespace, renames)
    try:
        sol = str(lvl / "solution.yaml")
        for cmd in extra:       # documented manual steps the yaml cannot express, e.g. deleting the old ReplicaSet
            run(["kubectl"] + [a.replace("{ns}", namespace) for a in cmd], timeout=120)
        r = run(["kubectl", "apply", "-f", sol], timeout=120)
        if r.returncode:
            r2 = run(["kubectl", "replace", "--force", "-f", sol], timeout=180)
            return r2.returncode == 0, "apply failed, replace --force: " + (r2.stderr or r2.stdout).strip()[-300:]
        return True, r.stdout.strip()[-300:]
    finally:
        cleanup(lvl)
