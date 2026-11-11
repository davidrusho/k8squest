#!/bin/bash

NS="${NAMESPACE:-k8squest}"

exec python3 - "$NS" <<'PY'
import json, os, re, stat, subprocess, sys

NS = sys.argv[1]
F = "/opt/course/k8squest/notrunning.txt"


def fail(msg):
    print("❌ " + msg)
    sys.exit(1)


def ok(msg):
    print("✅ " + msg)
    sys.exit(0)


def k(*a, inp=None):
    return subprocess.run(["kubectl", *a], capture_output=True, text=True, input=inp)


def kout(*a):
    r = k(*a)
    if r.returncode:
        fail("kubectl %s failed: %s" % (a[0], r.stderr.strip()[-150:]))
    return r.stdout


def kjson(*a):
    return json.loads(kout(*a, "-o", "json"))


try:
    fd = os.open(F, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
except OSError:
    fail("answer file %s is missing (or is a symbolic link)" % F)
st = os.fstat(fd)
if not stat.S_ISREG(st.st_mode):
    fail("answer path %s is not a regular file" % F)
if st.st_size > 1048576:
    fail("answer file %s is larger than 1 MiB" % F)
with os.fdopen(fd, "r", errors="replace") as fh:
    ans = fh.read()
if not ans.strip():
    fail("answer file %s is empty" % F)
lines = [l.rstrip() for l in ans.splitlines() if l.strip()]
words = set(ans.split())


def names(skip=("NAME",)):
    """First column of each line, a leading kind/ removed, header words skipped."""
    out = []
    for l in lines:
        w = l.split()[0]
        if w in skip:
            continue
        out.append(re.sub(r"^[\w.]+/", "", w))
    return out

OTHER = "otherns"
controlled_ns = {NS, OTHER}

def not_running(ns):
    items = json.loads(kout("get", "po", "-n", ns, "--field-selector=status.phase!=Running", "-o", "json"))["items"]
    return {(ns, p["metadata"]["name"]) for p in items}

want = not_running(NS) | not_running(OTHER)
if {(NS, "stuck"), (NS, "done"), (OTHER, "blocked")} - want:
    fail("the Pods this task created are not all in the live not-Running set; reset the task")
rows = [l.split() for l in lines if l.split()[0] not in ("NAMESPACE", "NAME")]
if rows and all(len(r) == 1 and "/" in r[0] for r in rows):         # -o name: pod/<name>
    got = {re.sub(r"^pod/", "", r[0]) for r in rows}
    need = {n for _, n in want}
    absent = sorted(need - got)
    anywhere = {p["metadata"]["name"] for p in json.loads(kout("get", "po", "-A", "--field-selector=status.phase!=Running", "-o", "json"))["items"]}
    running = {p["metadata"]["name"] for p in json.loads(kout("get", "po", "-n", NS, "--field-selector=status.phase=Running", "-o", "json"))["items"]} - anywhere
    if absent:
        fail("Pods missing from the answer: %s" % ", ".join(absent))
    if got & running:
        fail("Running Pods are in the answer: %s" % ", ".join(sorted(got & running)))
    ok("the not-Running Pods are listed")
short = [l for l in lines if len(l.split()) < 2 and l.split()[0] not in ("NAMESPACE", "NAME")]
if short:
    fail("the line %r has only one column; expected the table of `k get po -A` (NAMESPACE NAME ...) or `-o name` lines" % short[0])
got = {(r[0], r[1]) for r in rows if r[0] in controlled_ns}
if got != want:
    fail("for the namespaces %s and %s the answer lists %s, expected exactly %s" % (NS, OTHER, sorted(got), sorted(want)))
ok("the not-Running Pods of all namespaces are listed")
PY
