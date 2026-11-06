#!/usr/bin/env python3
"""Validator hardening for levels 20, 27, 33, 52 and 59 (stub kubectl, no cluster).

Each stub answers only the calls its validate.sh really makes and honours the jsonpath it
asks for; any other call exits 1. A slow cluster is simulated by timeout: the stub's
`rollout status` / `wait` succeed only when the --timeout asked for is at least 30 s,
so a 5 s timeout rejects a fix that is merely slow.
Set VALIDATE_ROOT to run against another copy of the repo (e.g. HEAD extracted by git show).

Run: python3 -m unittest tests.test_validate_t627_5
"""
import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(os.environ.get("VALIDATE_ROOT") or Path(__file__).resolve().parent.parent)
L20 = "worlds/world-2-deployments/level-20-replicaset"
L27 = "worlds/world-3-networking/level-27-crossnamespace"
L33 = "worlds/world-4-storage/level-33-access-mode"
L52 = "worlds/world-6-cluster-architecture/level-52-kustomize-overlay"
L59 = "worlds/world-6-cluster-architecture/level-59-cri-csi-extensions"

STUBS = {}
STUBS["20"] = r'''
case "$args" in
    "get deployment web-app -n k8squest") ;;
    "get deployment web-app -n k8squest -o jsonpath={.status.readyReplicas}") printf 3 ;;
    "get deployment web-app -n k8squest -o jsonpath={.spec.replicas}") printf 3 ;;
    "get replicaset -n k8squest -o json") printf '%s' "$STUB_RS" ;;
    "get replicaset -n k8squest -l app=webapp -o name") echo replicaset.apps/web-app-abc ;;
    *) echo "unexpected kubectl call: $args" >&2; exit 1 ;;
esac
'''
STUBS["27"] = r'''
case "$args" in
    "get namespace backend-ns"|"get service api-service -n backend-ns"|"get pod frontend-app -n k8squest") ;;
    "get endpoints api-service -n backend-ns -o jsonpath={.subsets[*].addresses[*].ip}") printf 10.244.0.5 ;;
    "get pod frontend-app -n k8squest -o jsonpath={.status.phase}") printf Running ;;
    "get pod frontend-app -n k8squest -o jsonpath={.spec.containers[0].command[2]}") printf '%s' "$STUB_CMD" ;;
    "exec frontend-app -n k8squest -- wget -q -T 5 -O- http://api-service.backend-ns.svc.cluster.local")
        printf '%s' "$STUB_EXEC_OUT"; [ "$STUB_EXEC_FAIL" = 1 ] && exit 1; exit 0 ;;
    "logs frontend-app -n k8squest --tail=20") printf '%s\n' "$STUB_LOGS" ;;
    *) echo "unexpected kubectl call: $args" >&2; exit 1 ;;
esac
'''
STUBS["33"] = r'''
case "$args" in
    "get pv shared-storage"|"get deployment web-servers -n k8squest") ;;
    "get pvc shared-pvc -n k8squest -o jsonpath={.status.phase}") printf Bound ;;
    "get pv shared-storage -o json"|"get pvc shared-pvc -n k8squest -o json") printf '{"spec":{"accessModes":["ReadWriteMany"]}}' ;;
    "get deployment web-servers -n k8squest -o json")
        c=$(cat "$STUB_COUNT" 2>/dev/null || echo 0); echo $((c + 1)) > "$STUB_COUNT"
        if [ "$c" -lt "${STUB_LAG:-0}" ]; then printf '%s' "$STUB_DEP_NOTREADY"; else printf '%s' "$STUB_DEP"; fi ;;
    *) echo "unexpected kubectl call: $args" >&2; exit 1 ;;
esac
'''
STUBS["52"] = r'''
case "$args" in
    "kustomize "*) echo "kind: Deployment" ;;
    "create --dry-run=client -f - -o jsonpath="*) cat >/dev/null; echo "Deployment/3/info" ;;
    "get deployment shop-web -n k8squest") ;;
    "get deployment shop-web -n k8squest -o jsonpath={.spec.replicas}") printf 3 ;;
    "get deployment shop-web -n k8squest -o jsonpath="*LOG_LEVEL*) printf info ;;
    "rollout status deployment/shop-web -n k8squest --timeout="*) slow_ok "${args##*--timeout=}" ;;
    *) echo "unexpected kubectl call: $args" >&2; exit 1 ;;
esac
'''
STUBS["59"] = r'''
case "$args" in
    "get pvc ledger-data -n k8squest -o jsonpath={.status.phase}") printf Bound ;;
    "get deployment ledger -n k8squest -o jsonpath={.spec.template.spec.runtimeClassName}") printf gvisor ;;
    "get runtimeclass gvisor") ;;
    "wait --for=condition=Ready pod -l app=ledger -n k8squest --timeout="*) slow_ok "${args##*--timeout=}" ;;
    "get pods -n k8squest -l app=ledger") echo "ledger-0 0/1 Pending" ;;
    *) echo "unexpected kubectl call: $args" >&2; exit 1 ;;
esac
'''
PRELUDE = r'''#!/bin/bash
args="$*"
# slow_ok <timeout>: a cluster that needs 30 s; STUB_NEVER=1 is a state that never becomes ready
slow_ok() { [ "$STUB_NEVER" = 1 ] && exit 1; t=${1%s}; [ "$t" -ge 30 ] && exit 0; exit 1; }
'''


def run(level, key, env_extra=None, workdir=False):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "kubectl"
        p.write_text(PRELUDE + STUBS[key])
        p.chmod(p.stat().st_mode | stat.S_IEXEC)
        env = dict(os.environ, PATH=f"{d}:{os.environ['PATH']}", STUB_COUNT=str(Path(d) / "count"))
        if workdir:
            (Path(d) / "work" / "level-52-kustomize-overlay" / "kustomize" / "overlays" / "prod").mkdir(parents=True)
            env["K8SQUEST_WORKDIR"] = str(Path(d) / "work")
        env.update(env_extra or {})
        return subprocess.run(["bash", str(ROOT / level / "validate.sh")], env=env,
                              capture_output=True, text=True, timeout=120)


def rs(name, replicas, owner=None):
    o = {"metadata": {"name": name}, "spec": {"replicas": replicas}, "status": {"replicas": replicas}}
    if owner:
        o["metadata"]["ownerReferences"] = [{"kind": "Deployment", "name": owner}]
    return o


class Level20(unittest.TestCase):
    def go(self, items):
        return run(L20, "20", {"STUB_RS": json.dumps({"items": items})})

    def test_state_left_by_solution_sh_passes(self):
        # solution.sh deletes web-app-rs: only the Deployment's ReplicaSets remain
        self.assertEqual(self.go([rs("web-app-abc", 3, "web-app")]).returncode, 0)

    def test_only_deployment_replicaset_passes(self):
        r = self.go([rs("web-app-abc", 3, "web-app"), rs("web-app-old", 0, "web-app")])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_stopped_standalone_replicaset_passes(self):
        self.assertEqual(self.go([rs("web-app-abc", 3, "web-app"), rs("web-app-rs", 0)]).returncode, 0)

    def test_running_standalone_replicaset_rejected(self):
        r = self.go([rs("web-app-abc", 3, "web-app"), rs("web-app-rs", 3)])
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("web-app-rs", r.stdout)


class Level27(unittest.TestCase):
    GOOD = 'while true; do wget -q -O- http://api-service.backend-ns.svc.cluster.local 2>&1; sleep 5; done'
    FORGED = '# wget http://api-service.backend-ns.svc.cluster.local\nwhile true; do echo "API Response from backend-ns"; sleep 5; done'

    def go(self, cmd, out="API Response from backend-ns", fail=False):
        return run(L27, "27", {"STUB_CMD": cmd, "STUB_EXEC_OUT": out, "STUB_EXEC_FAIL": "1" if fail else "",
                               "STUB_LOGS": "API Response from backend-ns", "LEVEL27_WAIT": "0"})

    def test_real_call_passes(self):
        r = self.go(self.GOOD)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_namespace_qualified_name_passes(self):
        self.assertEqual(self.go(self.GOOD.replace(".svc.cluster.local", "")).returncode, 0)

    def test_other_correct_shapes_pass(self):
        shapes = {
            "no scheme": "while true; do wget -q -O- api-service.backend-ns.svc.cluster.local; sleep 5; done",
            "continued URL": "while true; do wget -q -O- \\\n  http://api-service.backend-ns.svc.cluster.local; sleep 5; done",
            "url in variable": "URL=http://api-service.backend-ns.svc.cluster.local\nwhile true; do wget -q -O- $URL; sleep 5; done",
            "hash earlier on the line": 'while true; do echo "#1"; wget -q -O- http://api-service.backend-ns; sleep 5; done',
            "uppercase scheme": "while true; do curl -s HTTP://api-service.backend-ns.svc; sleep 5; done",
        }
        for name, cmd in shapes.items():
            with self.subTest(shape=name):
                r = self.go(cmd.replace("\\n", "\n"))
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_forged_echo_rejected(self):
        r = self.go(self.FORGED)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertNotIn("VALIDATION PASSED", r.stdout)

    def test_unresolvable_from_client_rejected(self):
        r = self.go(self.GOOD, out="wget: bad address 'api-service.backend-ns.svc.cluster.local'", fail=True)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("DNS resolution failed", r.stdout)


class Level33(unittest.TestCase):
    READY = '{"metadata":{"generation":2},"spec":{"replicas":3},"status":{"replicas":3,"readyReplicas":3,"updatedReplicas":3,"observedGeneration":2}}'
    STUCK = '{"metadata":{"generation":2},"spec":{"replicas":3},"status":{"replicas":4,"readyReplicas":3,"updatedReplicas":1,"observedGeneration":2}}'
    NOTREADY = '{"metadata":{"generation":2},"spec":{"replicas":3},"status":{"replicas":3,"readyReplicas":0,"updatedReplicas":3,"observedGeneration":2}}'

    def go(self, dep, **extra):
        env = {"STUB_DEP": dep, "STUB_DEP_NOTREADY": self.NOTREADY, "LEVEL33_READY_WAIT": "0"}
        env.update(extra)
        return run(L33, "33", env)

    def test_ready_passes(self):
        r = self.go(self.READY)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_unready_pods_rejected(self):
        r = self.go(self.NOTREADY)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("Not all pods are ready", r.stdout)

    def test_stuck_rollout_rejected(self):
        r = self.go(self.STUCK)
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_generation_not_observed_rejected(self):
        dep = self.READY.replace('"observedGeneration":2', '"observedGeneration":1')
        r = self.go(dep)
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_slow_start_passes_within_the_wait(self):
        r = self.go(self.READY, STUB_LAG="2", LEVEL33_READY_WAIT="20")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class Level52(unittest.TestCase):
    def test_slow_rollout_passes(self):
        r = run(L52, "52", workdir=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_never_ready_rejected(self):
        r = run(L52, "52", {"STUB_NEVER": "1"}, workdir=True)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("Rollout not finished", r.stdout)


class Level59(unittest.TestCase):
    def test_slow_pod_passes(self):
        r = run(L59, "59")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_never_ready_rejected(self):
        r = run(L59, "59", {"STUB_NEVER": "1"})
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("not Ready", r.stdout)


if __name__ == "__main__":
    unittest.main()
