#!/usr/bin/env python3
"""Validator loosening for levels 8, 12, 42 and 50 (stub kubectl, no cluster).

Each stub answers only the calls its validate.sh really makes and honours the jsonpath or
-o json it asks for; any other call exits 1. Set VALIDATE_ROOT to run against another copy
of the repo (e.g. HEAD extracted by git show).

Run: python3 -m unittest tests.test_validate_t627_6
"""
import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(os.environ.get("VALIDATE_ROOT") or Path(__file__).resolve().parent.parent)
L8 = "worlds/world-1-basics/level-8-logs"
L12 = "worlds/world-2-deployments/level-12-liveness"
L42 = "worlds/world-5-security/level-42-securitycontext"
L50 = "worlds/world-5-security/level-50-chaos-finale"

PRELUDE = '#!/bin/bash\nargs="$*"\n'
STUBS = {}
STUBS["8"] = r'''
case "$args" in
    "get pod database-app -n k8squest -o jsonpath={.status.phase}") printf Running ;;
    "get pod database-app -n k8squest -o jsonpath={.status.containerStatuses[0].ready}") printf true ;;
    "get pod database-app -n k8squest -o jsonpath={.status.containerStatuses[0].restartCount}") printf 0 ;;
    "get pod database-app -n k8squest -o jsonpath={.spec.containers[0].env[?(@.name==\"POSTGRES_PASSWORD\")].name}") printf '%s' "$STUB_ENV_NAME" ;;
    "get pod database-app -n k8squest -o json") printf '%s' "$STUB_POD_JSON" ;;
    "get configmap db-env -n k8squest -o json") printf '%s' "$STUB_CM_JSON" ;;
    "get secret db-env -n k8squest -o json") printf '%s' "$STUB_SECRET_JSON" ;;
    *) echo "unexpected kubectl call: $args" >&2; exit 1 ;;
esac
'''
STUBS["12"] = r'''
base="get deployment api-server -n k8squest -o jsonpath="
case "$args" in
    "get pods -n k8squest -l app=api -o jsonpath={.items[*].status.containerStatuses[*].restartCount}") printf '0 0' ;;
    "get pods -n k8squest -l app=api -o jsonpath={.items[?(@.status.phase==\"Running\")].metadata.name}") printf 'api-1 api-2' ;;
    "${base}{.spec.replicas}"|"${base}{.status.updatedReplicas}"|"${base}{.status.replicas}"|"${base}{.status.readyReplicas}") printf 2 ;;
    "${base}{.metadata.generation}"|"${base}{.status.observedGeneration}") printf 1 ;;
    "${base}{.spec.template.spec.containers[0].livenessProbe}") printf '{"httpGet":{"path":"%s","port":80}}' "$STUB_PATH" ;;
    "${base}{.spec.template.spec.containers[0].livenessProbe.httpGet.path}") printf '%s' "$STUB_PATH" ;;
    "${base}{.spec.template.spec.containers[0].livenessProbe.httpGet.port}") printf 80 ;;
    "get --raw /api/v1/namespaces/k8squest/pods/api-1:80/proxy"*)
        [ "${args##*/proxy}" = "$STUB_GOOD_PATH" ] && exit 0; echo 'Error from server (NotFound)' >&2; exit 1 ;;
    "exec api-1 -n k8squest -- wget"*) echo 'exec: "wget": executable file not found in $PATH' >&2; exit 126 ;;
    *) echo "unexpected kubectl call: $args" >&2; exit 1 ;;
esac
'''
STUBS["42"] = r'''
p="get pod web-app -n k8squest -o jsonpath="
case "$args" in
    "get pod web-app -n k8squest") ;;
    "${p}{.status.phase}") printf Running ;;
    "${p}{.spec.containers[0].securityContext.runAsNonRoot}") printf '%s' "$STUB_C_NONROOT" ;;
    "${p}{.spec.securityContext.runAsNonRoot}") printf '%s' "$STUB_P_NONROOT" ;;
    "${p}{.spec.containers[0].securityContext.runAsUser}") printf '%s' "$STUB_C_USER" ;;
    "${p}{.spec.securityContext.runAsUser}") printf '%s' "$STUB_P_USER" ;;
    "${p}{.spec.containers[0].securityContext.allowPrivilegeEscalation}") printf false ;;
    "exec web-app -n k8squest -- id -u") echo "$STUB_UID" ;;
    *) echo "unexpected kubectl call: $args" >&2; exit 1 ;;
esac
'''
STUBS["50"] = r'''
case "$args" in
    "get deployment chaos-app -n k8squest -o json") printf '%s' "$STUB_DEP" ;;
    "get deployment chaos-app -n k8squest") ;;
    "get serviceaccount app-sa -n k8squest"|"get role app-role -n k8squest"|"get rolebinding app-binding -n k8squest") ;;
    "get role app-role -n k8squest -o json") printf '{"rules":[{"apiGroups":[""],"resources":["pods"],"verbs":["get","list"]}]}' ;;
    "get rolebinding app-binding -n k8squest -o json") printf '{"roleRef":{"kind":"Role","name":"app-role"},"subjects":[{"kind":"ServiceAccount","name":"app-sa"}]}' ;;
    "get resourcequota chaos-quota -n k8squest -o jsonpath="*cpu*) printf 2 ;;
    "get resourcequota chaos-quota -n k8squest -o jsonpath="*memory*) printf 2Gi ;;
    "get resourcequota chaos-quota -n k8squest -o jsonpath="*pods*) printf 10 ;;
    "get networkpolicy -n k8squest -o json") printf '{"items":[{"spec":{"podSelector":{"matchLabels":{"app":"chaos"}},"policyTypes":["Ingress","Egress"],"ingress":[{"from":[{"podSelector":{}}]}],"egress":[{"to":[{"podSelector":{}}]}]}}]}' ;;
    "get priorityclass production-priority -o jsonpath={.value}") printf 1000 ;;
    "get pdb chaos-pdb -n k8squest") ;;
    "get pdb chaos-pdb -n k8squest -o jsonpath={.spec.minAvailable}") printf 1 ;;
    "get pdb chaos-pdb -n k8squest -o jsonpath={.spec.maxUnavailable}") ;;
    "get pdb chaos-pdb -n k8squest -o jsonpath={.status.disruptionsAllowed}") printf 1 ;;
    *) echo "unexpected kubectl call: $args" >&2; exit 1 ;;
esac
'''


def run(level, key, env):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "kubectl"
        p.write_text(PRELUDE + STUBS[key])
        p.chmod(p.stat().st_mode | stat.S_IEXEC)
        e = dict(os.environ, PATH=f"{d}:{os.environ['PATH']}")
        e.update(env)
        return subprocess.run(["bash", str(ROOT / level / "validate.sh")], env=e,
                              capture_output=True, text=True, timeout=120)


class Level8(unittest.TestCase):
    def go(self, envfrom, cm=None, secret=None, env_name=""):
        pod = {"spec": {"containers": [{"envFrom": envfrom}]}}
        return run(L8, "8", {"STUB_ENV_NAME": env_name, "STUB_POD_JSON": json.dumps(pod),
                             "STUB_CM_JSON": json.dumps(cm or {}), "STUB_SECRET_JSON": json.dumps(secret or {})})

    CM = {"data": {"POSTGRES_PASSWORD": "pw"}}

    def test_env_entry_still_passes(self):
        self.assertEqual(self.go([], env_name="POSTGRES_PASSWORD").returncode, 0)

    def test_envfrom_configmap_passes(self):
        r = self.go([{"configMapRef": {"name": "db-env"}}], cm=self.CM)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_envfrom_secret_passes(self):
        r = self.go([{"secretRef": {"name": "db-env"}}], secret={"data": {"POSTGRES_PASSWORD": "cHc="}})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_envfrom_prefix_applied(self):
        r = self.go([{"configMapRef": {"name": "db-env"}, "prefix": "POSTGRES_"}], cm={"data": {"PASSWORD": "pw"}})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_envfrom_without_the_key_rejected(self):
        r = self.go([{"configMapRef": {"name": "db-env"}}], cm={"data": {"OTHER": "x"}})
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_envfrom_prefix_breaking_the_name_rejected(self):
        r = self.go([{"configMapRef": {"name": "db-env"}, "prefix": "X_"}], cm=self.CM)
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_empty_value_rejected(self):
        r = self.go([{"configMapRef": {"name": "db-env"}}], cm={"data": {"POSTGRES_PASSWORD": ""}})
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_no_password_at_all_rejected(self):
        self.assertEqual(self.go([]).returncode, 1)


class Level12(unittest.TestCase):
    def go(self, path="/", good="/"):
        return run(L12, "12", {"STUB_PATH": path, "STUB_GOOD_PATH": good})

    def test_image_without_wget_passes(self):
        r = self.go()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_bad_probe_path_rejected(self):
        r = self.go(path="/nonexistent-healthz", good="/")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("does not return a success status", r.stdout)


class Level42(unittest.TestCase):
    def go(self, c_user="", p_user="", uid="101", c_nonroot="true", p_nonroot=""):
        return run(L42, "42", {"STUB_C_NONROOT": c_nonroot, "STUB_P_NONROOT": p_nonroot,
                               "STUB_C_USER": c_user, "STUB_P_USER": p_user, "STUB_UID": uid})

    def test_unset_runasuser_with_nonroot_image_passes(self):
        r = self.go()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_explicit_runasuser_passes(self):
        self.assertEqual(self.go(c_user="1000", uid="1000").returncode, 0)

    def test_runasuser_zero_rejected(self):
        r = self.go(c_user="0", uid="0")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("root (0)", r.stdout)

    def test_pod_level_runasuser_zero_rejected(self):
        self.assertEqual(self.go(p_user="0", uid="0").returncode, 1)

    def test_unset_runasuser_but_running_as_root_rejected(self):
        r = self.go(uid="0")
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_unset_runasuser_without_runasnonroot_rejected(self):
        self.assertEqual(self.go(c_nonroot="").returncode, 1)


def dep(user="1000"):
    sc = {"runAsNonRoot": True, "allowPrivilegeEscalation": False, "capabilities": {"drop": ["ALL"]}}
    pod_sc = {"runAsNonRoot": True, "seccompProfile": {"type": "RuntimeDefault"}}
    if user is not None:
        sc["runAsUser"] = int(user)
        pod_sc["runAsUser"] = int(user)
    return json.dumps({
        "metadata": {"generation": 1},
        "spec": {"replicas": 2, "template": {"spec": {
            "priorityClassName": "production-priority", "securityContext": pod_sc,
            "containers": [{"name": "app", "securityContext": sc,
                            "resources": {"requests": {"cpu": "200m", "memory": "256Mi"}}}]}}},
        "status": {"observedGeneration": 1, "readyReplicas": 2, "updatedReplicas": 2, "replicas": 2}})


class Level50(unittest.TestCase):
    def go(self, user):
        return run(L50, "50", {"STUB_DEP": dep(user)})

    def test_explicit_runasuser_passes(self):
        r = self.go("1000")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_unset_runasuser_passes(self):
        r = self.go(None)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_runasuser_zero_rejected(self):
        r = self.go("0")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("runAsUser is 0 (root)", r.stdout)


if __name__ == "__main__":
    unittest.main()
