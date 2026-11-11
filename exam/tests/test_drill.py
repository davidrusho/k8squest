"""Drill mode: state, hint ladder, titles, namespaces, persistence, and the exam lock. No real subprocess."""
import http.client
import json
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

import tests._path  # noqa: F401
import levels
import pool
import server
from drill import Conflict, Locked
from server import Exam
from store import DrillFile, Results, SessionFile
from tests.test_exam import Clock, FakeCluster


def make(tmp, cluster=None, clock=None):
    d = Path(tmp)
    return Exam(Results(d / "results.json"), SessionFile(d / "session.json"), now=clock or Clock(),
                cluster=cluster or FakeCluster(), do_reset=False)


class DrillCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cluster = FakeCluster()
        self.exam = make(self.tmp.name, self.cluster)
        self.drill = self.exam.drill
        self.tid = "t03"

    def tearDown(self):
        self.tmp.cleanup()

    # ---- state and titles
    def test_state_lists_every_pool_task_without_revealing_text(self):
        st = self.drill.state()
        self.assertFalse(st["exam_live"])
        self.assertEqual(len(st["tasks"]), len(pool.POOL))
        self.assertEqual([d["name"] for d in st["domains"]][0], "Troubleshooting")
        t = next(x for x in st["tasks"] if x["id"] == self.tid)
        self.assertEqual(t["title"], "Pod `web-app` does not start.")
        self.assertEqual((t["status"], t["hints_revealed"], t["attempts"]), ("not_tried", 0, 0))
        self.assertNotIn("hints", t)

    def test_titles_use_exam_text_only_and_never_a_namespace_placeholder(self):
        for t in pool.POOL:
            title = pool.drill_title(t)
            self.assertTrue(title, t["id"])
            self.assertNotIn("{ns}", title)
            self.assertNotIn("In namespace", title)
            self.assertNotIn("exam-" + t["id"] + "-", title)

    def test_title_never_contains_the_missions_name_or_description(self):
        import re
        for t in pool.POOL:
            m = (levels.level_dir(t["level"]) / "mission.yaml")
            if not m.is_file():
                continue
            name = re.search(r"^name:\s*(.+)$", m.read_text(), re.M)
            if name:
                self.assertNotIn(name.group(1).strip().strip("\"'").lower(), pool.drill_title(t).lower(), t["id"])

    # ---- namespaces
    def test_open_deploys_into_the_drill_namespace_with_drill_renames(self):
        seen = []
        self.cluster.deploy = lambda rel, ns, renames=None, cluster_objects=(): seen.append((ns, renames, list(cluster_objects))) or (True, "")
        p = self.drill.open("t31")
        self.assertEqual(seen[0][0], "drill-t31")
        self.assertEqual(seen[0][1], {"app-storage": "drill-t31-app-storage"})
        self.assertEqual(seen[0][2], ["pv/drill-t31-app-storage"])
        self.assertIn("drill-t31", p["text"]["body"])
        self.assertNotIn("exam-", p["text"]["body"])
        self.assertEqual(pool.namespace("t31"), "exam-t31")           # the exam is unchanged

    def test_open_deploys_once(self):
        self.drill.open(self.tid)
        self.drill.open(self.tid)
        self.assertEqual(self.cluster.deploys, ["drill-t03"])

    def test_hint_text_gets_the_drill_namespace(self):
        self.drill.open(self.tid)
        p = self.drill.hint(self.tid, 1)
        self.assertIn("-n drill-t03", p["hints"][0])
        self.assertNotIn("k8squest", p["hints"][0])

    def test_missing_level_files_are_handled(self):
        real = levels.level_texts
        levels.level_texts = lambda *a, **k: {"hints": [None, None, None], "solution": None, "debrief": None}
        try:
            self.drill.open(self.tid)
            for n in (1, 2, 3, 4):
                p = self.drill.hint(self.tid, n)
            self.assertEqual(len(p["hints"]), 3)
            self.assertTrue(all(h for h in p["hints"]))
            self.assertTrue(p["solution"] and p["debrief"])
        finally:
            levels.level_texts = real

    def test_level_texts_for_every_pool_task_have_no_namespace_token(self):
        for t in pool.POOL:
            raw = levels.level_texts(t["level"], pool.namespace(t["id"], "drill"), pool.renames_for(t, "drill"))
            for x in raw["hints"] + [raw["solution"], raw["debrief"]]:
                if x:
                    self.assertNotRegex(x, r"(?<![\w.-])k8squest(?![\w-])", t["id"])

    # ---- check and persistence
    def test_check_records_attempt_and_solved_and_persists(self):
        self.drill.open(self.tid)
        self.cluster.pass_next = False
        r = self.drill.check(self.tid)
        self.assertEqual((r["verdict"], r["message"], r["attempts"], r["solved"]), ("failed", "Not passed yet.", 1, False))
        self.assertIsNone(r["debrief"])
        self.drill.hint(self.tid, 1)
        self.cluster.pass_next = True
        r = self.drill.check(self.tid)
        self.assertEqual((r["verdict"], r["message"], r["attempts"], r["solved"]), ("passed", "Passed.", 2, True))
        self.assertTrue(r["debrief"])
        again = make(self.tmp.name, self.cluster)
        row = next(x for x in again.drill.state()["tasks"] if x["id"] == self.tid)
        self.assertTrue(row["solved"] and row["solved_at"] and row["attempts"] == 2)
        d = json.loads((Path(self.tmp.name) / "drill.json").read_text())["tasks"][self.tid]
        for k in ("opened", "attempts", "solved", "solved_at", "hints_revealed", "last_output"):
            self.assertIn(k, d)

    def test_check_before_open_is_refused(self):
        with self.assertRaises(ValueError):
            self.drill.check(self.tid)

    def test_drill_never_touches_results_or_session_files(self):
        self.drill.open(self.tid)
        self.cluster.pass_next = True
        self.drill.check(self.tid)
        self.assertFalse((Path(self.tmp.name) / "results.json").exists())
        self.assertFalse((Path(self.tmp.name) / "session.json").exists())
        self.assertEqual(self.exam.results.counted_ids(), set())

    def test_solved_drill_does_not_count_as_an_exam_pass(self):
        self.drill.open(self.tid)
        self.cluster.pass_next = True
        self.drill.check(self.tid)
        self.assertEqual(self.exam.results.counted_ids(), set())
        self.exam.start("missed")           # "missed first" is built from results only: all tasks still count as missed
        self.assertEqual(len(self.exam.session.tasks), 16)
        self.assertEqual(self.exam.results.counted_ids(), set())

    def test_failed_in_exam_filter_flag(self):
        self.exam.results.record(self.tid, "s1", 500.0, True, False, "2026-01-01T00:00:00Z")   # passed over time
        self.exam.results.record("t04", "s1", 100.0, True, True, "2026-01-01T00:00:00Z")      # counted
        self.exam.results.record("t05", "s1", 100.0, False, False, "2026-01-01T00:00:00Z")
        by = {t["id"]: t for t in self.drill.state()["tasks"]}
        self.assertTrue(by[self.tid]["failed_in_exam"] and by["t05"]["failed_in_exam"])
        self.assertFalse(by["t04"]["failed_in_exam"])
        self.assertFalse(by["t01"]["failed_in_exam"])
        self.assertEqual(by["t05"]["status_label"], "failed in exam")

    # ---- hint ladder
    def test_hints_in_order_and_409_when_skipping(self):
        self.drill.open(self.tid)
        with self.assertRaises(Conflict):
            self.drill.hint(self.tid, 2)
        p = self.drill.hint(self.tid, 1)
        self.assertEqual((len(p["hints"]), p["hints_revealed"], p["solution"]), (1, 1, None))
        with self.assertRaises(Conflict):
            self.drill.hint(self.tid, 3)
        self.drill.hint(self.tid, 2)
        p = self.drill.hint(self.tid, 3)
        self.assertEqual(len(p["hints"]), 3)
        self.assertIsNone(p["solution"])          # not before n == 4
        self.assertIsNone(p["debrief"])
        with self.assertRaises(Conflict):
            self.drill.hint("t04", 4)
        p = self.drill.hint(self.tid, 4)
        self.assertEqual(len(p["hints"]), 3)
        self.assertTrue(p["solution"])
        self.assertTrue(p["debrief"])

    def test_hint_is_idempotent_and_validates_n(self):
        self.drill.open(self.tid)
        self.drill.hint(self.tid, 1)
        self.assertEqual(self.drill.hint(self.tid, 1)["hints_revealed"], 1)
        for bad in (0, 5, "1", None, True, 1.5):
            with self.assertRaises(ValueError, msg=repr(bad)):
                self.drill.hint(self.tid, bad)

    def test_unknown_task_is_keyerror(self):
        with self.assertRaises(KeyError):
            self.drill.open("t99")

    def test_solution_carries_the_manual_step_for_t20(self):
        self.drill.open("t20")
        for n in (1, 2, 3, 4):
            p = self.drill.hint("t20", n)
        self.assertIn("kubectl delete rs web-app-rs -n drill-t20", p["solution"])

    # ---- reset
    def test_reset_redeploys_and_keeps_attempts_solved_hints(self):
        self.drill.open(self.tid)
        self.cluster.pass_next = True
        self.drill.check(self.tid)
        self.drill.hint(self.tid, 1)
        p = self.drill.reset(self.tid)
        self.assertEqual(self.cluster.deploys, ["drill-t03", "drill-t03"])
        self.assertEqual((p["attempts"], p["solved"], p["hints_revealed"]), (1, True, 1))

    def test_reset_deletes_only_drill_prefixed_objects(self):
        with self.assertRaises(ValueError):
            levels._check_deletable("drill-t31", ["pv/exam-t31-app-storage"])
        with self.assertRaises(ValueError):
            levels._check_deletable("default", [])
        levels._check_deletable("drill-t31", ["pv/drill-t31-app-storage"])

    # ---- exam start sweep
    def test_exam_start_sweeps_drill_namespaces_and_forgets_deployed(self):
        self.drill.open("t31")
        self.cluster.calls.clear()
        self.cluster.run = lambda args, **kw: (self.cluster.calls.append(args) or __import__("types").SimpleNamespace(
            returncode=0, stdout="namespace/drill-t31\nnamespace/exam-t01\nnamespace/default\n", stderr=""))
        self.exam.start("weighted")
        deleted = [c[3] for c in self.cluster.calls if c[:3] == ["kubectl", "delete", "namespace"]]
        self.assertEqual(sorted(deleted), ["drill-t31", "exam-t01"])
        flat = [" ".join(c) for c in self.cluster.calls]
        self.assertTrue(any("pv/drill-t31-app-storage" in c for c in flat))
        self.assertTrue(any("pv/exam-t31-app-storage" in c for c in flat))
        self.exam.end()
        self.assertFalse(next(t for t in self.drill.state()["tasks"] if t["id"] == "t31")["deployed"])
        self.drill.open("t31")
        self.assertEqual(self.cluster.deploys.count("drill-t31"), 2)

    # ---- the exam lock
    def test_every_drill_operation_is_locked_while_an_exam_is_live(self):
        self.drill.open(self.tid)
        self.exam.start("weighted")
        self.assertTrue(self.drill.state()["exam_live"])
        for fn in (lambda: self.drill.open(self.tid), lambda: self.drill.check(self.tid),
                   lambda: self.drill.hint(self.tid, 1), lambda: self.drill.reset(self.tid)):
            with self.assertRaises(Locked):
                fn()
        self.exam.end()
        self.assertFalse(self.drill.state()["exam_live"])
        self.drill.hint(self.tid, 1)

    def test_a_check_that_straddles_an_exam_start_is_discarded(self):
        self.drill.open(self.tid)
        self.cluster.on_validate = lambda: setattr(self.exam, "starting", True)
        self.cluster.pass_next = True
        with self.assertRaises(Locked):
            self.drill.check(self.tid)
        self.assertFalse(next(t for t in self.drill.state()["tasks"] if t["id"] == self.tid)["solved"])


    # ---- the checker's output is gated behind Hint 1
    def _failing(self, out="sessionAffinity: None (should be: ClientIP)"):
        self.cluster.validate = lambda *a, **k: (False, "\x1b[31m" + out + "\x1b[0m")

    def test_failed_check_withholds_output_until_hint_1_on_every_surface(self):
        self._failing()
        self.drill.open(self.tid)
        r = self.drill.check(self.tid)
        self.assertEqual((r["verdict"], r["message"], r["output"], r["output_withheld"]), ("failed", "Not passed yet.", None, True))
        self.assertIsNone(r["last_output"])
        row = next(t for t in self.drill.state()["tasks"] if t["id"] == self.tid)
        self.assertIsNone(row["last_output"])
        self.assertTrue(row["output_withheld"])
        self.assertIsNone(self.drill.open(self.tid)["last_output"])
        self.assertNotIn("ClientIP", json.dumps(self.drill.state()))
        # the data is stored, only the surfaces withhold it
        self.assertIn("ClientIP", json.loads((Path(self.tmp.name) / "drill.json").read_text())["tasks"][self.tid]["last_output"])

    def _surfaces(self):
        """The checker output as seen on every surface, in one tuple."""
        row = next(t for t in self.drill.state()["tasks"] if t["id"] == self.tid)
        return (self.drill.check(self.tid)["output"], row["last_output"], self.drill.open(self.tid)["last_output"])

    def test_output_stays_withheld_after_hint_1_and_2_and_shows_from_hint_3(self):
        self._failing()
        self.drill.open(self.tid)
        self.drill.check(self.tid)
        for n in (1, 2):
            p = self.drill.hint(self.tid, n)
            self.assertEqual((p["last_output"], p["output_withheld"]), (None, True), "after hint %d" % n)
            self.assertEqual(self._surfaces(), (None, None, None), "after hint %d" % n)
        p = self.drill.hint(self.tid, 3)
        self.assertEqual(p["last_output"], "sessionAffinity: None (should be: ClientIP)")     # ANSI stripped
        self.assertFalse(p["output_withheld"])
        self.assertEqual(set(self._surfaces()), {p["last_output"]})

    def test_a_passed_check_shows_its_output_with_no_hints(self):
        self.drill.open(self.tid)
        self.cluster.validate = lambda *a, **k: (True, "all good")
        r = self.drill.check(self.tid)
        self.assertEqual((r["output"], r["hints_revealed"]), ("all good", 0))

    # ---- exam start versus drill operations in flight
    def test_exam_start_is_locked_to_drill_while_it_sweeps(self):
        states = []
        self.cluster.on_run = lambda args: states.append(self.drill.exam_live())
        self.exam.start("weighted")
        self.assertTrue(states and all(states))

    def test_mid_sweep_drill_request_is_refused(self):
        seen = []

        def probe(args):
            if args[:3] == ["kubectl", "get", "ns"]:
                try:
                    self.drill.hint(self.tid, 1)
                    seen.append("allowed")
                except Locked:
                    seen.append("locked")
        self.cluster.on_run = probe
        self.exam.start("weighted")
        self.assertEqual(seen, ["locked"])

    def test_exam_start_waits_for_a_drill_operation_in_flight(self):
        self.drill.busy.add(self.tid)
        threading.Timer(0.3, lambda: self.drill.busy.discard(self.tid)).start()
        t0 = time.monotonic()
        out = self.exam.start("weighted")
        self.assertGreaterEqual(time.monotonic() - t0, 0.25)
        self.assertFalse(any("drill operation" in w for w in out["warnings"]))

    def test_a_drain_timeout_refuses_the_start_and_leaves_no_session(self):
        self.exam.drain_timeout = 0.2
        self.drill.busy.add(self.tid)
        with self.assertRaises(Conflict) as cm:
            self.exam.start("weighted")
        self.assertIn("still being prepared", str(cm.exception))
        self.assertIsNone(self.exam.session)
        self.assertFalse(Path(self.tmp.name, "session.json").exists())
        self.assertFalse(self.exam.starting)
        self.assertEqual(self.cluster.calls, [])             # nothing was swept
        self.drill.busy.discard(self.tid)
        self.drill.hint(self.tid, 1)                         # Drill is usable again

    def test_a_refused_start_keeps_a_running_exam_running(self):
        self.exam.start("weighted")
        self.exam.drain_timeout = 0.2
        self.drill.busy.add("t03")
        sid = self.exam.session.id
        with self.assertRaises(Conflict):
            self.exam.start("weighted")
        self.assertEqual((self.exam.session.id, self.exam.session.ended), (sid, None))
        self.drill.busy.discard("t03")

    def test_a_drill_op_resuming_after_an_exam_went_live_deletes_nothing(self):
        self.exam.starting = True            # the exam went live after the drill op passed its entry guard
        with self.assertRaises(Locked):
            self.drill._deploy(pool.BY_ID["t45"])
        self.assertEqual((self.cluster.deletes, self.cluster.deploys, self.cluster.calls), ([], [], []))

    def test_exam_going_live_between_cluster_steps_stops_the_next_step(self):
        self.cluster.on_delete = lambda: setattr(self.exam, "starting", True)
        with self.assertRaises(Locked):
            self.drill._deploy(pool.BY_ID["t45"])
        self.assertEqual(len(self.cluster.deletes), 1)       # the step in flight finished
        self.assertEqual(self.cluster.calls, [])             # no node reset (t45 labels) afterwards
        self.assertEqual(self.cluster.deploys, [])

    def test_exam_going_live_after_the_leftover_delete_stops_the_deploy(self):
        self.cluster.on_delete = lambda: setattr(self.exam, "starting", True)
        with self.assertRaises(Locked):
            self.drill._deploy(pool.BY_ID["t03"])           # no node reset for this task: only the deploy guard can stop it
        self.assertEqual(self.cluster.deploys, [])

    # ---- every operation holds busy while its cluster work runs
    def test_open_check_and_reset_hold_busy_during_their_cluster_work(self):
        seen = {}
        self.cluster.on_deploy = lambda: seen.setdefault("deploy", []).append(self.tid in self.drill.busy)
        self.cluster.on_validate = lambda: seen.setdefault("validate", []).append(self.tid in self.drill.busy)
        self.drill.open(self.tid)
        self.drill.check(self.tid)
        self.drill.reset(self.tid)
        self.assertEqual(seen, {"deploy": [True, True], "validate": [True]})
        self.assertEqual(self.drill.busy, set())             # and released afterwards

    def test_open_that_straddles_an_exam_start_removes_its_namespace(self):
        self.cluster.on_deploy = lambda: setattr(self.exam, "starting", True)
        with self.assertRaises(Locked):
            self.drill.open("t31")
        self.assertIn(("drill-t31", ["pv/drill-t31-app-storage"]), self.cluster.deletes)
        self.assertFalse(next(t for t in self.drill.state()["tasks"] if t["id"] == "t31")["deployed"])

    def test_reset_that_straddles_an_exam_start_removes_its_namespace(self):
        self.drill.open("t31")
        self.cluster.deletes.clear()
        self.cluster.on_deploy = lambda: setattr(self.exam, "starting", True)
        with self.assertRaises(Locked):
            self.drill.reset("t31")
        self.assertIn(("drill-t31", ["pv/drill-t31-app-storage"]), self.cluster.deletes)

    def test_reset_deploys_with_drill_prefixed_cluster_objects(self):
        self.drill.open("t31")
        self.drill.reset("t31")
        self.assertEqual(self.cluster.deploy_objects, [["pv/drill-t31-app-storage"]] * 2)

    # ---- cluster-global collisions
    def test_deploy_first_deletes_the_same_tasks_exam_leftovers(self):
        self.drill.open("t31")
        self.assertEqual(self.cluster.deletes[0], ("exam-t31", ["pv/exam-t31-app-storage"]))
        self.drill.reset("t31")
        self.assertEqual(self.cluster.deletes[-1], ("exam-t31", ["pv/exam-t31-app-storage"]))
        self.assertTrue(all(ns == "exam-t31" for ns, _ in self.cluster.deletes))

    def test_only_t45_resets_node_state(self):
        node_reset = lambda: [c for c in self.cluster.calls if c[:3] == ["kubectl", "get", "nodes"]]
        self.drill.open("t03")
        self.assertEqual(node_reset(), [])
        self.drill.open("t45")
        self.assertEqual(len(node_reset()), 1)
        self.drill.reset("t45")
        self.assertEqual(len(node_reset()), 2)
        self.assertEqual([t["id"] for t in pool.POOL if t.get("node_reset")], ["t45"])

    # ---- start survives a drill.json problem; DrillFile tolerates junk
    def test_drill_json_failure_does_not_break_exam_start(self):
        self.drill.open(self.tid)
        self.drill.clear_deployed = lambda: 1 / 0
        out = self.exam.start("weighted")
        self.assertTrue(any("drill.json" in w for w in out["warnings"]))
        self.assertIsNotNone(self.exam.session)
        self.assertTrue(Path(self.tmp.name, "session.json").exists())

    def test_drillfile_drops_non_dict_task_entries(self):
        f = DrillFile(Path(self.tmp.name) / "junk.json")
        f.save({"tasks": {"t01": 5, "t03": {"solved": True}, "t04": None}})
        self.assertEqual(f.load(), {"tasks": {"t03": {"solved": True}}})
        again = Exam(Results(Path(self.tmp.name) / "r2.json"), SessionFile(Path(self.tmp.name) / "s2.json"),
                     now=Clock(), cluster=FakeCluster(), do_reset=False, drillfile=f)
        again.drill.open("t01")


class DrillHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.exam = make(cls.tmp.name)
        server.EXAM = cls.exam
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.tmp.cleanup()

    def call(self, method, path, body=None, ctype="application/json"):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        h = {"Host": f"localhost:{self.port}"}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            h["Content-Type"] = ctype
        c.request(method, path, data, h)
        r = c.getresponse()
        out = json.loads(r.read())
        c.close()
        return r.status, out

    def test_1_http_flow_and_hint_order(self):
        code, st = self.call("GET", "/api/drill/state")
        self.assertEqual((code, st["exam_live"]), (200, False))
        self.assertEqual(self.call("POST", "/api/drill/open", {"id": "t03"})[0], 200)
        self.assertEqual(self.call("POST", "/api/drill/hint", {"id": "t03", "n": 2})[0], 409)
        self.assertEqual(self.call("POST", "/api/drill/hint", {"id": "t03", "n": 1})[0], 200)
        self.assertEqual(self.call("POST", "/api/drill/hint", {"id": "t03", "n": 9})[0], 400)
        self.assertEqual(self.call("POST", "/api/drill/check", {"id": "t03"})[0], 200)
        self.assertEqual(self.call("POST", "/api/drill/reset", {"id": "t03"})[0], 200)
        self.assertEqual(self.call("POST", "/api/drill/open", {"id": "t99"})[0], 404)
        self.assertEqual(self.call("POST", "/api/drill/open", {"id": 5})[0], 400)
        self.assertEqual(self.call("POST", "/api/drill/open", {"id": "t03"}, ctype="text/plain")[0], 415)

    def test_2_every_drill_post_is_409_while_an_exam_is_live(self):
        self.call("POST", "/api/session/start", {"mode": "weighted"})
        try:
            self.assertEqual(self.call("GET", "/api/drill/state")[1]["exam_live"], True)
            for op, body in (("open", {"id": "t03"}), ("check", {"id": "t03"}), ("hint", {"id": "t03", "n": 1}),
                             ("reset", {"id": "t03"}), ("open", {})):
                code, out = self.call("POST", "/api/drill/" + op, body)
                self.assertEqual(code, 409, op)
                self.assertIn("exam", out["error"].lower())
        finally:
            self.call("POST", "/api/session/end", {})
        self.assertEqual(self.call("POST", "/api/drill/hint", {"id": "t03", "n": 1})[0], 200)    # unlocked again


if __name__ == "__main__":
    unittest.main()
