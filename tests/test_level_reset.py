#!/usr/bin/env python3
# Added 2026 by David Rusho; see CHANGES.md
"""Tests for engine/level_reset.py using a stub kubectl on PATH (no cluster needed).

The stub logs every call to $STUB_LOG, answers `get <kind> -o name` from $STUB_OBJECTS
(JSON: kind -> [names]), `config current-context` from $STUB_CONTEXT, and can be told
to fail with $STUB_FAIL ("<verb> <kind-or-key>" -> stderr text).

Run: python3 tests/test_level_reset.py   (or python3 -m unittest tests.test_level_reset)
"""
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent / "engine"
sys.path.insert(0, str(ENGINE))
import level_reset  # noqa: E402

STUB = r'''#!/usr/bin/env python3
import json, os, sys
a = sys.argv[1:]
open(os.environ["STUB_LOG"], "a").write(json.dumps(a) + "\n")
fail = json.loads(os.environ.get("STUB_FAIL", "{}"))
if a[:2] == ["config", "current-context"]:
    print(os.environ.get("STUB_CONTEXT", "kind-k8squest")); sys.exit(0)
if a[0] == "get":
    print("\n".join(json.loads(os.environ["STUB_OBJECTS"]).get(a[1], []))); sys.exit(0)
for k, msg in fail.items():
    if k in " ".join(a):
        sys.stderr.write(msg); sys.exit(1)
sys.exit(0)
'''

OBJECTS = {
    "roles": ["role.rbac.authorization.k8s.io/k8squest-player-role", "role.rbac.authorization.k8s.io/level-role"],
    "rolebindings": ["rolebinding.rbac.authorization.k8s.io/k8squest-player-binding",
                     "rolebinding.rbac.authorization.k8s.io/level-binding"],
    "serviceaccounts": ["serviceaccount/default", "serviceaccount/k8squest-player", "serviceaccount/level-sa"],
    "configmaps": ["configmap/kube-root-ca.crt", "configmap/level-cm"],
}


class StubKubectl(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        (d / "kubectl").write_text(STUB)
        (d / "kubectl").chmod((d / "kubectl").stat().st_mode | stat.S_IXUSR)
        self.log = d / "calls.log"
        self.log.write_text("")
        self.env = {"PATH": f"{d}{os.pathsep}{os.environ['PATH']}", "STUB_LOG": str(self.log),
                    "STUB_OBJECTS": json.dumps(OBJECTS), "STUB_CONTEXT": "kind-k8squest"}
        self._saved = {k: os.environ.get(k) for k in list(self.env) + ["K8SQUEST_ALLOW_CONTEXT", "K8S_CLUSTER_TYPE", "STUB_FAIL"]}
        os.environ.update(self.env)
        for k in ("K8SQUEST_ALLOW_CONTEXT", "K8S_CLUSTER_TYPE", "STUB_FAIL"):
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def calls(self):
        return [json.loads(l) for l in self.log.read_text().splitlines() if l]

    def deleted(self):
        names = []
        for c in self.calls():
            if c[0] == "delete":
                names += [x for x in c if "/" in x]
        return names

    def test_player_rbac_survives_and_level_objects_are_deleted(self):
        self.assertEqual(level_reset.clear_leftovers("k8squest"), [])
        deleted = self.deleted()
        for keep in ("k8squest-player-role", "k8squest-player-binding", "serviceaccount/k8squest-player",
                     "serviceaccount/default", "configmap/kube-root-ca.crt"):
            self.assertFalse(any(d.endswith(keep) or d == keep for d in deleted), f"{keep} was deleted: {deleted}")
        for gone in ("role.rbac.authorization.k8s.io/level-role", "rolebinding.rbac.authorization.k8s.io/level-binding",
                     "serviceaccount/level-sa", "configmap/level-cm"):
            self.assertIn(gone, deleted)

    def test_no_wildcard_delete_of_roles_or_rolebindings(self):
        level_reset.clear_leftovers("k8squest")
        for c in self.calls():
            if c[0] == "delete":
                self.assertFalse({"roles", "rolebindings", "serviceaccounts"} & set(c) and "--all" in c, c)

    def test_taint_and_label_not_found_is_success(self):
        os.environ["STUB_FAIL"] = json.dumps({"taint nodes": 'taint "dedicated" not found',
                                              "label nodes": 'label "accelerator" not found'})
        self.assertEqual(level_reset.clear_leftovers("k8squest"), [])

    def test_failures_are_returned_with_stderr(self):
        os.environ["STUB_FAIL"] = json.dumps({"resourcequotas": "forbidden: nope", "taint nodes": "connection refused"})
        failed = dict(level_reset.clear_leftovers("k8squest"))
        self.assertIn("forbidden: nope", failed.get("delete resourcequotas", ""))
        self.assertIn("connection refused", failed.get("taint dedicated-", ""))
        self.assertIn("delete resourcequotas", level_reset.describe_failures(list(failed.items())))

    def test_node_edits_skipped_on_foreign_context_and_reported(self):
        os.environ["STUB_CONTEXT"] = "some-prod-cluster"
        failed = level_reset.clear_leftovers("k8squest")
        self.assertTrue(any(s == "node taints/labels" for s, _ in failed))
        self.assertFalse([c for c in self.calls() if c[0] in ("taint", "label")])

    def test_contexts(self):
        for ctx, want in (("kind-k8squest", True), ("k3s-k8squest", True), ("minikube", False)):
            os.environ["STUB_CONTEXT"] = ctx
            self.assertEqual(level_reset.on_game_cluster(), want, ctx)
        os.environ["STUB_CONTEXT"] = "minikube"
        os.environ["K8SQUEST_ALLOW_CONTEXT"] = "1"
        self.assertTrue(level_reset.on_game_cluster())

    def test_expected_context_follows_cluster_type(self):
        self.assertEqual(level_reset.expected_context(), "kind-k8squest")
        os.environ["K8S_CLUSTER_TYPE"] = "k3s"
        self.assertEqual(level_reset.expected_context(), "k3s-k8squest")


if __name__ == "__main__":
    unittest.main(verbosity=2)
