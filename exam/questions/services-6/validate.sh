#!/bin/bash

NS="${NAMESPACE:-k8squest}"

exec python3 - "$NS" <<'PY'
import json, os, re, stat, subprocess, sys

NS = sys.argv[1]
F = "/opt/course/k8squest/endpoints.txt"


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

sl = kjson("get", "endpointslices", "-n", NS, "-l", "kubernetes.io/service-name=web-svc")
ips = [a for i in sl["items"] for e in i.get("endpoints", []) for a in e.get("addresses", [])]
if len(ips) < 2:
    fail("the Service has fewer than 2 ready endpoints right now: %s" % ips)
has_ip = lambda ip: re.search(r"(?<![\d.])%s(?![\d.])" % re.escape(ip), ans)
miss = [ip for ip in ips if not has_ip(ip)]
if miss:
    fail("endpoint IPs missing from the answer: %s" % ", ".join(miss))
if "web-svc" not in ans and "Endpoints" not in ans:
    fail("the answer must be the endpoints output of web-svc")
ok("all endpoint IPs are listed")
PY
