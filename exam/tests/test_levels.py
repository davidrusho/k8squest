import re
import unittest
from pathlib import Path

import tests._path  # noqa: F401
import levels
import pool


class Rewrite(unittest.TestCase):
    def test_namespace_token_is_rewritten(self):
        t = "kubectl get pods -n k8squest\nnamespace: k8squest\nsvc.k8squest.svc.cluster.local\nNAMESPACE=\"k8squest\""
        out = levels.rewrite_text(t, "exam-t07")
        self.assertNotIn("k8squest", out)
        self.assertIn("-n exam-t07\n", out)
        self.assertIn("svc.exam-t07.svc.cluster.local", out)

    def test_shell_default_value_is_rewritten(self):
        self.assertEqual(levels.rewrite_text('NS="${NAMESPACE:-k8squest}"', "exam-t58"), 'NS="${NAMESPACE:-exam-t58}"')

    def test_longer_identifiers_are_left_alone(self):
        t = "k8squest-player kind-k8squest /tmp/k8squest-data k8squest_x $HOME/.k8squest/work"
        self.assertEqual(levels.rewrite_text(t, "exam-t07"), t)

    def test_renames_are_whole_names_only(self):
        t = "pv app-storage\nclaim app-storage-claim\nvolumeName: app-storage"
        out = levels.rewrite_text(t, "exam-t31", {"app-storage": "exam-t31-app-storage"})
        self.assertEqual(out, "pv exam-t31-app-storage\nclaim app-storage-claim\nvolumeName: exam-t31-app-storage")

    def test_renames_apply_inside_dns_names(self):
        out = levels.rewrite_text("http://api-service.backend-ns.svc", "exam-t27", {"backend-ns": "exam-t27-backend"})
        self.assertEqual(out, "http://api-service.exam-t27-backend.svc")

    def test_level_files_untouched_by_materialize(self):
        rel = "world-1-basics/level-1-pods"
        before = (levels.WORLDS / rel / "validate.sh").read_text()
        p = levels.materialize(rel, "exam-t01")
        try:
            self.assertIn("-n exam-t01", (p / "validate.sh").read_text())
        finally:
            levels.cleanup(p)
        self.assertEqual((levels.WORLDS / rel / "validate.sh").read_text(), before)
        self.assertIn("k8squest", before)

    def test_world_layout_is_kept_for_sourced_helpers(self):
        p = levels.materialize("world-6-cluster-architecture/level-58-serviceaccount-rbac", "exam-t58")
        try:
            self.assertTrue((p.parent / "_shared" / "lib.sh").is_file())
            self.assertTrue((p.parents[1] / "_shared" / "lib.sh").is_file())
        finally:
            levels.cleanup(p)


class PoolRewrite(unittest.TestCase):
    """For every pool task, no bare `k8squest` namespace token may survive in what gets deployed or validated."""

    def test_no_namespace_token_left(self):
        left = []
        for t in pool.ALL_TASKS:
            ns = pool.namespace(t["id"])
            p = levels.materialize(t["level"], ns, t["renames"])
            try:
                for f in p.rglob("*"):
                    if f.suffix in (".yaml", ".sh") and f.is_file():
                        for n, line in enumerate(f.read_text().splitlines(), 1):
                            if levels._NS_RE.search(line):
                                left.append(f"{t['id']} {f.name}:{n}: {line.strip()[:80]}")
            finally:
                levels.cleanup(p)
        self.assertEqual(left, [])

    def test_renamed_cluster_objects_carry_the_exam_prefix(self):
        for t in pool.ALL_TASKS:
            for new in t["renames"].values():
                self.assertIn("exam-", new, t["id"])
            for obj in t["cluster_objects"]:
                self.assertIn("exam-", obj, t["id"])

    def test_every_level_exists_with_a_validator(self):
        for t in pool.ALL_TASKS:
            d = levels.level_dir(t["level"])
            self.assertTrue((d / "validate.sh").is_file(), t["id"])
            self.assertTrue((d / "broken.yaml").is_file() or (d / "setup.sh").is_file(), t["id"])

    def test_task_wording_names_its_own_namespace_objects(self):
        for t in pool.ALL_TASKS:
            self.assertIn("{ns}", t["text"] + " {ns}")      # placeholder syntax is valid
            self.assertNotIn("k8squest", t["text"], t["id"])
        ids = [t["id"] for t in pool.ALL_TASKS]
        self.assertEqual(len(ids), len(set(ids)))
        for t in pool.ALL_TASKS:
            self.assertRegex(t["id"], r"^t\d\d$")


class Pinning(unittest.TestCase):
    def setUp(self):
        levels._cleanup_pinned()
        self.addCleanup(levels._cleanup_pinned)

    def test_every_kubectl_call_is_pinned_to_the_context(self):
        from unittest import mock
        seen = []

        def fake(args, **kw):
            seen.append(list(args))
            return mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch.object(levels, "pinned_kubeconfig", return_value="/pinned/config"), \
                mock.patch.object(levels.subprocess, "run", fake):
            levels.run(["kubectl", "get", "ns"])
        self.assertEqual(seen, [["kubectl", "--context", levels.KUBE_CONTEXT, "get", "ns"]])

    def test_scripts_get_a_kubeconfig_whose_current_context_is_pinned(self):
        from unittest import mock
        with mock.patch.object(levels, "pinned_kubeconfig", return_value="/pinned/config"):
            env = levels.kenv("exam-t01")
        self.assertEqual(env["KUBECONFIG"], "/pinned/config")
        self.assertEqual(env["K8SQUEST_CONTEXT"], levels.KUBE_CONTEXT)
        self.assertEqual(env["NAMESPACE"], "exam-t01")

    def test_destructive_delete_guard_validates_before_any_command(self):
        from unittest import mock
        with mock.patch.object(levels, "run") as run:
            for ns in ("default", "kube-system", "k8squest", "", None):
                with self.assertRaises(ValueError):
                    levels.delete_task_objects(ns)
            with self.assertRaises(ValueError):          # good namespace, bad object: nothing may run
                levels.delete_task_objects("exam-t01", cluster_objects=["pv/important-data"])
            with self.assertRaises(ValueError):
                levels.delete_task_objects("exam-t01", cluster_objects=["pv/exam-ok", "pv/shared-storage"])
            run.assert_not_called()
            levels.delete_task_objects("exam-t01", cluster_objects=["pv/exam-t31-app-storage"])
            self.assertEqual(run.call_count, 2)


class PinnedKubeconfig(unittest.TestCase):
    BODY = "apiVersion: v1\nusers:\n- user:\n    token: SECRET-TOKEN-XYZ\n"

    def setUp(self):
        levels._cleanup_pinned()
        self.addCleanup(levels._cleanup_pinned)

    def fake(self, rc=0, out=None, exc=None):
        from unittest import mock
        calls = []

        def run(args, **kw):
            calls.append(list(args))
            if exc:
                raise exc
            return mock.Mock(returncode=rc, stdout=self.BODY if out is None else out, stderr="")
        return run, calls

    def test_modes_cleanup_and_nothing_printed(self):
        import contextlib
        import io
        import os
        import stat
        from unittest import mock
        run, calls = self.fake()
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(levels.subprocess, "run", run), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            path = levels.pinned_kubeconfig()
            again = levels.pinned_kubeconfig()
        self.assertEqual(path, again)
        self.assertEqual(len(calls), 1)               # built once
        self.assertEqual(calls[0][-2:], ["--context", levels.KUBE_CONTEXT])
        self.assertIn("--minify", calls[0])
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(os.path.dirname(path)).st_mode), 0o700)
        self.assertEqual(open(path).read(), self.BODY)
        self.assertNotIn("SECRET-TOKEN-XYZ", out.getvalue() + err.getvalue())
        levels._cleanup_pinned()
        self.assertFalse(os.path.exists(path))
        self.assertFalse(os.path.exists(os.path.dirname(path)))

    def test_failure_raises_and_is_not_cached(self):
        from unittest import mock
        bad, _ = self.fake(rc=1, out="")
        with mock.patch.object(levels.subprocess, "run", bad):
            with self.assertRaises(RuntimeError) as cm:
                levels.pinned_kubeconfig()
        self.assertNotIn("SECRET", str(cm.exception))
        good, calls = self.fake()
        with mock.patch.object(levels.subprocess, "run", good):
            self.assertTrue(levels.pinned_kubeconfig())      # retried, not stuck on the failure
        self.assertEqual(len(calls), 1)

    def test_missing_kubectl_raises_a_clear_error(self):
        from unittest import mock
        run, _ = self.fake(exc=FileNotFoundError("kubectl"))
        with mock.patch.object(levels.subprocess, "run", run):
            with self.assertRaises(RuntimeError):
                levels.pinned_kubeconfig()

    def test_sigterm_and_sighup_exit_through_normal_cleanup(self):
        import signal
        saved = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGHUP)}
        levels._HANDLERS["installed"] = False
        try:
            levels.install_signal_cleanup()
            for s in saved:
                handler = signal.getsignal(s)
                self.assertTrue(callable(handler) and handler is not saved[s])
                with self.assertRaises(SystemExit):       # SystemExit runs atexit, which removes the file
                    handler(s, None)
        finally:
            for s, h in saved.items():
                signal.signal(s, h)
            levels._HANDLERS["installed"] = False


class NodeReset(unittest.TestCase):
    def runner(self, nodes="node/n1\n", fail=None, stderr=""):
        from types import SimpleNamespace
        calls = []

        def run(args, **kw):
            calls.append(list(args))
            rc = 1 if fail and fail in args else 0
            return SimpleNamespace(returncode=rc, stdout=nodes if args[1:3] == ["get", "nodes"] else "", stderr=stderr if rc else "")
        return run, calls

    def test_removes_the_exam_labels_and_taint_keys_and_uncordons(self):
        run, calls = self.runner()
        self.assertEqual(levels.reset_node_state(run), [])
        self.assertEqual(levels.NODE_LABEL_KEYS, ("accelerator", "gpu-type", "disk"))
        self.assertEqual(levels.NODE_TAINT_KEYS, ("dedicated",))
        self.assertIn(["kubectl", "label", "node/n1", "accelerator-", "gpu-type-", "disk-"], calls)
        self.assertIn(["kubectl", "taint", "nodes", "n1", "dedicated-"], calls)
        self.assertIn(["kubectl", "uncordon", "node/n1"], calls)
        # only the named taint key is ever removed; nothing is cordoned or tainted
        self.assertEqual([c for c in calls if "taint" in c], [["kubectl", "taint", "nodes", "n1", "dedicated-"]])
        self.assertFalse([c for c in calls if "cordon" in c and "uncordon" not in c])

    def test_a_missing_taint_is_not_a_warning_but_a_real_failure_is(self):
        run, _ = self.runner(fail="taint", stderr='error: taint "dedicated" not found')
        self.assertEqual(levels.reset_node_state(run), [])
        run, _ = self.runner(fail="taint", stderr="forbidden")
        w = levels.reset_node_state(run)
        self.assertEqual(len(w), 1)
        self.assertIn("taint dedicated", w[0])

    def test_failures_are_warnings_but_missing_labels_are_not(self):
        run, _ = self.runner(fail="label", stderr="boom")
        w = levels.reset_node_state(run)
        self.assertEqual(len(w), 1)
        self.assertIn("labels", w[0])
        run, _ = self.runner(fail="label", stderr='label "accelerator" not found.')
        self.assertEqual(levels.reset_node_state(run), [])
        run, _ = self.runner(fail="uncordon", stderr="nope")
        self.assertIn("uncordon", levels.reset_node_state(run)[0])
        run, _ = self.runner(fail="get", stderr="down")
        self.assertIn("could not list nodes", levels.reset_node_state(run)[0])


class ClusterScopedNames(unittest.TestCase):
    """No cluster-scoped object or extra namespace that broken.yaml or solution.yaml creates may keep a
    game-owned name after the rewrite."""
    KINDS = r"PersistentVolume|PriorityClass|StorageClass|ClusterRole|ClusterRoleBinding|CustomResourceDefinition|Namespace|RuntimeClass|IngressClass"

    def test_names_are_exam_prefixed(self):
        bad = []
        pat = re.compile(r"^kind:\s*(%s)\s*\n(?:(?!^---).*\n)*?\s*name:\s*(\S+)" % self.KINDS, re.M)
        for t in pool.ALL_TASKS:
            p = levels.materialize(t["level"], pool.namespace(t["id"]), t["renames"])
            try:
                for fn in ("broken.yaml", "solution.yaml", "setup.yaml"):
                    f = p / fn
                    if not f.is_file():
                        continue
                    for m in pat.finditer(f.read_text()):
                        if not m.group(2).startswith("exam-"):
                            bad.append(f"{t['id']} {fn}: {m.group(1)} {m.group(2)}")
            finally:
                levels.cleanup(p)
        self.assertEqual(bad, [])

    def test_task_wording_uses_no_unrenamed_old_name(self):
        for t in pool.ALL_TASKS:
            for old in t["renames"]:
                self.assertIsNone(levels._token_re(old).search(t["text"]), f"{t['id']} mentions {old}")


if __name__ == "__main__":
    unittest.main()
