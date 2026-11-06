#!/usr/bin/env python3
"""A failed pod listing must fail validate.sh, not count as "0 bad pods" (levels 51, 63, 70).

Runs each validate.sh with stub kubectl/helm/docker first on PATH. The stubs answer every
earlier stage so the script reaches the pod-listing stage; the pod listing itself either
fails (STUB_PODS=fail), returns nothing (empty) or returns a healthy list (ok).
Set VALIDATE_ROOT to run against another copy of the repo (e.g. HEAD extracted by git show).

Run: python3 -m unittest tests.test_validate_failopen
"""
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(os.environ.get("VALIDATE_ROOT") or Path(__file__).resolve().parent.parent)
W6 = "worlds/world-6-cluster-architecture/level-51-helm-failed-upgrade"
W7_63 = "worlds/world-7-troubleshooting/level-63-scheduler-down"
W7_70 = "worlds/world-7-troubleshooting/level-70-troubleshooting-finale"

KUBECTL = r'''#!/bin/bash
args="$*"
pods() {
    case "$STUB_PODS" in
        fail) echo "error: api unavailable" >&2; exit 1 ;;
        empty) exit 0 ;;
        *) printf '%b' "$1"; exit 0 ;;
    esac
}
case "$args" in
    *"config current-context"*) echo kind-k8squest-multinode ;;
    *"rollout status"*) exit 0 ;;
    *"get pods -n kube-system"*) printf true ;;
    *"get deployment checkout"*"nodeName"*) printf '' ;;
    *"get deployment checkout"*) printf 3 ;;
    *"get deployment shop"*) printf 4 ;;
    *"get node "*) printf true ;;
    *"exec etcd-"*) printf '{"totalKey":5}' ;;
    *"get pods"*"app=webapp"*) pods 'nginx:1.27-alpine\nnginx:1.27-alpine\n' ;;
    *"get pods"*"app=checkout"*)
        rows="${STUB_CHECKOUT_ROWS:-c1|n1\nc2|n2\nc3|n3\n}"
        case "$args" in
            *'{.metadata.name}{"|"}{.spec.nodeName}'*) pods "$rows" ;;
            *) pods "$(printf '%b' "$rows" | awk -F'|' '{print $2}' | sed 's/$/\\n/' | tr -d '\n')" ;;
        esac ;;
    *"get pods"*"app=shop"*) pods 's1|k8squest-multinode-worker2|Running|\ns2|k8squest-multinode-worker2|Running|\ns3|k8squest-multinode-worker2|Running|\ns4|k8squest-multinode-worker2|Running|\n' ;;
    *) exit 0 ;;
esac
'''
HELM = r'''#!/bin/bash
case "$*" in
    "status"*) echo '{"status":"deployed"}' ;;
    "get manifest"*) echo 'image: "nginx:1.27-alpine"' ;;
esac
'''
DOCKER = "#!/bin/bash\nexit 0\n"


def run_validate(level, pods, **extra):
    with tempfile.TemporaryDirectory() as d:
        for name, body in (("kubectl", KUBECTL), ("helm", HELM), ("docker", DOCKER)):
            p = Path(d) / name
            p.write_text(body)
            p.chmod(p.stat().st_mode | stat.S_IEXEC)
        env = dict(os.environ, PATH=f"{d}:{os.environ['PATH']}", STUB_PODS=pods, **extra)
        env.pop("K8SQUEST_CONTEXT", None)
        return subprocess.run(["bash", str(ROOT / level / "validate.sh")], env=env,
                              capture_output=True, text=True, timeout=60)


class FailOpenTests(unittest.TestCase):
    levels = {"51": W6, "63": W7_63, "70": W7_70}

    def test_failed_listing_fails(self):
        for n, level in self.levels.items():
            with self.subTest(level=n):
                r = run_validate(level, "fail")
                self.assertNotEqual(r.returncode, 0, r.stdout)
                self.assertNotIn("SUCCESS", r.stdout)

    def test_empty_listing_fails(self):
        for n, level in self.levels.items():
            with self.subTest(level=n):
                r = run_validate(level, "empty")
                self.assertNotEqual(r.returncode, 0, r.stdout)
                self.assertNotIn("SUCCESS", r.stdout)

    def test_healthy_listing_passes(self):
        # positive control: proves the stubs really reach and pass the hardened stage
        for n, level in self.levels.items():
            with self.subTest(level=n):
                r = run_validate(level, "ok")
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn("SUCCESS", r.stdout)

    def test_level_63_nodeless_pod_listed_last_fails(self):
        # command substitution strips trailing newlines; the row must survive that
        r = run_validate(W7_63, "ok", STUB_CHECKOUT_ROWS="c1|n1\\nc2|n2\\nc3|\\n")
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn("1 checkout pod(s) have no node", r.stdout)


if __name__ == "__main__":
    unittest.main()
