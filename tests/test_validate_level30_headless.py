#!/usr/bin/env python3
"""Level 30 (headless Service) validate.sh stage 5 must prove per-pod DNS read-only (stub kubectl).

The stub logs every call to $STUB_LOG and answers only the calls validate.sh really makes,
honouring the jsonpath it asks for; any other call exits 1, except the mutating verbs
(run, apply, create, delete), which succeed so a validator that uses them is caught by
the never-mutates test rather than by a crash. getent answers `<ip>  <name>` for the
per-pod names; STUB_RESOLVE_<n> overrides the answer for web-<n>, STUB_SERVICENAME and
STUB_HOSTALIASES set the StatefulSet fields.
Set VALIDATE_ROOT to run against another copy of the repo (e.g. HEAD extracted by git show).

Run: python3 -m unittest tests.test_validate_level30_headless
"""
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(os.environ.get("VALIDATE_ROOT") or Path(__file__).resolve().parent.parent)
LEVEL = "worlds/world-3-networking/level-30-headless"

KUBECTL = r'''#!/bin/bash
echo "$*" >> "$STUB_LOG"
args="$*"
case "$args" in
    "get service web-cluster -n k8squest") ;;
    "get service web-cluster -n k8squest -o jsonpath={.spec.clusterIP}") printf None ;;
    "get statefulset web -n k8squest") ;;
    "get pods -n k8squest -l app=web-cluster -o jsonpath="*) for ((k = 0; k < ${STUB_REPLICAS:-3}; k++)); do echo True; done ;;
    "get statefulset web -n k8squest -o jsonpath={.spec.replicas}") printf '%s' "${STUB_REPLICAS:-3}" ;;
    "get statefulset web -n k8squest -o jsonpath={.spec.serviceName}") printf '%s' "$STUB_SERVICENAME" ;;
    "get statefulset web -n k8squest -o jsonpath={.spec.template.spec.hostAliases}") printf '%s' "$STUB_HOSTALIASES" ;;
    "exec -n k8squest web-"*" -- getent "*"hosts web-"*".web-cluster.k8squest.svc.cluster.local")
        name=${args##* }; n=${name#web-}; n=${n%%.*}
        # lag: the first $STUB_LAG lookups fail (counter file in the stub's directory)
        c=$(cat "$STUB_COUNT" 2>/dev/null || echo 0); echo $((c + 1)) > "$STUB_COUNT"
        [ "$STUB_FAIL" = 1 ] && exit 2
        [ "$c" -lt "${STUB_LAG:-0}" ] && exit 2
        var="STUB_RESOLVE_$n"; ip=${!var:-10.244.0.1$n}
        # a pod's own name is answered from its /etc/hosts, whatever the Service says
        [ "$4" = "web-$n" ] && ip=10.244.0.1$n
        echo "fd00::1  STREAM $name"   # an IPv6 answer first: the podIP must be found among ALL addresses
        echo "$ip  STREAM $name" ;;
    "get pod web-"*" -n k8squest -o jsonpath={.status.podIP}") n=${3#web-}; [ "$STUB_EMPTY_PODIP" = 1 ] || printf '10.244.0.1%s' "$n" ;;
    "get endpoints web-cluster -n k8squest -o jsonpath="*) printf '10.244.0.10 10.244.0.11 10.244.0.12' ;;
    run*|apply*|create*|delete*|wait*) ;;
    *) echo "unexpected kubectl call: $args" >&2; exit 1 ;;
esac
'''


def run_validate(servicename="web-cluster", hostaliases="", replicas="3", extra=None, **resolve):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "kubectl"
        p.write_text(KUBECTL)
        p.chmod(p.stat().st_mode | stat.S_IEXEC)
        log = Path(d) / "calls.log"
        log.write_text("")
        env = dict(os.environ, PATH=f"{d}:{os.environ['PATH']}", STUB_LOG=str(log),
                   STUB_SERVICENAME=servicename, STUB_HOSTALIASES=hostaliases, STUB_REPLICAS=replicas,
                   STUB_COUNT=str(Path(d) / 'count'), LEVEL30_DNS_WAIT='0', LEVEL30_DNS_INTERVAL='0')
        env.update(extra or {})
        for n, ip in resolve.items():
            env[f"STUB_RESOLVE_{n}"] = ip
        r = subprocess.run(["bash", str(ROOT / LEVEL / "validate.sh")], env=env,
                           capture_output=True, text=True, timeout=120)
        return r, log.read_text().splitlines()


class Level30Tests(unittest.TestCase):
    def test_correct_resolution_passes(self):
        r, _ = run_validate()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("web-2.web-cluster.k8squest.svc.cluster.local", r.stdout)

    def test_mismatched_ip_fails(self):
        r, _ = run_validate(**{"1": "10.99.99.99"})
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("DNS mismatch: resolved to 10.99.99.99", r.stdout)

    def test_wrong_servicename_fails(self):
        r, _ = run_validate(servicename="web")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("serviceName is 'web'", r.stdout)

    def test_hostaliases_fails(self):
        r, _ = run_validate(hostaliases='[{"ip":"127.0.0.1","hostnames":["x"]}]')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("hostAliases", r.stdout)

    def test_resolves_from_a_different_pod(self):
        r, calls = run_validate()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        lookups = [c.split() for c in calls if " getent " in c]
        self.assertEqual(len(lookups), 3, calls)
        for c in lookups:
            pod, name = c[3], c[-1]
            self.assertNotEqual(name.split(".")[0], pod, f"{pod} resolved its own name")

    def test_single_replica_fails(self):
        r, _ = run_validate(replicas="1")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("expects 3", r.stdout)

    def test_getent_failure_rejected(self):
        r, _ = run_validate(extra={"STUB_FAIL": "1", "LEVEL30_DNS_WAIT": "2", "LEVEL30_DNS_INTERVAL": "1"})
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("DNS resolution failed for web-0", r.stdout)

    def test_empty_podip_rejected(self):
        r, _ = run_validate(extra={"STUB_EMPTY_PODIP": "1"})
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("no pod IP", r.stdout)

    def test_lagging_dns_passes_after_retries(self):
        r, calls = run_validate(extra={"STUB_LAG": "3", "LEVEL30_DNS_WAIT": "20", "LEVEL30_DNS_INTERVAL": "0"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_never_mutates_the_cluster(self):
        r, calls = run_validate()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(calls, "stub saw no calls")
        bad = [c for c in calls if c.split()[0] in ("run", "apply", "create", "delete", "wait")]
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
