"""Question tasks (drill-page questions turned into cluster tasks): drill-only, admission, paths, texts, e2e arg logic."""
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tests._path  # noqa: F401
import levels
import pool
import selection
from tests.test_drill import make
from tests.test_exam import FakeCluster


class Admission(unittest.TestCase):
    def test_question_tasks_never_in_the_exam_pool_or_selection(self):
        qids = {t["id"] for t in pool.QUESTION_TASKS}
        self.assertTrue(qids)
        self.assertFalse(qids & {t["id"] for t in pool.POOL})
        self.assertFalse(qids & set(pool.BY_ID))
        self.assertFalse(qids & {t["id"] for t in pool.ALL_TASKS})
        # even when every task is offered as unproven, the exam pool is built from ALL_TASKS only
        picked = selection.select_session(pool.ALL_TASKS, set(), "all") if hasattr(selection, "select_session") else []
        self.assertFalse(qids & {t["id"] for t in picked})

    def test_drill_pool_admits_by_status(self):
        q = pool.QUESTION_TASKS
        self.assertEqual(pool.select_pool({"c01": {"verdict": "OK"}}, q), [pool.BY_ID_QUESTION["c01"]])
        self.assertEqual(pool.select_pool({t["id"]: {"verdict": "OK"} for t in q}, q), q)
        self.assertEqual(pool.select_pool({}, q), [])
        self.assertEqual(pool.select_pool({"c01": {"verdict": "SOLUTION-DOES-NOT-PASS"}}, q), [])

    def test_unproven_flag_admits_all_question_tasks(self):
        with mock.patch.dict(os.environ, {"EXAM_ALLOW_UNPROVEN": "1"}):
            dp = pool._drill_pool()
        self.assertTrue({t["id"] for t in pool.QUESTION_TASKS} <= {t["id"] for t in dp})

    def test_question_task_shape(self):
        t = pool.BY_ID_QUESTION["c01"]
        self.assertEqual((t["source"], t["qid"], t["level"], t["pattern"]), ("question", "services-1", "questions/services-1", "expose"))
        self.assertTrue(all(x["pattern"] is None for x in pool.ALL_TASKS))
        with self.assertRaises(AssertionError):
            pool.Q("c99", "x", pool.NET, "no-such-pattern", "text")
        self.assertEqual(pool.drill_title(t), "Expose Deployment `web` as a ClusterIP Service named `web-svc` on port 80.")


class Paths(unittest.TestCase):
    def test_resolution_and_traversal(self):
        self.assertEqual(levels.level_dir("questions/services-1"), (levels.QUESTIONS / "services-1").resolve())
        for bad in ("questions/../../etc", "questions/..", "questions/nope", "questions/../worlds"):
            with self.assertRaises(ValueError, msg=bad):
                levels.level_dir(bad)

    def test_materialize_rewrites_and_cleanup_leaves_nothing(self):
        p = levels.materialize("questions/services-1", "drill-c01")
        root = p.parents[1]
        try:
            self.assertTrue(root.is_dir())
            self.assertIn("namespace: drill-c01", (p / "broken.yaml").read_text())
            self.assertNotIn("k8squest", (p / "validate.sh").read_text())
            self.assertIn("-n drill-c01", (p / "solution.sh").read_text())
        finally:
            levels.cleanup(p)
        self.assertFalse(root.exists())
        self.assertIn("k8squest", (levels.QUESTIONS / "services-1" / "broken.yaml").read_text())

    def test_world_cleanup_still_removes_the_whole_tree(self):
        p = levels.materialize("world-1-basics/level-1-pods", "exam-t01")
        root = p.parents[2]
        levels.cleanup(p)
        self.assertFalse(root.exists())

    def test_level_texts_for_c01(self):
        t = pool.BY_ID_QUESTION["c01"]
        raw = levels.level_texts(t["level"], "drill-c01")
        self.assertTrue(all(raw["hints"]))
        self.assertIn("kubernetes.io/docs/reference/kubectl/quick-reference", raw["hints"][0])
        self.assertIn("kubectl expose", raw["hints"][1])
        self.assertIn("k expose <type> <name> --port=<port>", raw["hints"][2])
        self.assertEqual(raw["solution"], "kubectl -n drill-c01 expose deploy web --name=web-svc --port=80")
        self.assertTrue(raw["debrief"])

    def test_apply_solution_runs_solution_sh_in_the_materialized_dir(self):
        seen = []

        def fake_run(args, **kw):
            seen.append((list(args), kw.get("cwd")))
            return mock.Mock(returncode=0, stdout="ok", stderr="")
        with mock.patch.object(levels, "run", fake_run), mock.patch.object(levels, "kenv", return_value={}):
            ok, _ = levels.apply_solution("questions/services-1", "drill-c01")
        self.assertTrue(ok)
        self.assertEqual(seen[0][0], ["bash", "solution.sh"])
        self.assertTrue(seen[0][1].endswith("services-1"))
        self.assertEqual(len(seen), 1)       # no kubectl apply -f solution.yaml


class E2eArgs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        before = os.environ.get("EXAM_ALLOW_UNPROVEN")
        import e2e          # sets EXAM_ALLOW_UNPROVEN at import; do not leak it into the other tests
        cls.e2e = e2e
        if before is None:
            os.environ.pop("EXAM_ALLOW_UNPROVEN", None)
        else:
            os.environ["EXAM_ALLOW_UNPROVEN"] = before

    def test_write_status_refused_for_drill_exam_tasks(self):
        c = self.e2e.check_args
        self.assertIsNotNone(c("drill", True, {"t22", "t30"}, False))
        self.assertIsNotNone(c("drill", True, {"t22", "c01"}, False))     # mixed
        self.assertIsNotNone(c("drill", True, set(), False))              # whole pool
        self.assertIsNotNone(c("drill", True, {"c01"}, True))             # --level exploration

    def test_write_status_allowed_for_question_only_jobs(self):
        c = self.e2e.check_args
        self.assertIsNone(c("drill", True, {"c01"}, False))
        self.assertIsNone(c("drill", False, {"t22"}, False))
        self.assertIsNone(c("exam", True, {"t22"}, False))

    def test_question_tasks_refused_with_kind_exam(self):
        self.assertIn("drill-only", self.e2e.check_args("exam", False, {"c01"}, False))


class PatternsPayload(unittest.TestCase):
    def test_only_used_patterns_are_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            dp = [pool.BY_ID["t03"], pool.BY_ID_QUESTION["c01"]]
            with mock.patch.object(pool, "DRILL_POOL", dp), mock.patch.object(pool, "DRILL_BY_ID", {t["id"]: t for t in dp}):
                st = make(tmp, FakeCluster()).drill.state()
        self.assertEqual(st["patterns"], [{"id": "expose", "name": "k expose <type> <name> --port=<port>"}])
        by = {t["id"]: t for t in st["tasks"]}
        self.assertEqual((by["c01"]["pattern"], by["c01"]["source"]), ("expose", "question"))
        self.assertEqual((by["t03"]["pattern"], by["t03"]["source"]), (None, "exam"))


class ReviewFixes(unittest.TestCase):
    def test_non_question_level_with_both_files_still_applies_solution_yaml(self):
        rel = "world-2-deployments/level-20-replicaset"
        d = levels.level_dir(rel)
        self.assertTrue((d / "solution.sh").is_file() and (d / "solution.yaml").is_file())
        seen = []

        def fake_run(args, **kw):
            seen.append(list(args))
            return mock.Mock(returncode=0, stdout="ok", stderr="")
        with mock.patch.object(levels, "run", fake_run), mock.patch.object(levels, "kenv", return_value={}):
            ok, _ = levels.apply_solution(rel, "exam-t20")
        self.assertTrue(ok)
        self.assertNotIn(["bash", "solution.sh"], seen)
        self.assertTrue(any(a[:3] == ["kubectl", "apply", "-f"] and a[3].endswith("solution.yaml") for a in seen))

    def test_cleanup_refuses_a_tree_materialize_did_not_create(self):
        with tempfile.TemporaryDirectory() as tmp:
            foreign = Path(tmp) / "a" / "b" / "c"
            foreign.mkdir(parents=True)
            sibling = Path(tmp) / "keep.txt"
            sibling.write_text("x")
            for path in (foreign, Path(tmp) / "questions" / "q"):
                with self.assertRaises(ValueError):
                    levels.cleanup(path)
            self.assertTrue(sibling.is_file() and foreign.is_dir())

    def test_c01_never_enters_the_exam_even_when_its_status_is_ok(self):
        status = {t["id"]: {"verdict": "OK"} for t in pool.ALL_TASKS + pool.QUESTION_TASKS}
        self.assertNotIn("c01", {t["id"] for t in pool.select_pool(status)})
        with mock.patch.object(pool, "load_status", return_value=status), \
                mock.patch.dict(os.environ, {"EXAM_ALLOW_UNPROVEN": "0"}):
            built = pool._pool()
        self.assertNotIn("c01", {t["id"] for t in built})
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(pool, "POOL", built):
            ex = make(tmp, FakeCluster())
            ex.start("weighted")
            ids = {t["id"] for t in ex.session.tasks}
        self.assertTrue(ids)
        self.assertNotIn("c01", ids)

    def test_drill_c01_open_hint_check_reset(self):
        c01 = pool.BY_ID_QUESTION["c01"]
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(pool, "DRILL_POOL", [c01]), \
                mock.patch.object(pool, "DRILL_BY_ID", {"c01": c01}):
            cluster = FakeCluster()
            d = make(tmp, cluster).drill
            p = d.open("c01")
            self.assertEqual(cluster.deploys, ["drill-c01"])
            self.assertEqual(p["namespace"], "drill-c01")
            self.assertIn("drill-c01", p["text"]["body"])
            r = d.check("c01")
            self.assertEqual(r["verdict"], "failed")
            self.assertIsNone(r["output"])                    # withheld before Hint 3
            self.assertTrue(r["output_withheld"])
            d.hint("c01", 1)
            d.hint("c01", 2)
            self.assertIsNone(d.check("c01")["output"])
            p = d.hint("c01", 3)
            self.assertIn("Pattern: k expose", p["hints"][2])
            self.assertIsNotNone(d.check("c01")["output"])
            p = d.hint("c01", 4)
            self.assertIn("drill-c01", p["solution"])
            self.assertNotIn("k8squest", p["solution"])
            d.reset("c01")
            self.assertEqual(cluster.deploys, ["drill-c01", "drill-c01"])

    def test_status_key_is_the_task_id(self):
        import e2e
        self.assertEqual(e2e.status_key("c01", "drill-c01"), "c01")
        self.assertEqual(e2e.status_key("t22", "exam-t22"), "t22")
        self.assertEqual(e2e.status_key(None, "exam-t22"), "t22")

    def test_sweep_covers_question_task_cluster_objects(self):
        q = pool.Q("c98", "services-1", pool.NET, "expose", "x", cluster_objects=["pv/drill-c98-data"])
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(pool, "QUESTION_TASKS", [q]):
            cluster = FakeCluster()
            make(tmp, cluster)._remove_exam_namespaces()
        self.assertIn(["kubectl", "delete", "pv/drill-c98-data", "--ignore-not-found", "--wait=false"], cluster.calls)


NODE = "k8squest-control-plane"     # the kind node name is a literal, not the namespace token; only the node tasks may carry it


NODE_TASKS = {"c44", "c90", "c91", "c92", "c93", "c94", "c95", "c96", "c97"}   # exactly the tasks that name the node


def strip_node(task_id, text):
    return text.replace(NODE, "") if task_id in NODE_TASKS else text


class AllQuestionTasks(unittest.TestCase):
    FILES = ("broken.yaml", "validate.sh", "solution.sh", "hint-1.txt", "hint-2.txt", "hint-3.txt", "debrief.md")

    def test_every_question_task_has_its_files_and_a_valid_pattern(self):
        for t in pool.QUESTION_TASKS:
            d = levels.level_dir(t["level"])
            for f in self.FILES:
                if f == "broken.yaml" and t.get("cluster") == "kubeadm":
                    continue        # a kubeadm task has setup.sh instead
                self.assertTrue((d / f).is_file() and (d / f).read_text().strip(), f"{t['id']}: {f}")
            self.assertIn(t["pattern"], pool.PATTERN_IDS, t["id"])
            self.assertIn("Pattern: ", (d / "hint-3.txt").read_text())

    def test_ids_unique_and_contiguous(self):
        ids = [t["id"] for t in pool.QUESTION_TASKS]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids, ["c%02d" % i for i in range(1, len(ids) + 1)])
        self.assertEqual(len({t["qid"] for t in pool.QUESTION_TASKS}), len(ids))

    def test_namespaces_and_cluster_objects_are_deletable_and_prefixed(self):
        for t in pool.QUESTION_TASKS:
            ns = pool.namespace(t["id"], "drill")
            objs = pool.cluster_objects_for(t, "drill")
            levels._check_deletable(ns, objs)
            for name in pool.renames_for(t, "drill").values():
                self.assertTrue(name.startswith(f"drill-{t['id']}-"), (t["id"], name))
            for o in objs:
                self.assertTrue(o.split("/", 1)[1].startswith(f"drill-{t['id']}-"), o)
            # the sweep that exam start does covers the exam-prefixed names too
            levels._check_deletable(pool.namespace(t["id"], "exam"), pool.cluster_objects_for(t, "exam"))

    def test_rendered_text_has_no_leftover_dev_namespace_or_token(self):
        for t in pool.QUESTION_TASKS:
            body = pool.render_text(t, "h", "drill")["body"]
            self.assertNotIn("{ns}", body, t["id"])
            self.assertNotIn("k8squest", strip_node(t["id"], body), t["id"])
            self.assertNotIn("exam-c", body, t["id"])
            stripped = re.sub(r"\b(env|APP_ENV)=(dev|prod)\b", "", re.sub(r"drill-c\d+-[\w-]+", "", body))
            self.assertIsNone(re.search(r"\bdev\b|\bprod\b(?!-ns)", stripped), (t["id"], body))
            texts = levels.level_texts(t["level"], pool.namespace(t["id"], "drill"), pool.renames_for(t, "drill"))
            for raw in texts["hints"] + [texts["solution"], texts["debrief"]]:
                self.assertNotIn("k8squest", strip_node(t["id"], raw or ""), t["id"])
                self.assertNotRegex(raw or "", r"\b(devns|prodns)\b", t["id"])

    def test_materialized_files_use_the_task_namespace_and_renames(self):
        for t in pool.QUESTION_TASKS:
            p = levels.materialize(t["level"], pool.namespace(t["id"], "drill"), pool.renames_for(t, "drill"))
            try:
                for f in ("broken.yaml", "validate.sh", "solution.sh"):
                    if not (p / f).is_file():
                        self.assertEqual((t.get("cluster"), f), ("kubeadm", "broken.yaml"))
                        continue
                    txt = (p / f).read_text()
                    self.assertNotIn("k8squest", strip_node(t["id"], txt), (t["id"], f))
                    self.assertNotRegex(txt, r"\b(devns|prodns)\b", (t["id"], f))
            finally:
                levels.cleanup(p)

    RAW = ("broken.yaml", "validate.sh", "solution.sh", "hint-1.txt", "hint-2.txt", "hint-3.txt", "debrief.md")

    def test_every_rename_key_occurs_as_a_whole_token_in_a_raw_file(self):
        for t in pool.QUESTION_TASKS:
            d = levels.level_dir(t["level"])
            raw = "\n".join((d / f).read_text() for f in self.RAW if (d / f).is_file())
            for old in t.get("renames", {}):
                self.assertRegex(raw, r"(?<![\w-])" + re.escape(old) + r"(?![\w-])", (t["id"], old))

    def test_created_namespaces_and_cluster_roles_are_in_cluster_objects(self):
        pat = re.compile(r"kind:\s*(Namespace|ClusterRole|ClusterRoleBinding|PersistentVolume|StorageClass)\b[\s\S]*?\n\s*name:\s*(\S+)"
                         r"|create\s+(ns|namespace|clusterrole|clusterrolebinding)\s+(\S+)")
        kinds = {"ns": "namespace", "namespace": "namespace", "clusterrole": "clusterrole", "clusterrolebinding": "clusterrolebinding",
                 "persistentvolume": "pv", "storageclass": "storageclass"}
        for t in pool.QUESTION_TASKS:
            d = levels.level_dir(t["level"])
            ren = pool.renames_for(t, "drill")
            have = {o.lower() for o in pool.cluster_objects_for(t, "drill")}
            for f in ("broken.yaml", "solution.sh"):
                if not (d / f).is_file():
                    continue
                for m in pat.finditer((d / f).read_text()):
                    kind = (m.group(1) or m.group(3)).lower()
                    name = m.group(2) or m.group(4)
                    kind = kinds.get(kind, kind)
                    name = ren.get(name, name)
                    self.assertIn(f"{kind}/{name}".lower(), have, (t["id"], f, kind, name))

    def test_hint_3_is_the_pattern_name(self):
        names = {p["id"]: p["name"] for p in pool.PATTERNS}
        for t in pool.QUESTION_TASKS:
            h = (levels.level_dir(t["level"]) / "hint-3.txt").read_text().strip()
            self.assertEqual(h, "Pattern: " + names[t["pattern"]], t["id"])

    def test_every_shell_script_parses(self):
        import tests._path as guard
        for f in sorted(levels.QUESTIONS.glob("*/*.sh")):
            with mock.patch.object(subprocess, "Popen", guard.REAL_POPEN):     # `bash -n` parses only, never executes
                r = guard.REAL_RUN(["bash", "-n", str(f)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f"{f}: {r.stderr}")
        self.assertTrue(list(levels.QUESTIONS.glob("*/setup.sh")))

    RM = "rm -rf /opt/course/k8squest"
    OWN = '[ "$(stat -c %U /opt/course/k8squest)" = "$(id -un)" ] || { echo "answer dir not owned by $(id -un)"; exit 1; }'

    def test_answer_file_tasks_reset_their_own_directory_first(self):
        seen = 0
        for t in pool.QUESTION_TASKS:
            d = levels.level_dir(t["level"])
            texts = {f.name: f.read_text() for f in d.iterdir() if f.is_file()}
            for name, txt in texts.items():
                if t.get("cluster") == "kubeadm":      # the only sudo allowed is the helper (or running as cka1), never a bare one
                    self.assertEqual(txt.count("sudo"), txt.count("sudo -n /usr/local/sbin/cka-kubeadm ") + txt.count("sudo -n -H -u cka1 "),
                                     (t["id"], name))
                    continue
                self.assertNotIn("sudo", txt, (t["id"], name))
            if t.get("cluster") == "kubeadm" or not any("/opt/course" in x for x in texts.values()):
                continue        # kubeadm answer files have their own test (KubeadmQuestionTasks)
            seen += 1
            self.assertIn("setup.sh", texts, t["id"])
            body = [l.strip() for l in texts["setup.sh"].splitlines() if l.strip() and not l.strip().startswith("#")]
            body = [l for l in body if l != "set -e" and not l.startswith("NS=")]
            self.assertEqual(body[0], self.RM, t["id"])
            self.assertRegex(body[1], r"^mkdir -m (1777|0700) /opt/course/k8squest$", t["id"])
            self.assertEqual(body[2], self.OWN, t["id"])
            self.assertEqual(texts["setup.sh"].count("rm -rf"), 1, t["id"])
            for name, txt in texts.items():
                for path in re.findall(r"/opt/course/[\w./-]+", txt):
                    self.assertTrue(re.fullmatch(r"/opt/course/k8squest(/[\w.-]+)?", path), (t["id"], name, path))
        self.assertGreaterEqual(seen, 30)

    def test_validators_read_the_answer_without_following_symlinks(self):
        for t in pool.QUESTION_TASKS:
            v = (levels.level_dir(t["level"]) / "validate.sh").read_text()
            if t.get("cluster") == "kubeadm":
                continue        # a kubeadm validator tests `[ ! -L file ]` on the node (KubeadmQuestionTasks)
            if "/opt/course" in v:
                self.assertIn("os.O_NOFOLLOW", v, t["id"])
                self.assertIn("S_ISREG", v, t["id"])

    def test_embedded_validator_python_compiles(self):
        n = 0
        for t in pool.QUESTION_TASKS:
            v = (levels.level_dir(t["level"]) / "validate.sh").read_text()
            if "<<'PY'" not in v:
                continue
            src = v.split("<<'PY'\n", 1)[1].rsplit("\nPY\n", 1)[0]
            compile(src, t["id"] + "/validate.sh", "exec")       # compile only, never executed
            n += 1
        self.assertGreaterEqual(n, 30)

    def test_materialized_answer_task_resets_only_its_own_namespace_directory(self):
        t = pool.BY_ID_QUESTION["c60"]
        p = levels.materialize(t["level"], "drill-c60", pool.renames_for(t, "drill"))
        try:
            s = (p / "setup.sh").read_text()
            self.assertNotIn("k8squest", s)
            self.assertEqual(re.findall(r"rm -rf (\S+)", s), ["/opt/course/drill-c60"])
            self.assertEqual(re.findall(r"mkdir -m \S+ (\S+)", s), ["/opt/course/drill-c60"])
        finally:
            levels.cleanup(p)

    def test_answer_paths_in_task_text_match_the_files(self):
        for t in pool.QUESTION_TASKS:
            d = levels.level_dir(t["level"])
            if t.get("cluster") == "kubeadm" or "/opt/course" not in (d / "validate.sh").read_text():
                continue
            for path in re.findall(r"/opt/course/\{ns\}/[\w.-]+", t["text"]):
                self.assertIn(path.replace("{ns}", "k8squest"), (d / "validate.sh").read_text() + (d / "setup.sh").read_text(), (t["id"], path))

    def test_c05_node_port_is_used_by_no_level(self):
        self.assertIn("30777", pool.BY_ID_QUESTION["c05"]["text"])
        for f in levels.WORLDS.rglob("*"):
            if f.is_file() and f.suffix in (".yaml", ".yml", ".sh", ".md", ".txt"):
                self.assertNotIn("30777", f.read_text(errors="replace"), str(f))


class KubeadmQuestionTasks(unittest.TestCase):
    """Structure of every kubeadm task directory (c100 to c115). Behaviour is proven live by e2e.py, not here."""
    LOCK_WAIT = 60          # cka-kubeadm run-on waits at most this long for its root lock (hosts/cka-kubeadm RUN_ON_LOCK_WAIT)
    HELPER_RE = re.compile(r"sudo -n /usr/local/sbin/cka-kubeadm run-on --timeout (\d+) (controlplane|node01)\b")

    def tasks(self):
        ts = [t for t in pool.QUESTION_TASKS if t.get("cluster") == "kubeadm"]
        self.assertEqual([t["id"] for t in ts], ["c%d" % i for i in range(100, 116)])
        return ts

    def test_every_task_has_the_files_a_kubeadm_task_needs(self):
        for t in self.tasks():
            d = levels.level_dir(t["level"])
            self.assertFalse((d / "broken.yaml").exists(), t["id"])
            for f in ("validate.sh", "solution.sh", "hint-1.txt", "hint-2.txt", "hint-3.txt", "debrief.md"):
                self.assertTrue((d / f).is_file() and (d / f).read_text().strip(), (t["id"], f))
            extra = {f.name for f in d.iterdir()} - {"validate.sh", "solution.sh", "setup.sh", "hint-1.txt", "hint-2.txt", "hint-3.txt", "debrief.md",
                                                     "setup-node01.sh", "setup-cka1.sh", "solution-node01.sh", "solution-cka1.sh"}
            self.assertEqual(extra, set(), t["id"])
            self.assertTrue((d / "hint-1.txt").read_text().startswith("Docs: "), t["id"])
            self.assertTrue((d / "hint-2.txt").read_text().startswith("Search the page for: "), t["id"])
        # task text: every node or host it sends the candidate to
        for tid in ("c101", "c102", "c103", "c104", "c105", "c106", "c107", "c108", "c110", "c114"):
            self.assertIn("ssh controlplane", pool.BY_ID_QUESTION[tid]["text"], tid)
        for tid in ("c111", "c113"):
            self.assertIn("ssh node01", pool.BY_ID_QUESTION[tid]["text"], tid)
        self.assertIn("cka1", pool.BY_ID_QUESTION["c115"]["text"])

    def test_node_and_timeout_directives_parse_and_stay_in_range(self):
        for t in self.tasks():
            d = levels.level_dir(t["level"])
            for f in sorted(d.glob("s*.sh")):
                text = f.read_text()
                head = text.split("\n", 3)[:3]
                if "-node01" in f.name:
                    self.assertIn("# node: node01", head, f.name)
                if "-cka1" in f.name:
                    self.assertIn("# node: cka1", head, f.name)
                secs = levels.kubeadm_script_seconds(text)          # raises for a value outside 1..900
                self.assertLessEqual(secs, 900, (t["id"], f.name))
                # the server side waits longer than the helper can take: lock wait plus the run itself
                self.assertGreater(secs + levels.KUBEADM_SCRIPT_MARGIN, self.LOCK_WAIT + secs, (t["id"], f.name))
                if "upgrade apply" in text or "apt-get install" in text:
                    self.assertGreaterEqual(secs, 300, (t["id"], f.name, "apt and kubeadm need a long timeout"))
        self.assertEqual(levels.kubeadm_script_seconds("#!/bin/bash\ntrue\n"), levels.RUN_ON_SECONDS)
        with self.assertRaises(ValueError):
            levels.kubeadm_script_seconds("# timeout: 0\n")
        with self.assertRaises(ValueError):
            levels.kubeadm_script_seconds("# timeout: 901\n")

    def test_validators_go_through_the_helper_and_fit_the_server_timeout(self):
        for t in self.tasks():
            v = (levels.level_dir(t["level"]) / "validate.sh").read_text()
            calls = self.HELPER_RE.findall(v)
            if t["id"] == "c115":        # reads cka1's own files as cka1 plus one controlplane read
                self.assertIn("sudo -n -H -u cka1 env -u KUBECONFIG kubectl config current-context", v)
            self.assertTrue(calls, t["id"])
            self.assertEqual(len(calls), v.count("cka-kubeadm run-on"), t["id"])      # every call asks for an explicit --timeout
            # the helper waits up to 60 s for its lock before each call, then runs at most its --timeout
            self.assertLess(sum(self.LOCK_WAIT + int(n) for n, _ in calls), levels.KUBEADM_VALIDATE_TIMEOUT, t["id"])
            for n, _ in calls:
                self.assertLessEqual(int(n), 150, t["id"])
            # a failed check is exit 1; a check that cannot run says so
            self.assertIn("could not check", v, t["id"])
            self.assertEqual(len(re.findall(r"^exit 0$", v, re.M)), 1, t["id"])
            self.assertEqual(v.count("<<'EOS'"), v.count("run-on"), t["id"])         # the node script is quoted: nothing expands on k8s-lab

    def test_answer_file_tasks_use_one_directory_one_convention(self):
        seen = 0
        for t in self.tasks():
            d = levels.level_dir(t["level"])
            texts = {f.name: f.read_text() for f in d.iterdir() if f.is_file()}
            paths = set(re.findall(r"/opt/course/[\w./-]+", t["text"]))
            if t["id"] == "c115":
                self.assertEqual(paths, set(), "c115 is the exception: its answer is in cka1's home")
                self.assertIn("~/cluster1-confirm.txt", t["text"])
                self.assertIn("$F", texts["validate.sh"])
                self.assertIn("test -f \"$F\" -a ! -L \"$F\"", texts["validate.sh"])
                continue
            for name, txt in texts.items():
                for path in re.findall(r"/opt/course/[\w./-]+", txt):
                    self.assertTrue(re.fullmatch(r"/opt/course/kubeadm(/[\w.-]+)?", path), (t["id"], name, path))
            if not paths:
                continue
            seen += 1
            for path in paths:
                self.assertRegex(path, r"^/opt/course/kubeadm/[\w.-]+$", t["id"])
                self.assertIn(path, texts["validate.sh"], (t["id"], path))
            self.assertIn("[ -f \"$f\" ] && [ ! -L \"$f\" ]", texts["validate.sh"], t["id"])      # a regular file, never a symbolic link
            self.assertIn("-le ", texts["validate.sh"], t["id"])                                   # and a size limit
            body = [l.strip() for l in texts["setup.sh"].splitlines() if l.strip() and not l.strip().startswith("#")]
            body = [l for l in body if l != "set -e" and l != "set -eu"]
            self.assertEqual(texts["setup.sh"].count("rm -rf /opt/course/kubeadm\n"), 1, t["id"])
            i = body.index("rm -rf /opt/course/kubeadm")
            self.assertEqual(body[i + 1:i + 3], ["mkdir -p /opt/course", "mkdir -m 1777 /opt/course/kubeadm"], t["id"])    # the candidate is not root
        self.assertEqual(seen, 4)           # c101, c102, c103 and c107 are the answer-file tasks

    def test_scripts_parse_and_every_setup_is_stand_alone(self):
        import tests._path as guard
        for t in self.tasks():
            d = levels.level_dir(t["level"])
            for f in sorted(d.glob("*.sh")):
                with mock.patch.object(subprocess, "Popen", guard.REAL_POPEN):
                    r = guard.REAL_RUN(["bash", "-n", str(f)], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, "%s: %s" % (f, r.stderr))
                txt = f.read_text()
                self.assertTrue(txt.startswith("#!/bin/bash\n"), f)
                if f.name != "validate.sh":      # run-on feeds one file: no sourcing, no copies of other files
                    self.assertNotIn("source ", txt, f)
                    self.assertNotRegex(txt, r"(^|\s)\. /", f)
                self.assertNotRegex(txt, r"1\.37\.\d", (f, "a patch release is read from the repository, never written down"))
        # a task that depends on an earlier step starts the cluster at that step by itself
        for tid in ("c108", "c109", "c110", "c111"):
            txt = (levels.level_dir(pool.BY_ID_QUESTION[tid]["level"]) / "setup.sh").read_text()
            self.assertIn("apt-get install", txt, tid)
        for tid, needs in (("c109", ["upgrade apply"]), ("c110", ["upgrade apply", "drain controlplane"]),
                           ("c111", ["upgrade apply", "drain controlplane", "kubelet=", "uncordon controlplane", "cordon node01"])):
            txt = (levels.level_dir(pool.BY_ID_QUESTION[tid]["level"]) / "setup.sh").read_text()
            for n in needs:
                self.assertIn(n, txt, (tid, n))
        self.assertIn("kubeadm=", (levels.level_dir("questions/upgrade-6") / "setup-node01.sh").read_text())

    def test_the_shown_solution_has_no_runner_directives(self):
        for t in self.tasks():
            raw = (levels.level_dir(t["level"]) / "solution.sh").read_text()
            shown = levels.level_texts(t["level"], "kubeadm")["solution"]
            self.assertNotRegex(shown, r"(?m)^#\s*(timeout|node):", t["id"])
            self.assertEqual(len(shown.splitlines()), len([l for l in raw.splitlines() if not re.fullmatch(r"#\s*(timeout|node):.*", l.strip())]), t["id"])
        self.assertIn("# timeout: 900", (levels.level_dir("questions/upgrade-3") / "solution.sh").read_text())      # the file keeps it
        self.assertNotIn("timeout", levels.level_texts("questions/upgrade-3", "kubeadm")["solution"].split("\n")[1])

    def test_the_text_never_hardcodes_a_patch_release(self):
        for t in self.tasks():
            self.assertNotRegex(pool.render_text(t, "h", "drill")["body"], r"1\.37\.\d", t["id"])
            texts = levels.level_texts(t["level"], "kubeadm")
            for raw in texts["hints"] + [texts["solution"], texts["debrief"]]:
                self.assertNotRegex(raw or "", r"1\.37\.\d", t["id"])


if __name__ == "__main__":
    unittest.main()
