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
if a[:1] == ["--context"]:
    a = a[2:]     # logged with it, matched without it
if a[:2] == ["config", "current-context"]:
    print(os.environ.get("STUB_CONTEXT", "kind-k8squest")); sys.exit(0)
if a[:2] == ["config", "get-contexts"]:
    print(os.environ.get("STUB_CONTEXTS", "")); sys.exit(0)
if a[0] == "get" and "--raw" in a and os.environ.get("STUB_API_DOWN"):
    sys.stderr.write("connection refused"); sys.exit(1)
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

LIMA_STUB = r'''#!/usr/bin/env python3
import os, sys
a = sys.argv[1:]
open(os.environ["STUB_LOG"], "a").write("LIMA " + " ".join(a) + "\n")
if a[:1] == ["--version"]:
    print("limactl version " + os.environ.get("STUB_LIMA_VERSION", "2.2.1")); sys.exit(0)
if a[:1] == ["list"]:
    rows = [l.split() for l in os.environ.get("STUB_LIMA_LIST", "").splitlines() if l.strip()]
    if "--json" in a:
        import json
        for r in rows:   # "<name> <Status> [foreign]": a machine without the game's marker param is "foreign"
            param = {} if r[2:3] == ["foreign"] else {"k8squest_world": "8"}
            print(json.dumps({"name": r[0], "status": r[1], "config": {"param": param}}))
    else:
        print("\n".join(" ".join(r[:2]) for r in rows))
    sys.exit(0)
if a[:1] in (["create"], ["start"]) and os.environ.get("STUB_LIMA_FAIL"):
    sys.stderr.write(os.environ["STUB_LIMA_FAIL"]); sys.exit(1)
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
        (d / "limactl").write_text(LIMA_STUB)
        (d / "limactl").chmod((d / "limactl").stat().st_mode | stat.S_IXUSR)
        for q in ("qemu-system-x86_64", "qemu-system-aarch64"):   # the Linux preflight looks for QEMU
            (d / q).write_text("#!/bin/sh\nexit 0\n")
            (d / q).chmod(0o755)
        self.bin = d
        self.log = d / "calls.log"
        self.log.write_text("")
        self.env = {"PATH": f"{d}{os.pathsep}{os.environ['PATH']}", "STUB_LOG": str(self.log),
                    "STUB_OBJECTS": json.dumps(OBJECTS), "STUB_CONTEXT": "kind-k8squest"}
        self._saved = {k: os.environ.get(k) for k in list(self.env) + ["K8SQUEST_ALLOW_CONTEXT", "K8S_CLUSTER_TYPE", "STUB_FAIL", "STUB_KIND_CLUSTERS", "STUB_KIND_FAIL", "STUB_DOCKER_RUNNING",
                                                                "STUB_API_DOWN", "STUB_CONTEXTS", "STUB_LIMA_VERSION", "STUB_LIMA_LIST", "STUB_LIMA_FAIL"]}
        os.environ.update(self.env)
        self._saved_limit_file = level_reset.INOTIFY_LIMIT_FILE
        level_reset.INOTIFY_LIMIT_FILE = str(d / "no-such-inotify-file")   # tests never read the host's limit
        for k in ("K8SQUEST_ALLOW_CONTEXT", "K8S_CLUSTER_TYPE", "STUB_FAIL", "STUB_KIND_CLUSTERS", "STUB_KIND_FAIL", "STUB_DOCKER_RUNNING",
                  "STUB_API_DOWN", "STUB_CONTEXTS", "STUB_LIMA_VERSION", "STUB_LIMA_LIST", "STUB_LIMA_FAIL"):
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
                if l and not l.startswith(("KIND ", "DOCKER ", "LIMA "))]

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
        self.assertEqual(level_reset.context_for("lima"), "k8squest-lima")
        with self.assertRaises(ValueError):
            level_reset.context_for("no-such-cluster")

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

    # ---- World 8: the Lima machines

    def lima_calls(self):
        return [l[5:] for l in self.log.read_text().splitlines() if l.startswith("LIMA ")]

    def kvm_and_mem(self, kvm=True, mem_kib=16 * 1024 * 1024):
        d = Path(self.tmp.name)
        kvm_path = d / "kvm"
        if kvm:
            kvm_path.write_text("")
        mem = d / "meminfo"
        mem.write_text(f"MemTotal:       {mem_kib} kB\nMemFree:        1 kB\n")
        return str(kvm_path), str(mem)

    def test_world_8_declares_lima_and_gets_the_lima_context(self):
        w8 = next((ENGINE.parent / "worlds").glob("world-8-*")) / "level-71-node-prep"
        self.assertEqual(level_reset.world_cluster(w8), "lima")
        self.assertEqual(level_reset.level_env(w8)["K8SQUEST_CONTEXT"], "k8squest-lima")

    def test_lima_context_is_a_game_cluster(self):
        os.environ["STUB_CONTEXT"] = "k8squest-lima"
        self.assertTrue(level_reset.on_game_cluster())

    def test_preflight_passes_on_a_capable_linux_host(self):
        kvm, mem = self.kvm_and_mem()
        self.assertIsNone(level_reset.lima_preflight("Linux", kvm, mem, "x86_64"))

    def test_preflight_names_a_missing_limactl(self):
        empty = Path(self.tmp.name) / "empty-bin"
        empty.mkdir()
        os.environ["PATH"] = str(empty)
        try:
            msg = level_reset.lima_preflight("Darwin")
        finally:
            os.environ["PATH"] = self.env["PATH"]
        self.assertIn("limactl not found", msg)
        self.assertIn("lima-vm.io", msg)

    def test_preflight_rejects_an_old_lima(self):
        os.environ["STUB_LIMA_VERSION"] = "1.2.1"
        self.assertIn("older than 2.0.0", level_reset.lima_preflight("Darwin"))

    def test_preflight_on_macos_needs_no_kvm(self):
        self.assertIsNone(level_reset.lima_preflight("Darwin", "/no/such/kvm", "/no/such/meminfo"))

    def test_preflight_says_when_kvm_is_missing(self):
        kvm, mem = self.kvm_and_mem(kvm=False)
        msg = level_reset.lima_preflight("Linux", kvm, mem, "x86_64")
        self.assertIn("does not exist", msg)
        self.assertIn("virtualization", msg)

    def test_preflight_says_when_kvm_is_not_usable_by_this_user(self):
        kvm, mem = self.kvm_and_mem()
        Path(kvm).chmod(0)
        try:
            if os.access(kvm, os.R_OK | os.W_OK):   # running as root: permissions do not apply
                self.skipTest("root can open anything")
            msg = level_reset.lima_preflight("Linux", kvm, mem, "x86_64")
        finally:
            Path(kvm).chmod(0o644)
        self.assertIn("kvm group", msg)

    def test_preflight_says_when_qemu_is_missing(self):
        kvm, mem = self.kvm_and_mem()
        only_lima = Path(self.tmp.name) / "only-lima"
        only_lima.mkdir()
        (only_lima / "limactl").write_text(LIMA_STUB.replace("#!/usr/bin/env python3", f"#!{sys.executable}", 1))
        (only_lima / "limactl").chmod(0o755)
        os.environ["PATH"] = str(only_lima)
        try:
            msg = level_reset.lima_preflight("Linux", kvm, mem, "x86_64")
        finally:
            os.environ["PATH"] = self.env["PATH"]
        self.assertIn("qemu-system-x86_64 not found", msg)

    def test_preflight_says_when_ram_is_short(self):
        kvm, mem = self.kvm_and_mem(mem_kib=4 * 1024 * 1024)
        msg = level_reset.lima_preflight("Linux", kvm, mem, "x86_64")
        self.assertIn("4096 MiB of RAM", msg)
        self.assertIn("8 GiB", msg)

    def lima_world(self, **env):
        os.environ.update({"STUB_CONTEXT": "kind-k8squest", **env})
        # the preflight is a separate tested unit; here a host that passes it
        saved = level_reset.lima_preflight
        level_reset.lima_preflight = lambda *a, **k: None
        try:
            return level_reset.ensure_world_cluster("lima", ENGINE.parent, say=lambda m: None)
        finally:
            level_reset.lima_preflight = saved

    def test_lima_creates_and_starts_both_machines_from_node_yaml(self):
        self.assertEqual(self.lima_world(), (True, ""))
        calls = self.lima_calls()
        for name, cpus, mem in (("k8squest-cp", 2, "3"), ("k8squest-worker", 2, "2.5")):
            create = [c for c in calls if c.startswith("create") and f"--name={name} " in c + " "]
            self.assertEqual(len(create), 1, calls)
            self.assertIn(f"--cpus={cpus}", create[0])
            self.assertIn(f"--memory={mem}", create[0])
            self.assertTrue(create[0].endswith("lima/node.yaml"), create[0])
            self.assertIn(f"start {name}", calls)

    def test_lima_leaves_running_machines_alone(self):
        self.lima_world(STUB_LIMA_LIST="k8squest-cp Running\nk8squest-worker Running", STUB_CONTEXTS="k8squest-lima")
        self.assertFalse([c for c in self.lima_calls() if c.startswith(("create", "start"))])

    def test_lima_starts_a_stopped_machine_without_creating_it(self):
        self.lima_world(STUB_LIMA_LIST="k8squest-cp Running\nk8squest-worker Stopped")
        calls = self.lima_calls()
        self.assertIn("start k8squest-worker", calls)
        self.assertFalse([c for c in calls if c.startswith("create")])
        self.assertNotIn("start k8squest-cp", calls)

    def test_lima_broken_machine_says_how_to_delete_it(self):
        ok, why = self.lima_world(STUB_LIMA_LIST="k8squest-cp Broken\nk8squest-worker Running")
        self.assertFalse(ok)
        self.assertIn("limactl delete -f k8squest-cp", why)
        self.assertFalse([c for c in self.lima_calls() if c.startswith(("create", "start"))])

    def test_lima_failed_create_is_reported(self):
        ok, why = self.lima_world(STUB_LIMA_FAIL="qemu exploded")
        self.assertFalse(ok)
        self.assertIn("qemu exploded", why)
        self.assertFalse([c for c in self.calls() if c[:2] == ["config", "use-context"]])

    def test_lima_creates_a_placeholder_context_and_switches_to_it(self):
        self.assertEqual(self.lima_world(STUB_LIMA_LIST="k8squest-cp Running\nk8squest-worker Running"), (True, ""))
        calls = self.calls()
        self.assertTrue([c for c in calls if c[:3] == ["config", "set-cluster", "k8squest-lima"]
                         and "--server=https://127.0.0.1:16443" in c and "--tls-server-name=kubernetes" in c], calls)
        self.assertIn(["config", "set-context", "k8squest-lima", "--cluster=k8squest-lima"], calls)
        self.assertIn(["config", "use-context", "k8squest-lima"], calls)

    def test_lima_does_not_overwrite_an_existing_context(self):
        self.lima_world(STUB_LIMA_LIST="k8squest-cp Running\nk8squest-worker Running", STUB_CONTEXTS="kind-k8squest\nk8squest-lima")
        self.assertFalse([c for c in self.calls() if c[:2] in (["config", "set-cluster"], ["config", "set-context"])])

    def test_lima_preflight_failure_stops_before_any_machine_is_touched(self):
        os.environ["STUB_LIMA_VERSION"] = "1.0.0"
        ok, why = level_reset.ensure_world_cluster("lima", ENGINE.parent, say=lambda m: None)
        self.assertFalse(ok)
        self.assertIn("older than 2.0.0", why)
        self.assertEqual(self.lima_calls(), ["--version"])

    def test_lima_refuses_a_same_named_machine_the_game_did_not_create(self):
        ok, why = self.lima_world(STUB_LIMA_LIST="k8squest-cp Running foreign\nk8squest-worker Running")
        self.assertFalse(ok)
        self.assertIn("did not create it", why)
        self.assertIn("limactl delete -f k8squest-cp", why)
        self.assertIn("limactl clone k8squest-cp <new-name>", why)
        self.assertFalse([c for c in self.lima_calls() if c.startswith(("create", "start"))])
        self.assertFalse([c for c in self.calls() if c[:2] == ["config", "use-context"]])

    def test_lima_node_yaml_carries_the_marker_the_engine_looks_for(self):
        text = (ENGINE.parent / "lima" / "node.yaml").read_text()
        self.assertIn(f'{level_reset.LIMA_MARKER_KEY}: "{level_reset.LIMA_MARKER_VALUE}"', text)

    def test_harness_deletes_only_the_machines_it_created(self):
        sys.path.insert(0, str(ENGINE.parent / "tests"))
        import level_harness
        os.environ.update(STUB_LIMA_LIST="k8squest-cp Running", STUB_CONTEXT="kind-k8squest")
        saved = level_reset.lima_preflight
        level_reset.lima_preflight = lambda *a, **k: None
        try:
            ok, why, created = level_harness.ensure_cluster("lima")
        finally:
            level_reset.lima_preflight = saved
        self.assertTrue(ok, why)
        self.assertEqual(created, ["k8squest-worker"])      # the user's own k8squest-cp is not ours
        level_harness.cleanup_created([("lima", n) for n in created])
        deletes = [c for c in self.lima_calls() if c.startswith("delete")]
        self.assertEqual(deletes, ["delete -f k8squest-worker"])

    def test_world_has_api(self):
        self.assertTrue(level_reset.world_has_api("kind"))
        self.assertTrue(level_reset.world_has_api("kind-multinode"))
        self.assertTrue(level_reset.world_has_api("lima"))          # the stub answers
        os.environ["STUB_API_DOWN"] = "1"
        self.assertFalse(level_reset.world_has_api("lima"))         # levels 71/72: no cluster yet
        self.assertTrue(level_reset.world_has_api("kind"))          # other worlds are never skipped

    def test_deploy_level_skips_the_namespace_work_when_the_lima_cluster_does_not_exist_yet(self):
        world = Path(self.tmp.name) / "worlds" / "world-x"
        level = world / "level-1-x"
        level.mkdir(parents=True)
        (world / "world.yaml").write_text('order: 8\ntitle: "T"\ndescription: "D"\ncluster: lima\nrequires: []\n')
        (level / "setup.sh").write_text("#!/bin/bash\nexit 0\n")
        os.environ.update(STUB_LIMA_LIST="k8squest-cp Running\nk8squest-worker Running", STUB_API_DOWN="1")
        saved = level_reset.lima_preflight
        level_reset.lima_preflight = lambda *a, **k: None
        try:
            ok, msg = level_reset.deploy_level(level)
        finally:
            level_reset.lima_preflight = saved
        self.assertTrue(ok, msg)
        verbs = [c[0] for c in self.calls()]
        self.assertNotIn("apply", [c[0] for c in self.calls() if c[:2] != ["config", "set-context"]] and
                         [v for v in verbs if v == "apply"])
        self.assertFalse([c for c in self.calls() if c[0] in ("delete", "apply")], self.calls())
        # positive control: with an API the same level gets the namespace apply and the delete
        self.log.write_text("")
        os.environ.pop("STUB_API_DOWN")
        level_reset.lima_preflight = lambda *a, **k: None
        try:
            level_reset.deploy_level(level)
        finally:
            level_reset.lima_preflight = saved
        self.assertTrue([c for c in self.calls() if c[0] == "apply"], self.calls())
        self.assertTrue([c for c in self.calls() if c[0] == "delete"], self.calls())

    def test_harness_clusters_and_lima_are_handled_in_one_place(self):
        sys.path.insert(0, str(ENGINE.parent / "tests"))
        import level_harness
        self.assertEqual(level_harness.context_for("lima"), level_reset.LIMA_CONTEXT)
        self.assertEqual(level_harness.LIMA, "lima")

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


class World8Guard(unittest.TestCase):
    """World 8 scripts reset and rebuild the two machines' Kubernetes cluster. Run on any other
    kubectl context they must refuse, and must not touch the machines first."""

    ROOT = Path(__file__).resolve().parent.parent / "worlds" / "world-8-cluster-lifecycle"
    LEVELS = ("level-71-node-prep", "level-72-kubeadm-init", "level-73-join-worker",
              "level-74-upgrade", "level-75-etcd-restore", "level-76-maintenance-drain")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.log = d / "calls.log"
        self.log.write_text("")
        (d / "kubectl").write_text('#!/bin/bash\necho "kubectl $*" >> "$STUB_LOG"\n'
                                   '[ "$1 $2" = "config current-context" ] && echo "$STUB_CONTEXT"\nexit 0\n')
        (d / "limactl").write_text('#!/bin/bash\necho "limactl $*" >> "$STUB_LOG"\nexit 0\n')
        for n in ("kubectl", "limactl"):
            (d / n).chmod(0o755)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("K8SQUEST")}
        self.env.update(PATH=f"{d}{os.pathsep}{os.environ['PATH']}", STUB_LOG=str(self.log))

    def tearDown(self):
        self.tmp.cleanup()

    def run_setup(self, level, context):
        return subprocess.run(["bash", "setup.sh"], cwd=str(self.ROOT / level),
                              env={**self.env, "STUB_CONTEXT": context}, capture_output=True, text=True, timeout=60)

    def test_setup_refuses_on_another_context_and_touches_no_machine(self):
        for level in self.LEVELS:
            self.log.write_text("")
            r = self.run_setup(level, "kind-k8squest")
            self.assertNotEqual(r.returncode, 0, level)
            self.assertIn("REFUSING", r.stderr, level)
            self.assertIn("k8squest-lima", r.stderr, level)
            calls = self.log.read_text().splitlines()
            self.assertEqual([c for c in calls if c.startswith("limactl")], [], f"{level}: {calls}")

    def test_guard_accepts_the_lima_context(self):
        # positive control: the refusal above is about the context, not a broken harness
        r = subprocess.run(["bash", "-c", ". _shared/lib.sh; require_game_context"], cwd=str(self.ROOT),
                           env={**self.env, "STUB_CONTEXT": "k8squest-lima"}, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_a_script_run_by_hand_defaults_to_the_lima_context(self):
        r = subprocess.run(["bash", "-c", '. _shared/lib.sh; echo "$K8SQUEST_CONTEXT"'], cwd=str(self.ROOT),
                           env={**self.env, "STUB_CONTEXT": "k8squest-lima"}, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.stdout.strip(), "k8squest-lima")

    def test_every_script_parses(self):
        for script in sorted(self.ROOT.glob("level-*/*.sh")) + sorted((self.ROOT / "_shared").rglob("*.sh")):
            r = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f"{script.name}: {r.stderr}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
