#!/bin/bash

NS="${NAMESPACE:-k8squest}"

exec python3 - "$NS" <<'PY'
import json, os, re, stat, subprocess, sys

NS = sys.argv[1]
F = "/opt/course/k8squest/nodelabels.txt"


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

def token(text):
    return r"(?<![\w./-])" + re.escape(text) + r"(?![\w./-])"

def has_label(key, v):
    # k=v, k: v (YAML) and "k": "v" (JSON), each as a whole token
    q = "[" + chr(34) + chr(39) + "]?"
    return bool(re.search(token(key + "=" + v), ans) or
                re.search(r"(?<![\w./-])" + q + re.escape(key) + q + r":\s*" + q + re.escape(v) + q + r"(?![\w./-])", ans))

for n in kjson("get", "no")["items"]:
    name = n["metadata"]["name"]
    miss = ["%s=%s" % kv for kv in n["metadata"].get("labels", {}).items() if not has_label(*kv)]
    if not re.search(token(name), ans) or miss:
        fail("node %s or its labels are missing from the answer: %s" % (name, ", ".join(miss[:3])))
ok("the labels of all nodes are listed")
PY
