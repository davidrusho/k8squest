#!/usr/bin/env python3
"""Level 23 (DNS) validate.sh must accept only a Service DNS name (stub kubectl, no cluster).

The stub answers only the calls validate.sh really makes and honours the jsonpath it asks
for: the command/args listing, `.spec.hostAliases` and `.status.phase` each come back only
when the args contain that exact jsonpath; `get svc <name> -n k8squest` succeeds only for
names in $STUB_SVCS; any other call exits 1, so a changed request cannot pass by accident.
Set VALIDATE_ROOT to run against another copy of the repo (e.g. HEAD extracted by git show).

Run: python3 -m unittest tests.test_validate_level23_dns
"""
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(os.environ.get("VALIDATE_ROOT") or Path(__file__).resolve().parent.parent)
LEVEL = "worlds/world-3-networking/level-23-dns"

KUBECTL = r'''#!/bin/bash
args="$*"
case "$args" in
    "get pod app-client -n k8squest -o jsonpath={.status.phase}") printf Running ;;
    "get pod app-client -n k8squest -o jsonpath={.spec.hostAliases}") printf '%s' "$STUB_HOSTALIASES" ;;
    "get pod app-client -n k8squest -o jsonpath={.spec.containers[0].command} {.spec.containers[0].args}")
        if [ -n "$STUB_CMDLINE" ]; then printf '%s' "$STUB_CMDLINE"
        else printf '["sh","-c"] ["while true; do\\n  pg_isready -h %s -p 5432 || echo failed\\n  sleep 5\\ndone\\n"]' "$STUB_HOST"; fi ;;
    "get svc "*" -n k8squest")
        svc=$3
        case ",$STUB_SVCS," in *",$svc,"*) exit 0 ;; *) exit 1 ;; esac ;;
    "exec app-client -n k8squest -- getent hosts "*) exit 0 ;;
    "exec app-client -n k8squest -- pg_isready -h "*) echo "$STUB_HOST:5432 - accepting connections" ;;
    *) echo "unexpected kubectl call: $args" >&2; exit 1 ;;
esac
'''


def run_validate(host, hostaliases="", svcs="database-service", cmdline=""):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "kubectl"
        p.write_text(KUBECTL)
        p.chmod(p.stat().st_mode | stat.S_IEXEC)
        env = dict(os.environ, PATH=f"{d}:{os.environ['PATH']}", STUB_HOST=host,
                   STUB_HOSTALIASES=hostaliases, STUB_SVCS=svcs, STUB_CMDLINE=cmdline)
        return subprocess.run(["bash", str(ROOT / LEVEL / "validate.sh")], env=env,
                              capture_output=True, text=True, timeout=60)


class Level23Tests(unittest.TestCase):
    def rejected(self, r, why=None):
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertNotIn("Level complete", r.stdout)
        if why:
            self.assertIn(why, r.stdout)

    def accepted(self, r):
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Level complete", r.stdout)

    def test_ip_host_rejected(self):
        for ip in ("10.96.12.34", "10.244.0.7"):
            with self.subTest(ip=ip):
                self.rejected(run_validate(ip), "skips DNS")

    def test_hostaliases_rejected(self):
        self.rejected(run_validate("database", hostaliases='[{"ip":"10.96.0.9","hostnames":["database"]}]',
                                   svcs="database,database-service"), "hostAliases")

    def test_unknown_service_rejected(self):
        self.rejected(run_validate("database"), "no Service named")

    def test_other_namespace_fqdn_rejected(self):
        for h in ("database-service.other", "database-service.other.svc.cluster.local",
                  "database-service.k8squest.svc.example.com"):
            with self.subTest(host=h):
                self.rejected(run_validate(h), "not a Service name in the k8squest namespace")

    def test_short_name_accepted(self):
        self.accepted(run_validate("database-service"))
        self.accepted(run_validate("database", svcs="database,database-service"))

    def test_quoted_shell_string_accepted(self):
        # args printed as JSON: pg_isready -h \"database-service\" arrives with escaped quotes
        self.accepted(run_validate("database-service", cmdline='[] ["pg_isready -h \\"database-service\\" -p 5432"]'))

    def test_exec_list_accepted(self):
        self.accepted(run_validate("database-service", cmdline='["pg_isready","-h","database-service","-p","5432"] '))

    def test_variable_host_rejected(self):
        self.rejected(run_validate("x", cmdline='["sh","-c"] ["pg_isready -h $DB_HOST -p 5432"]'), "variable")

    def test_echo_only_client_rejected(self):
        self.rejected(run_validate("x", cmdline='["sh","-c"] ["echo database-service:5432 - accepting connections"]'),
                      "does not run a pg_isready")

    def test_uppercase_host_accepted(self):
        self.accepted(run_validate("Database-Service"))

    def test_fqdn_accepted(self):
        for h in ("database-service.k8squest", "database-service.k8squest.svc",
                  "database-service.k8squest.svc.cluster.local",
                  "database-service.k8squest.svc.cluster.local."):
            with self.subTest(host=h):
                self.accepted(run_validate(h))


if __name__ == "__main__":
    unittest.main()
