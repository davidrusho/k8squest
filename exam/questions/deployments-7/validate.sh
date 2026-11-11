#!/bin/bash

NS="${NAMESPACE:-k8squest}"

exec python3 - "$NS" <<'PY'
import json, os, re, stat, subprocess, sys

NS = sys.argv[1]
F = "/opt/course/k8squest/d.yaml"


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

r = k("create", "--dry-run=client", "-f", "-", "-o", "json", inp=ans)
if r.returncode:
    fail("the file is not a valid manifest: " + r.stderr.strip()[-150:])
o = json.loads(r.stdout)
if o.get("kind") != "Deployment" or o["metadata"]["name"] != "api":
    fail("the file must hold Deployment api, found %s %s" % (o.get("kind"), o.get("metadata", {}).get("name")))
if o["spec"].get("replicas") != 2 or re.sub(r":latest$", "", o["spec"]["template"]["spec"]["containers"][0]["image"]) != "nginx":
    fail("the file must have 2 replicas of image nginx")
live = kjson("get", "deploy", "api", "-n", NS)
if live["spec"]["replicas"] != 2:
    fail("Deployment api has %s replicas, expected 2" % live["spec"]["replicas"])
ok("d.yaml holds Deployment api and the Deployment exists")
PY
