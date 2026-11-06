"""Exam/Session behaviour with a fake cluster and a fake clock: server-side in-time accounting."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import tests._path  # noqa: F401
import pool
from server import Exam
from store import Results, SessionFile


class FakeCluster:
    def __init__(self):
        self.deploys = []
        self.pass_next = False
        self.on_validate = None
        self.run_rc = 0
        self.calls = []

    def run(self, args, **kw):
        self.calls.append(args)
        return SimpleNamespace(returncode=self.run_rc, stdout="", stderr="boom" if self.run_rc else "")

    def deploy(self, level, ns, renames, cluster_objects=(), node_labels=()):
        self.deploys.append(ns)
        return True, ""

    def validate(self, level, ns, renames, timeout=120):
        if self.on_validate:
            self.on_validate()
        return self.pass_next, "\x1b[32mchecked\x1b[0m line"


class Clock:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


class ExamCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.clock = Clock()
        self.cluster = FakeCluster()
        self.exam = Exam(Results(d / "results.json"), SessionFile(d / "session.json"),
                         now=self.clock, cluster=self.cluster, do_reset=False)
        self.exam.start("weighted")
        self.tid = self.exam.session.tasks[0]["id"]
        self.exam.open_task(self.tid)

    def tearDown(self):
        self.tmp.cleanup()

    def work(self, seconds, step=10):
        end = self.clock.t + seconds
        while self.clock.t < end:
            self.clock.t = min(end, self.clock.t + step)
            self.exam.event(self.tid, "beat")

    def check(self, passed):
        self.cluster.pass_next = passed
        return self.exam.check(self.tid)

    def test_session_has_16_tasks_rotating_hosts(self):
        tasks = self.exam.session.tasks
        self.assertEqual(len(tasks), 16)
        self.assertEqual([t["host"] for t in tasks[:4]], ["cka1", "cka2", "cka3", "cka1"])

    def test_pass_at_449_counts(self):
        self.work(449)
        r = self.check(True)
        self.assertEqual(r["verdict"], "passed_in_time")
        self.assertTrue(self.exam.results.counted(self.tid))

    def test_pass_at_451_does_not_count(self):
        self.work(451)
        r = self.check(True)
        self.assertEqual(r["verdict"], "passed_over_time")
        self.assertIn("does not count", r["message"])
        self.assertFalse(self.exam.results.counted(self.tid))
        a = self.exam.results.attempts(self.tid)[0]
        self.assertTrue(a["passed"] and not a["in_time"])

    def test_failed_check_is_recorded_and_ansi_stripped(self):
        self.work(30)
        r = self.check(False)
        self.assertEqual(r["verdict"], "failed")
        self.assertEqual(r["output"], "checked line")
        self.assertEqual(len(self.exam.results.attempts(self.tid)), 1)

    def test_time_accumulates_across_visits(self):
        self.work(240)
        other = self.exam.session.tasks[1]["id"]
        self.exam.open_task(other)                 # leaves the first task
        self.clock.t += 600                        # a long time elsewhere costs the first task nothing
        self.exam.event(other, "hide")
        self.exam.event(self.tid, "show")
        self.work(210)                             # 240 + 210 = 450 -> still in time
        self.assertEqual(self.check(True)["verdict"], "passed_in_time")
        self.work(2)                               # 452 -> over
        self.assertEqual(self.check(True)["verdict"], "passed_over_time")

    def test_results_persist_across_server_restarts(self):
        self.work(100)
        self.check(True)
        again = Results(Path(self.tmp.name) / "results.json")
        self.assertTrue(again.counted(self.tid))
        restored = Exam(again, SessionFile(Path(self.tmp.name) / "session.json"),
                        now=self.clock, cluster=self.cluster, do_reset=False)
        self.assertEqual(restored.session.id, self.exam.session.id)

    def test_end_summary_and_missed_first_session(self):
        self.work(100)
        self.check(True)
        self.exam.end()
        sm = self.exam.state()["session"]["summary"]
        self.assertEqual(sm["counted"], [self.tid])
        self.assertEqual(len(sm["missed"]), 15)
        self.exam.start("missed")
        ids = [t["id"] for t in self.exam.session.tasks]
        self.assertNotIn(self.tid, ids)

    def test_status_labels(self):
        st = lambda: self.exam.state()["session"]["tasks"][0]["status"]
        self.assertEqual(st(), "opened")
        self.exam.flag(self.tid, True)
        self.assertEqual(st(), "flagged")
        self.work(10)
        self.check(False)
        self.assertEqual(st(), "failed")
        self.assertEqual(self.exam.state()["session"]["tasks"][1]["status"], "not_opened")

    def test_deploy_only_on_first_open(self):
        n = len(self.cluster.deploys)
        self.exam.open_task(self.tid)
        self.assertEqual(len(self.cluster.deploys), n)
        self.assertEqual(self.cluster.deploys[0], pool.namespace(self.tid))

    # ---- review fixes
    def test_slow_validator_does_not_push_a_pass_over_time(self):
        self.work(440)
        self.cluster.on_validate = lambda: setattr(self.clock, "t", self.clock.t + 30)   # validator sleeps
        self.assertEqual(self.check(True)["verdict"], "passed_in_time")

    def test_clock_resumes_after_server_restart(self):
        self.work(100)
        d = Path(self.tmp.name)
        again = Exam(Results(d / "results.json"), SessionFile(d / "session.json"),
                     now=self.clock, cluster=self.cluster, do_reset=False)
        self.clock.t += 5
        again.event(self.tid, "beat")
        for _ in range(5):
            self.clock.t += 10
            again.event(self.tid, "beat")
        # the 5 s the server was down are not charged: 100 s before + 50 s of beats after
        self.assertEqual(again.session.elapsed(self.tid, self.clock.t), 100 + 50)

    def test_check_in_flight_across_end_and_start_is_dropped(self):
        def swap():
            self.exam.end()
            self.exam.start("weighted")
        self.cluster.on_validate = swap
        self.work(30)
        self.cluster.pass_next = True
        with self.assertRaises(ValueError):
            self.exam.check(self.tid)
        self.assertEqual(self.exam.results.attempts(self.tid), [])
        self.assertTrue(all(not t["attempts"] for t in self.exam.session.tasks))

    def test_hidden_flag_survives_a_restart(self):
        self.work(30)
        self.exam.event(self.tid, "hide")
        d = Path(self.tmp.name)
        again = Exam(Results(d / "results.json"), SessionFile(d / "session.json"),
                     now=self.clock, cluster=self.cluster, do_reset=False)
        self.assertTrue(again.session.clocks.hidden)
        self.clock.t += 5
        again.event(self.tid, "beat")                 # a late beat after an explicit hide must not restart it
        self.assertFalse(again.session.clocks.clock(self.tid).running)
        again.event(self.tid, "show")
        self.assertTrue(again.session.clocks.clock(self.tid).running)

    def test_start_resets_node_state(self):
        self.cluster.calls.clear()
        self.exam.start("weighted")
        self.assertIn(["kubectl", "get", "nodes", "-o", "name"], self.cluster.calls)

    def test_hide_names_its_task(self):
        other = self.exam.session.tasks[1]["id"]
        self.exam.open_task(other)
        self.exam.event(self.tid, "hide")            # stale hide for a task that is no longer shown
        self.assertTrue(self.exam.session.clocks.clock(other).running)

    def test_flag_must_be_a_real_boolean(self):
        for bad in ("false", 1, None, "yes"):
            with self.assertRaises(ValueError):
                self.exam.flag(self.tid, bad)
        self.assertFalse(self.exam.session.get(self.tid)["flagged"])

    def test_persisted_session_with_unknown_task_is_dropped(self):
        d = Path(self.tmp.name)
        sf = SessionFile(d / "session.json")
        data = sf.load()
        data["tasks"][0]["id"] = "t99"
        sf.save(data)
        fresh = Exam(Results(d / "results.json"), sf, now=self.clock, cluster=self.cluster, do_reset=False)
        self.assertIsNone(fresh.state()["session"])

    def test_namespace_sweep_failure_is_reported(self):
        self.cluster.run_rc = 1
        out = self.exam.start("weighted")
        self.assertTrue(any("could not list namespaces" in w for w in out["warnings"]), out)
        self.assertTrue(any("could not list nodes" in w for w in out["warnings"]), out)

    def test_every_session_id_is_unique_within_a_second(self):
        ids = set()
        for _ in range(5):
            self.exam.start("weighted")
            ids.add(self.exam.session.id)
        self.assertEqual(len(ids), 5)


if __name__ == "__main__":
    unittest.main()
