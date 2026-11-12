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
QUESTIONS = REPO / "exam" / "questions"
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


def is_question(rel):
    return isinstance(rel, str) and rel.startswith("questions/")


def level_dir(rel):
    root, sub = (QUESTIONS, rel[len("questions/"):]) if is_question(rel) else (WORLDS, rel)
    p = (root / sub).resolve()
    if root.resolve() not in p.parents or not p.is_dir():
        raise ValueError(f"no such level: {rel}")
    return p


_ROOTS = set()      # temp trees materialize() created; cleanup() removes only these


def materialize(rel, namespace, renames=None, dest=None):
    """Copy level `rel` (e.g. 'world-1-basics/level-1-pods') into a temp tree that keeps the repo
    layout (<tmp>/worlds/_shared, <tmp>/worlds/<world>/{_shared,world.yaml,<level>}) so a setup.sh
    that sources ../_shared/lib.sh still works, with the namespace / renames applied to every text
    file. Returns the Path of the level copy. Caller removes it with cleanup()."""
    src = level_dir(rel)
    root = Path(dest) if dest else Path(tempfile.mkdtemp(prefix="exam-lvl-"))
    _ROOTS.add(root.resolve())
    if is_question(rel):        # a question task is one directory: <tmp>/questions/<qid>
        qroot = root / "questions"
        qroot.mkdir(parents=True)
        out = qroot / src.name
        shutil.copytree(src, out, symlinks=False)
        _rewrite_tree(qroot, namespace, renames)
        return out
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
    _rewrite_tree(wroot, namespace, renames)
    return out


def _rewrite_tree(tree, namespace, renames):
    for f in tree.rglob("*"):
        if f.is_file() and f.suffix in TEXT_SUFFIXES:
            try:
                t = f.read_text()
            except UnicodeDecodeError:
                continue
            n = rewrite_text(t, namespace, renames)
            if n != t:
                f.write_text(n)


def cleanup(path):
    """Remove the whole temp tree: <tmp>/worlds/<world>/<level> (3 deep) or <tmp>/questions/<qid> (2 deep)."""
    path = Path(path)
    root = (path.parents[1] if path.parent.name == "questions" else path.parents[2]).resolve()
    if root not in _ROOTS:
        raise ValueError(f"refusing to remove {root}: not a temp tree created by materialize()")
    _ROOTS.discard(root)
    shutil.rmtree(root, ignore_errors=True)


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


TASK_PREFIXES = ("exam-", "drill-")


def _check_deletable(namespace, cluster_objects):
    """Validate every argument before anything is deleted: an exam- or drill- namespace, and cluster-scoped
    objects carrying the same prefix."""
    if not isinstance(namespace, str) or not namespace.startswith(TASK_PREFIXES):
        raise ValueError(f"refusing to delete namespace {namespace!r}: not an exam or drill namespace")
    prefix = "exam-" if namespace.startswith("exam-") else "drill-"
    for obj in cluster_objects:
        if not isinstance(obj, str) or "/" not in obj or not obj.split("/", 1)[1].startswith(prefix):
            raise ValueError(f"refusing to delete {obj!r}: not a {prefix}prefixed object")


def delete_task_objects(namespace, cluster_objects=()):
    """Delete the task namespace (waiting for it to go) and its cluster-scoped objects."""
    cluster_objects = list(cluster_objects)
    _check_deletable(namespace, cluster_objects)      # before any kubectl runs
    run(["kubectl", "delete", "namespace", namespace, "--ignore-not-found", "--wait=true",
         "--timeout=150s"], timeout=170)
    for obj in cluster_objects:        # e.g. "pv/exam-t31-app-storage"
        run(["kubectl", "delete", obj, "--ignore-not-found", "--wait=true", "--timeout=90s"], timeout=110)


# Node state some tasks leave behind (t45's setup and the node drill tasks label, taint and cordon the node).
# Removed at session start and before every drill deploy so a solved or abandoned state cannot carry into
# the next task. Only the keys below are touched: any other label or taint of the node is left alone.
NODE_LABEL_KEYS = ("accelerator", "gpu-type", "disk")
NODE_TAINT_KEYS = ("dedicated",)


def reset_node_state(runner=None):
    """Remove the exam/drill node labels and taints (NODE_LABEL_KEYS, NODE_TAINT_KEYS) from every node and
    uncordon every node, kubectl pinned to the context. Returns a list of warning strings, empty when
    everything worked."""
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
        for key in NODE_TAINT_KEYS:
            r = runner(["kubectl", "taint", "nodes", node.split("/", 1)[-1], f"{key}-"], timeout=30)
            # removing a taint that is not there is fine
            if r.returncode and "not found" not in (r.stderr or ""):
                warn.append(f"could not remove taint {key} from {node}: " + (r.stderr or r.stdout).strip()[-200:])
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


# ---- kubeadm tasks: they run on the two-VM kubeadm cluster, not on kind. Every step goes through the root helper
# (exam/hosts/cka-kubeadm, deployed to /usr/local/sbin); the Proxmox token never reaches this process.
KUBEADM_HELPER = ["sudo", "-n", "/usr/local/sbin/cka-kubeadm"]
KUBEADM_TASK_NS = "kubeadm"       # materialize() needs a namespace; kubeadm task files do not use the token


_TOKEN_RE = re.compile(r"PVEAPIToken=\S+")


# Timeouts, so that this side never gives up before the helper does. The helper waits for its root lock (ensure-up and
# rollback up to 420 s, run-on up to 60 s) and then runs: rollback or ensure-up up to 420 s, run-on up to its --timeout.
# rollback / ensure-up: 420 + 420 = 840 s worst case -> 900 s here.
# setup / solution: 60 + 240 = 300 s -> 330 s here. validate.sh makes one run-on --timeout 150: 60 + 150 = 210 s -> 240 s here.
RUN_ON_SECONDS = 240
KUBEADM_STEP_TIMEOUT = 900
KUBEADM_SCRIPT_TIMEOUT = 330
KUBEADM_VALIDATE_TIMEOUT = 240


def _kubeadm_helper(args, timeout, input=None, stdout=False):
    """(ok, message), or (ok, message, stdout) when stdout=True. The message is stderr only and goes to the browser,
    so anything shaped like the Proxmox token is redacted first."""
    r = run(KUBEADM_HELPER + list(args), timeout=timeout, input=input, env=dict(os.environ))
    text = _TOKEN_RE.sub("PVEAPIToken=<redacted>", (r.stderr or ("" if stdout else r.stdout)))
    res = (r.returncode == 0, text.strip()[-400:])
    return res + (r.stdout or "",) if stdout else res


def kubeadm_generation():
    """The helper's rollback generation: a random token replaced at the start of every rollback attempt ("none" before the
    first). Compared for equality only. Raises RuntimeError when it cannot be read."""
    r = run(KUBEADM_HELPER + ["generation"], timeout=60, env=dict(os.environ))
    out = (r.stdout or "").strip()
    if r.returncode != 0 or not re.fullmatch(r"[0-9a-f]{16}|none", out):
        raise RuntimeError("could not read the kubeadm cluster generation: " + _TOKEN_RE.sub("<redacted>", (r.stderr or ""))[-200:])
    return out


def kubeadm_rollback():
    """Roll both VMs back to the clean snapshot, start them and wait for the cluster. Returns (ok, message, generation):
    the generation comes from the helper's own `GENERATION=<token>` stdout line (None on failure)."""
    ok, msg, out = _kubeadm_helper(["rollback"], KUBEADM_STEP_TIMEOUT, stdout=True)
    m = re.search(r"^GENERATION=([0-9a-f]{16})$", out, re.M)
    if ok and not m:
        return False, "the helper did not report a generation", None
    return ok, msg, (m.group(1) if ok else None)


def kubeadm_ensure_up():
    """Start a stopped VM and wait for the cluster, without any rollback. Returns (ok, message)."""
    return _kubeadm_helper(["ensure-up"], KUBEADM_STEP_TIMEOUT)


def _kubeadm_script(rel, name):
    """Run <name> (setup.sh or solution.sh) of a kubeadm task as root on controlplane, or on node01 when its first
    line is `# node: node01`. A missing file is fine. Returns (ok, message)."""
    lvl = materialize(rel, KUBEADM_TASK_NS)
    try:
        f = lvl / name
        if not f.is_file():
            return True, ""
        text = f.read_text()
        if not text.strip():
            return False, "%s is empty" % name
        head = ([l.strip() for l in text.split("\n", 2)[:2]] + ["", ""])[:2]       # a one-line file has no line 2
        # the directive is line 1, or line 2 after a shebang
        node = "node01" if head[0] == "# node: node01" or (head[0].startswith("#!") and head[1] == "# node: node01") else "controlplane"
        return _kubeadm_helper(["run-on", "--timeout", str(RUN_ON_SECONDS), node], KUBEADM_SCRIPT_TIMEOUT, input=text)
    finally:
        cleanup(lvl)


def kubeadm_setup(rel):
    return _kubeadm_script(rel, "setup.sh")


def kubeadm_solution(rel):
    """The task's solution.sh, run like setup.sh. Used by the e2e proof only."""
    return _kubeadm_script(rel, "solution.sh")


def kubeadm_validate(rel, timeout=KUBEADM_VALIDATE_TIMEOUT):
    """Run validate.sh on this host (as david); it reaches the VMs through the helper. Returns (passed, output)."""
    lvl = materialize(rel, KUBEADM_TASK_NS)
    try:
        # KUBECONFIG=/dev/null: a bare kubectl in a validator must fail rather than silently use the kind cluster
        r = run(["bash", "validate.sh"], cwd=str(lvl), timeout=timeout, env={**os.environ, "KUBECONFIG": "/dev/null"})
        out = (r.stdout or "") + (("\n" + r.stderr) if r.stderr.strip() else "")
        return r.returncode == 0, out.strip()
    finally:
        cleanup(lvl)


def level_texts(rel, namespace, renames=None):
    """The level's player-facing text, rewritten like the deployed copy: {"hints": [h1, h2, h3], "solution", "debrief"}.
    A missing file gives None. Reads files only; the level directory is never modified."""
    src = level_dir(rel)

    def read(name):
        try:
            return rewrite_text((src / name).read_text(), namespace, renames).strip()
        except (OSError, UnicodeDecodeError):
            return None
    return {"hints": [read(f"hint-{i}.txt") for i in (1, 2, 3)],
            "solution": read("solution.sh") if is_question(rel) else read("solution.yaml"),
            "debrief": read("debrief.md")}


def apply_solution(rel, namespace, renames=None, extra=()):
    """Apply the level's solution.yaml (rewritten), or run its solution.sh for a question task. Used by the e2e proof only.
    Falls back to `replace --force` when apply is refused (immutable fields)."""
    lvl = materialize(rel, namespace, renames)
    try:
        if is_question(rel) and (lvl / "solution.sh").is_file():     # a question task: the answer is commands, not a manifest
            for cmd in extra:
                run(["kubectl"] + [a.replace("{ns}", namespace) for a in cmd], timeout=120)
            r = run(["bash", "solution.sh"], cwd=str(lvl), timeout=180, env=kenv(namespace))
            return r.returncode == 0, (r.stderr or r.stdout).strip()[-300:]
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
