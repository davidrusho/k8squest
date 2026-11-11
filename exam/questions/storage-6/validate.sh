#!/bin/bash

NS="${NAMESPACE:-k8squest}"

exec python3 - "$NS" <<'PY'
import json, os, re, stat, subprocess, sys

NS = sys.argv[1]
F = "/opt/course/k8squest/defaultsc.txt"


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

d = [s["metadata"]["name"] for s in kjson("get", "sc")["items"]
     if s["metadata"].get("annotations", {}).get("storageclass.kubernetes.io/is-default-class") == "true"]
if len(d) != 1:
    fail("expected exactly one default StorageClass, found %s" % d)
good = ans.strip() == d[0] or re.fullmatch(r"storageclass(\.storage\.k8s\.io)?/%s" % re.escape(d[0]), ans.strip()) or any(re.match(r"^%s\s+\(default\)" % re.escape(d[0]), l) for l in lines)
if not good or any("(default)" in l and not l.startswith(d[0]) for l in lines):
    fail("the answer must name %r as the default StorageClass" % d[0])
ok("the default StorageClass is named")
PY
