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

KIND_STUB = r'''#!/usr/bin/env python3
import os, sys
a = sys.argv[1:]
open(os.environ["STUB_LOG"], "a").write("KIND " + " ".join(a) + "\n")
if a[:2] == ["get", "clusters"]:
    print(os.environ.get("STUB_KIND_CLUSTERS", "k8squest")); sys.exit(0)
if a[:2] == ["create", "cluster"] and os.environ.get("STUB_KIND_FAIL"):
    sys.stderr.write("docker is not running"); sys.exit(1)
sys.exit(0)
'''

DOCKER_STUB = r'''#!/usr/bin/env python3
import os, sys
a = sys.argv[1:]
open(os.environ["STUB_LOG"], "a").write("DOCKER " + " ".join(a) + "\n")
if a[:1] == ["inspect"]:
    print(os.environ.get("STUB_DOCKER_RUNNING", "true")); sys.exit(0 if os.environ.get("STUB_DOCKER_RUNNING", "true") != "missing" else 1)
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
        (d / "docker").write_text(DOCKER_STUB)
        (d / "docker").chmod((d / "docker").stat().st_mode | stat.S_IXUSR)
        (d / "kind").write_text(KIND_STUB)
        (d / "kind").chmod((d / "kind").stat().st_mode | stat.S_IXUSR)
        self.log = d / "calls.log"
        self.log.write_text("")
        self.env = {"PATH": f"{d}{os.pathsep}{os.environ['PATH']}", "STUB_LOG": str(self.log),
                    "STUB_OBJECTS": json.dumps(OBJECTS), "STUB_CONTEXT": "kind-k8squest"}
        self._saved = {k: os.environ.get(k) for k in list(self.env) + ["K8SQUEST_ALLOW_CONTEXT", "K8S_CLUSTER_TYPE", "STUB_FAIL", "STUB_KIND_CLUSTERS", "STUB_KIND_FAIL", "STUB_DOCKER_RUNNING"]}
        os.environ.update(self.env)
        self._saved_limit_file = level_reset.INOTIFY_LIMIT_FILE
        level_reset.INOTIFY_LIMIT_FILE = str(d / "no-such-inotify-file")   # tests never read the host's limit
        for k in ("K8SQUEST_ALLOW_CONTEXT", "K8S_CLUSTER_TYPE", "STUB_FAIL", "STUB_KIND_CLUSTERS", "STUB_KIND_FAIL", "STUB_DOCKER_RUNNING"):
            os.environ.pop(k, None)

    def tearDown(self):
        level_reset.INOTIFY_LIMIT_FILE = self._saved_limit_file
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def calls(self):
        return [json.loads(l) for l in self.log.read_text().splitlines()
                if l and not l.startswith(("KIND ", "DOCKER "))]

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

    # ---- cluster type -> kubectl context (the one mapping the engine, reset.py, harness and scripts share)

    def test_context_for_each_cluster_type(self):
        self.assertEqual(level_reset.context_for("kind"), "kind-k8squest")
        self.assertEqual(level_reset.context_for("kind-multinode"), "kind-k8squest-multinode")
        os.environ["K8S_CLUSTER_TYPE"] = "k3s"
        self.assertEqual(level_reset.context_for("kind"), "k3s-k8squest")
        self.assertEqual(level_reset.context_for("kind-multinode"), "kind-k8squest-multinode")
        with self.assertRaises(ValueError):
            level_reset.context_for("lima")

    def test_multinode_context_is_a_game_cluster(self):
        os.environ["STUB_CONTEXT"] = "kind-k8squest-multinode"
        self.assertTrue(level_reset.on_game_cluster())

    def test_real_worlds_declare_the_clusters_the_scripts_expect(self):
        worlds = Path(__file__).resolve().parent.parent / "worlds"
        w6 = next(worlds.glob("world-6-*")) / "level-51-helm-failed-upgrade"
        w7 = next(worlds.glob("world-7-*")) / "level-61-kubelet-stopped"
        self.assertEqual(level_reset.world_cluster(w6), "kind")
        self.assertEqual(level_reset.world_cluster(w7), "kind-multinode")
        self.assertEqual(level_reset.level_env(w6)["K8SQUEST_CONTEXT"], "kind-k8squest")
        self.assertEqual(level_reset.level_env(w7)["K8SQUEST_CONTEXT"], "kind-k8squest-multinode")

    def test_ensure_world_cluster_creates_missing_multinode_and_switches(self):
        os.environ["STUB_KIND_CLUSTERS"] = "k8squest"
        os.environ["STUB_CONTEXT"] = "kind-k8squest"
        msgs = []
        ok, why = level_reset.ensure_world_cluster("kind-multinode", ENGINE.parent, say=msgs.append)
        self.assertEqual((ok, why), (True, ""))
        kind_calls = [l for l in self.log.read_text().splitlines() if l.startswith("KIND create")]
        self.assertEqual(len(kind_calls), 1)
        self.assertIn("--name k8squest-multinode", kind_calls[0])
        self.assertIn("kind/multinode.yaml", kind_calls[0])
        self.assertIn("--wait 180s", kind_calls[0])
        self.assertIn(["config", "use-context", "kind-k8squest-multinode"], self.calls())
        self.assertTrue(any("kind create cluster" in m for m in msgs), msgs)

    def test_ensure_world_cluster_leaves_an_existing_multinode_cluster_alone(self):
        os.environ["STUB_KIND_CLUSTERS"] = "k8squest\nk8squest-multinode"
        os.environ["STUB_CONTEXT"] = "kind-k8squest-multinode"
        self.assertEqual(level_reset.ensure_world_cluster("kind-multinode", ENGINE.parent, say=lambda m: None), (True, ""))
        self.assertFalse([l for l in self.log.read_text().splitlines() if l.startswith("KIND create")])
        self.assertFalse([c for c in self.calls() if c[:2] == ["config", "use-context"]])

    def test_ensure_world_cluster_switches_back_for_a_kind_world(self):
        os.environ["STUB_CONTEXT"] = "kind-k8squest-multinode"
        self.assertEqual(level_reset.ensure_world_cluster("kind", ENGINE.parent, say=lambda m: None), (True, ""))
        self.assertIn(["config", "use-context", "kind-k8squest"], self.calls())
        self.assertFalse([l for l in self.log.read_text().splitlines() if l.startswith("KIND create")])

    def test_ensure_world_cluster_reports_a_failed_create_and_does_not_switch(self):
        os.environ["STUB_KIND_CLUSTERS"] = ""
        os.environ["STUB_KIND_FAIL"] = "1"
        ok, why = level_reset.ensure_world_cluster("kind-multinode", ENGINE.parent, say=lambda m: None)
        self.assertFalse(ok)
        self.assertIn("docker is not running", why)
        self.assertFalse([c for c in self.calls() if c[:2] == ["config", "use-context"]])

    # ---- inotify preflight before creating the multinode cluster

    def _limit_file(self, text):
        f = Path(self.tmp.name) / "max_user_instances"
        if text is not None:
            f.write_text(text)
        level_reset.INOTIFY_LIMIT_FILE = str(f)

    def _creates(self):
        return [l for l in self.log.read_text().splitlines() if l.startswith("KIND create")]

    def test_low_inotify_limit_refuses_and_does_not_create(self):
        self._limit_file("128\n")
        os.environ["STUB_KIND_CLUSTERS"] = "k8squest"
        ok, why = level_reset.ensure_world_cluster("kind-multinode", ENGINE.parent, say=lambda m: None)
        self.assertFalse(ok)
        self.assertIn("sudo sysctl fs.inotify.max_user_instances=512", why)
        self.assertIn("/etc/sysctl.d/", why)
        self.assertIn("kind.sigs.k8s.io/docs/user/known-issues", why)
        self.assertEqual(self._creates(), [])

    def test_inotify_limit_at_or_above_minimum_proceeds(self):
        for val in ("512", "8192"):
            self._limit_file(val)
            os.environ["STUB_KIND_CLUSTERS"] = "k8squest"
            self.log.write_text("")
            self.assertEqual(level_reset.ensure_world_cluster("kind-multinode", ENGINE.parent, say=lambda m: None), (True, ""), val)
            self.assertEqual(len(self._creates()), 1, val)

    def test_missing_inotify_file_proceeds(self):
        self._limit_file(None)   # path set, file absent (macOS / Docker Desktop)
        os.environ["STUB_KIND_CLUSTERS"] = "k8squest"
        self.assertEqual(level_reset.ensure_world_cluster("kind-multinode", ENGINE.parent, say=lambda m: None), (True, ""))
        self.assertEqual(len(self._creates()), 1)

    def test_inotify_limit_not_checked_when_cluster_exists_or_for_kind_world(self):
        self._limit_file("128")
        os.environ["STUB_KIND_CLUSTERS"] = "k8squest\nk8squest-multinode"
        self.assertEqual(level_reset.ensure_world_cluster("kind-multinode", ENGINE.parent, say=lambda m: None), (True, ""))
        self.assertEqual(level_reset.ensure_world_cluster("kind", ENGINE.parent, say=lambda m: None), (True, ""))

    def test_harness_exits_nonzero_when_a_level_is_skipped(self):
        """A skipped level is not a proven one: the harness must not exit 0 for it."""
        os.environ["STUB_KIND_CLUSTERS"] = ""
        os.environ["STUB_KIND_FAIL"] = "1"
        harness = ENGINE.parent / "tests" / "level_harness.py"
        r = subprocess.run([sys.executable, str(harness), "--level", "level-61-kubelet-stopped"],
                           capture_output=True, text=True, timeout=120)
        self.assertIn("1 skip", r.stdout)
        self.assertEqual(r.returncode, 1, r.stdout[-400:])

    # ---- missing tools, failed follow-up applies, half-dead existing cluster

    def test_run_reports_a_missing_binary_as_rc_127(self):
        r = level_reset._run(["definitely-not-installed-xyz", "--version"])
        self.assertEqual(r.returncode, 127)
        self.assertIn("definitely-not-installed-xyz not found on PATH", r.stderr)

    def test_missing_kind_is_a_clear_message_not_a_traceback(self):
        empty = Path(self.tmp.name) / "empty-bin"
        empty.mkdir()
        os.environ["PATH"] = str(empty)
        try:
            ok, why = level_reset.ensure_world_cluster("kind-multinode", ENGINE.parent, say=lambda m: None)
        finally:
            os.environ["PATH"] = self.env["PATH"]
        self.assertFalse(ok)
        self.assertIn("not found on PATH", why)

    def test_failed_namespace_apply_after_create_is_reported(self):
        os.environ["STUB_KIND_CLUSTERS"] = "k8squest"
        os.environ["STUB_FAIL"] = json.dumps({"apply": "namespaces is forbidden"})
        ok, why = level_reset.ensure_world_cluster("kind-multinode", ENGINE.parent, say=lambda m: None)
        self.assertFalse(ok)
        self.assertIn("namespace could not be applied", why)
        self.assertIn("forbidden", why)

    def test_existing_cluster_with_a_dead_node_container_says_to_delete_it(self):
        os.environ["STUB_KIND_CLUSTERS"] = "k8squest\nk8squest-multinode"
        os.environ["STUB_DOCKER_RUNNING"] = "false"
        ok, why = level_reset.ensure_world_cluster("kind-multinode", ENGINE.parent, say=lambda m: None)
        self.assertFalse(ok)
        self.assertIn("kind delete cluster --name k8squest-multinode", why)
        self.assertIn("start the level again", why)
        self.assertFalse([c for c in self.calls() if c[:2] == ["config", "use-context"]])


class World7Guard(unittest.TestCase):
    """World 7 scripts edit CoreDNS, kindnet, metrics-server and the nodes of whatever cluster
    kubectl points at. Run by hand (no K8SQUEST_CONTEXT) on the main cluster they must refuse."""

    ROOT = Path(__file__).resolve().parent.parent / "worlds" / "world-7-troubleshooting"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.log = d / "calls.log"
        self.log.write_text("")
        (d / "kubectl").write_text('#!/bin/bash\necho "kubectl $*" >> "$STUB_LOG"\n'
                                   '[ "$1 $2" = "config current-context" ] && echo "$STUB_CONTEXT"\nexit 0\n')
        (d / "docker").write_text('#!/bin/bash\necho "docker $*" >> "$STUB_LOG"\nexit 0\n')
        for n in ("kubectl", "docker"):
            (d / n).chmod(0o755)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("K8SQUEST")}
        self.env.update(PATH=f"{d}{os.pathsep}{os.environ['PATH']}", STUB_LOG=str(self.log))

    def tearDown(self):
        self.tmp.cleanup()

    def run_setup(self, level, context):
        env = {**self.env, "STUB_CONTEXT": context}
        return subprocess.run(["bash", "setup.sh"], cwd=str(self.ROOT / level), env=env,
                              capture_output=True, text=True, timeout=60)

    def test_setup_refuses_on_the_main_cluster_and_touches_nothing(self):
        for level in ("level-61-kubelet-stopped", "level-66-coredns", "level-67-cni-node", "level-68-metrics-server"):
            self.log.write_text("")
            r = self.run_setup(level, "kind-k8squest")
            self.assertNotEqual(r.returncode, 0, level)
            self.assertIn("REFUSING", r.stderr, level)
            self.assertIn("kind-k8squest-multinode", r.stderr, level)
            calls = self.log.read_text().splitlines()
            self.assertFalse([c for c in calls if c.startswith("docker")], f"{level}: {calls}")
            self.assertEqual([c for c in calls if c.startswith("kubectl") and "current-context" not in c], [], level)

    def test_guard_accepts_the_multinode_context(self):
        # positive control: the refusal above is about the context, not a broken harness
        env = {**self.env, "STUB_CONTEXT": "kind-k8squest-multinode"}
        r = subprocess.run(["bash", "-c", '. _shared/lib.sh; require_game_context'], cwd=str(self.ROOT),
                           env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
