"""Kubeadm tasks: the cka-kubeadm root helper (fake Proxmox, ssh and clock) and Drill's kubeadm ownership. No real subprocess."""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from urllib.parse import unquote

import tests._path  # noqa: F401
import levels
import pool
from drill import Conflict, Locked
from tests.test_drill import make
from tests.test_exam import Clock, FakeCluster

HELPER = Path(__file__).resolve().parent.parent / "hosts" / "cka-kubeadm"
_loader = importlib.machinery.SourceFileLoader("cka_kubeadm", str(HELPER))
ck = importlib.util.module_from_spec(importlib.util.spec_from_loader("cka_kubeadm", _loader))
_loader.exec_module(ck)

TOKEN = "PVEAPIToken=cka@pve!drill=0123456789abcdef-SECRET"


class FakeWorld:
    """A fake Proxmox + two VMs + ssh + kubectl + clock. Records every call so tests can assert order and leaks."""

    def __init__(self, status=("running", "running"), task_polls=2, ready_after=3, task_exit="OK", fail_http=None):
        self.vm = {111: status[0], 112: status[1]}
        self.task_polls, self.task_exit, self.fail_http = task_polls, task_exit, fail_http
        self.ready_after = ready_after          # ssh and kubectl succeed from this many readiness polls on; None = never
        self.now = 0.0
        self.http_calls, self.runs, self.logs = [], [], []
        self.tasks = {}                          # upid -> [polls left, vmid, effect]
        self.polls = 0
        self.ca = str(HELPER)            # any non-empty file stands in for the CA
        self._tmp = tempfile.TemporaryDirectory()
        self.gen = os.path.join(self._tmp.name, "state", "generation")
        self.locks = []                  # timeouts of every lock acquisition

    def clock(self):
        return self.now

    def sleep(self, n):
        self.now += n

    def http(self, method, url, token):
        self.http_calls.append((method, url.replace(ck.PVE_BASE, ""), token))
        path = url.replace(ck.PVE_BASE, "")
        if self.fail_http and self.fail_http[0] == (method, path.split("?")[0].split("/")[-1]):
            return self.fail_http[1], {"data": None, "message": self.fail_http[2]}, "reason"
        if path == "/cluster/resources?type=vm":
            return 200, {"data": [{"vmid": 111, "node": "pve1", "type": "qemu"}, {"vmid": 112, "node": "pve1", "type": "qemu"},
                                  {"vmid": 200, "node": "pve1", "type": "qemu"}]}, "OK"
        parts = path.strip("/").split("/")
        if method == "GET" and path.endswith("/status/current"):
            return 200, {"data": {"status": self.vm[int(parts[3])]}}, "OK"
        if method == "POST":
            vmid = int(parts[3])
            effect = "stopped" if path.endswith("/rollback") else "running"
            upid = "UPID:pve1:00AB:%s:qm%s:%d:cka@pve!drill:" % (parts[-1], parts[-1], vmid)
            self.tasks[upid] = [self.task_polls, vmid, effect]
            return 200, {"data": upid}, "OK"
        if method == "GET" and "/tasks/" in path:
            upid = unquote(parts[3])
            t = self.tasks[upid]
            if t[0] > 0:
                t[0] -= 1
                return 200, {"data": {"status": "running"}}, "OK"
            self.vm[t[1]] = t[2] if self.task_exit == "OK" else self.vm[t[1]]
            return 200, {"data": {"status": "stopped", "exitstatus": self.task_exit}}, "OK"
        raise AssertionError("unexpected PVE call %s %s" % (method, path))

    def _ready(self):
        return self.ready_after is not None and self.polls >= self.ready_after

    def run(self, argv, env=None, input=None, capture=False, timeout=None):
        self.runs.append({"argv": list(argv), "env": dict(env) if env is not None else None, "input": input, "timeout": timeout})
        if argv[-1] == "true":
            if all(v == "running" for v in self.vm.values()):
                self.polls += 1
            return (0 if self._ready() else 255), "", ""
        if argv[:3] == ["kubectl", "get", "nodes"]:
            ready = "True" if self._ready() else "False"
            items = [{"metadata": {"name": n}, "status": {"conditions": [{"type": "Ready", "status": ready}]}} for n in ("controlplane", "node01")]
            return 0, json.dumps({"items": items}), ""
        return 7, "", ""

    def kube(self, **kw):
        return ck.Kubeadm(TOKEN, http=self.http, run=self.run, sleep=self.sleep, clock=self.clock, log=self.logs.append, **kw)

    def main(self, argv, stdin=""):
        err, out = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            rc = ck.main(argv, stdin=io.StringIO(stdin), token=TOKEN, ca=self.ca, gen_path=self.gen, lock=self.lock, http=self.http, run=self.run, sleep=self.sleep,
                         clock=self.clock, log=lambda m: print("cka-kubeadm: " + m, file=err))
        return rc, out.getvalue(), err.getvalue()

    @contextlib.contextmanager
    def lock(self, timeout):
        self.locks.append(timeout)
        yield

    def posts(self):
        return [(c[1].split("/qemu/")[1]) for c in self.http_calls if c[0] == "POST"]


class HelperRollback(unittest.TestCase):
    def test_rollback_posts_both_rollbacks_then_starts_both_then_waits_for_ready(self):
        w = FakeWorld()
        rc, out, err = w.main(["rollback"])
        self.assertEqual(rc, 0, err)
        self.assertRegex(out.strip(), r"^GENERATION=[0-9a-f]{16}$")
        self.assertEqual(w.locks, [420])
        self.assertEqual("GENERATION=" + w.main(["generation"])[1].strip(), out.strip())
        self.assertEqual(w.posts(), ["111/snapshot/k8s-1-36-clean/rollback", "112/snapshot/k8s-1-36-clean/rollback",
                                     "111/status/start", "112/status/start"])
        # both rollbacks were requested before either task was polled, and both tasks stopped before the first start
        first_task_poll = next(i for i, c in enumerate(w.http_calls) if "/tasks/" in c[1])
        self.assertEqual([c[0] for c in w.http_calls[:first_task_poll]].count("POST"), 2)
        first_start = next(i for i, c in enumerate(w.http_calls) if c[1].endswith("/status/start"))
        rb_done = [i for i, c in enumerate(w.http_calls) if "/tasks/" in c[1] and "rollback" in unquote(c[1])]
        self.assertTrue(rb_done and max(rb_done) < first_start)         # both rollback tasks were polled before any start
        self.assertEqual(w.vm, {111: "running", 112: "running"})
        self.assertIn("cluster ready", err)
        self.assertTrue(any(c[1].startswith("/nodes/pve1/tasks/UPID%3A") for c in w.http_calls))     # the upid is URL-quoted

    def test_ready_needs_vms_ssh_and_both_nodes(self):
        w = FakeWorld(ready_after=4)
        w.main(["ensure-up"])
        ssh = [r for r in w.runs if r["argv"][-1] == "true"]
        self.assertEqual(ssh[0]["argv"][:9], ["sudo", "-n", "-H", "-u", "david", "ssh", "-o", "BatchMode=yes", "-o"])
        self.assertEqual({r["argv"][-2] for r in ssh}, {"david@192.168.1.226", "david@192.168.1.227"})
        self.assertEqual(w.runs[-1]["argv"][:3], ["kubectl", "get", "nodes"])
        self.assertEqual(w.runs[-1]["env"]["KUBECONFIG"], "/etc/cka-hosts/cluster1.kubeconfig")

    def test_progress_is_one_line_per_phase(self):
        w = FakeWorld(ready_after=3)
        rc, _, err = w.main(["rollback"])
        lines = [l for l in err.splitlines() if l.startswith("cka-kubeadm: waiting for")]
        self.assertEqual(len(lines), len(set(lines)))
        self.assertIn("cka-kubeadm: waiting for ssh to both VMs", lines)

    def test_a_failed_task_stops_the_rollback_with_the_exit_status(self):
        w = FakeWorld(task_exit="ERROR: rollback failed: no such snapshot")
        rc, _, err = w.main(["rollback"])
        self.assertEqual(rc, 1)
        self.assertIn("rollback of VM 111 failed: ERROR: rollback failed: no such snapshot", err)
        self.assertEqual([p for p in w.posts() if "start" in p], [])        # nothing was started

    def test_an_http_error_prints_the_status_and_the_pve_message_only(self):
        w = FakeWorld(fail_http=(("POST", "rollback"), 403, "Permission check failed (/vms/111, VM.Snapshot.Rollback)"))
        rc, out, err = w.main(["rollback"])
        self.assertEqual(rc, 1)
        self.assertIn("HTTP 403: Permission check failed (/vms/111, VM.Snapshot.Rollback)", err)
        self.assertNotIn(TOKEN, err + out)
        self.assertNotIn("SECRET", err + out)

    def test_it_times_out_after_420_seconds_when_the_cluster_never_gets_ready(self):
        w = FakeWorld(ready_after=None)
        rc, _, err = w.main(["ensure-up"])
        self.assertEqual(rc, 1)
        self.assertIn("timed out after 420s waiting for ssh to both VMs", err)
        self.assertGreaterEqual(w.now, 420)
        self.assertLess(w.now, 430)

    def test_a_task_that_never_stops_times_out(self):
        w = FakeWorld(task_polls=10 ** 6)
        rc, _, err = w.main(["rollback"])
        self.assertEqual(rc, 1)
        self.assertIn("timed out waiting for rollback of VM 111", err)

    def test_ensure_up_starts_only_the_stopped_vm_and_never_rolls_back(self):
        w = FakeWorld(status=("running", "stopped"))
        rc, _, err = w.main(["ensure-up"])
        self.assertEqual((rc, w.posts()), (0, ["112/status/start"]))
        self.assertEqual(w.vm[112], "running")

    def test_ensure_up_on_a_running_cluster_posts_nothing(self):
        w = FakeWorld()
        self.assertEqual(w.main(["ensure-up"])[0], 0)
        self.assertEqual(w.posts(), [])

    def test_the_token_is_only_ever_a_request_header(self):
        w = FakeWorld(status=("stopped", "stopped"))
        rc, out, err = w.main(["rollback"])
        self.assertEqual(rc, 0)
        self.assertTrue(w.http_calls and all(c[2] == TOKEN for c in w.http_calls))      # used as the header value
        for r in w.runs:                                                                 # never given to a child
            self.assertNotIn("SECRET", " ".join(r["argv"]))
            self.assertFalse(any("SECRET" in v for v in (r["env"] or {}).values()))
            self.assertNotIn("SECRET", r["input"] or "")
        self.assertNotIn("SECRET", out + err + "".join(w.logs))
        self.assertTrue(all("SECRET" not in c[1] for c in w.http_calls))                 # nor in a URL


class HelperOther(unittest.TestCase):
    def test_run_on_pipes_stdin_to_sudo_bash_over_ssh_and_relays_the_exit_code(self):
        w = FakeWorld()
        rc, _, _ = w.main(["run-on", "node01"], stdin="echo hi\nexit 3\n")
        self.assertEqual(rc, 7)                                    # the fake's rc for any other command comes back unchanged
        self.assertEqual(w.runs[0]["argv"], ["sudo", "-n", "-H", "-u", "david", "ssh"] + ck.SSH_OPTS +
                         ["david@192.168.1.227", "sudo", "bash", "-s"])
        self.assertEqual(w.runs[0]["timeout"], 240)
        self.assertEqual(w.locks, [60])           # run-on waits at most 60 s for the lock
        self.assertEqual(w.runs[0]["input"], "echo hi\nexit 3\n")
        w2 = FakeWorld()
        w2.main(["run-on", "controlplane"], stdin="x")
        self.assertIn("david@192.168.1.226", w2.runs[0]["argv"])
        self.assertEqual(w2.http_calls, [])                         # no PVE call, so no token needed

    def test_the_kubectl_subcommand_is_gone(self):
        w = FakeWorld()
        rc, _, err = w.main(["kubectl", "get", "nodes"])
        self.assertEqual(rc, 2)
        self.assertIn("usage", err)
        self.assertEqual(w.runs, [])
        self.assertNotIn("kubectl ARGS", ck.USAGE)
        self.assertFalse(hasattr(ck.Kubeadm, "kubectl"))

    def test_usage_errors_exit_2_and_run_nothing(self):
        w = FakeWorld()
        for argv in ([], ["bogus"], ["rollback", "now"], ["ensure-up", "x"], ["run-on"], ["run-on", "mars"], ["run-on", "node01", "x"]):
            self.assertEqual(w.main(argv)[0], 2, argv)
        self.assertEqual((w.runs, w.http_calls), ([], []))

    def test_an_unreadable_or_empty_token_file_is_an_error_that_does_not_print_it(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ck.Failure) as cm:
                ck.read_token(os.path.join(d, "missing"))
            self.assertNotIn(d, str(cm.exception))
            f = Path(d) / "tok"
            f.write_text("  \n")
            with self.assertRaises(ck.Failure):
                ck.read_token(str(f))
            f.write_text(TOKEN + "\n")
            self.assertEqual(ck.read_token(str(f)), TOKEN)

    def test_a_missing_or_empty_ca_refuses_before_any_request(self):
        for make_ca in (lambda d: os.path.join(d, "none.pem"), lambda d: (Path(d, "e.pem").write_text("") or str(Path(d, "e.pem")))):
            with tempfile.TemporaryDirectory() as d:
                w = FakeWorld()
                w.ca = make_ca(d)
                for cmd in ("rollback", "ensure-up"):
                    rc, _, err = w.main([cmd])
                    self.assertEqual(rc, 1)
                    self.assertIn("Proxmox CA", err)
                    self.assertIn("without verifying", err)
                self.assertEqual((w.http_calls, w.runs), ([], []))

    def test_the_real_http_verifies_the_chain_but_not_the_hostname(self):
        made = {}

        class Ctx:
            pass
        real = ck.ssl.create_default_context

        def fake(cafile=None):
            made["cafile"] = cafile
            c = real()
            made["ctx"] = c
            return c
        with mock.patch.object(ck.ssl, "create_default_context", fake), \
                mock.patch.object(ck.urllib.request, "urlopen", side_effect=OSError("stop")):
            with self.assertRaises(ck.Failure):
                ck.real_http("GET", "https://x/", "t")
        self.assertEqual(made["cafile"], "/etc/cka-hosts/pve-ca.pem")
        self.assertEqual((made["ctx"].verify_mode, made["ctx"].check_hostname), (ck.ssl.CERT_REQUIRED, False))
        with mock.patch.object(ck, "CA_FILE", "/nonexistent/ca.pem"):
            with self.assertRaises(ck.Failure) as cm:
                ck.real_http("GET", "https://x/", "t")
        self.assertIn("cannot load the Proxmox CA", str(cm.exception))

    def test_the_helper_file_is_executable_python(self):
        self.assertTrue(os.access(HELPER, os.X_OK))
        self.assertTrue(HELPER.read_text().startswith("#!/usr/bin/env python3\n"))


# ---------------------------------------------------------------- Drill
class KubeadmCluster(FakeCluster):
    """FakeCluster plus the kubeadm calls, logged in order."""

    def __init__(self, clock=None):
        super().__init__()
        self.klog = []
        self.clock = clock
        self.rollback_secs = 0
        self.fail = {}                  # step name -> message
        self.on_rollback = None
        self.pass_kubeadm = False
        self.gen = 0                    # the helper's generation token; replaced on every rollback ATTEMPT, like the real one
        self.gen_reads = 0

    def kubeadm_generation(self):
        self.gen_reads += 1
        return self.gen

    def _step(self, name, extra=""):
        self.klog.append(name + extra)
        return (False, self.fail[name]) if name in self.fail else (True, "")

    def kubeadm_rollback(self):
        if self.clock:
            self.clock.t += self.rollback_secs
        if self.on_rollback:
            self.on_rollback()
        self.gen += 1                   # the helper replaces the token before its first Proxmox call, so a failure bumps too
        ok, msg = self._step("rollback")
        return ok, msg, (self.gen if ok else None)

    def kubeadm_ensure_up(self):
        return self._step("ensure_up")

    def kubeadm_setup(self, rel):
        return self._step("setup", ":" + rel)

    def kubeadm_validate(self, rel, timeout=180):
        self.klog.append("validate:" + rel)
        return self.pass_kubeadm, "checked"


class KubeadmDrill(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = Clock()
        self.cluster = KubeadmCluster(self.clock)
        self.exam = make(self.tmp.name, self.cluster, self.clock)
        self.drill = self.exam.drill
        other = dict(pool.BY_ID_QUESTION["c100"], id="c999")
        dp = [pool.BY_ID_QUESTION["c100"], other, pool.BY_ID["t03"]]
        for m in (mock.patch.object(pool, "DRILL_POOL", dp), mock.patch.object(pool, "DRILL_BY_ID", {t["id"]: t for t in dp})):
            m.start()
            self.addCleanup(m.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def owner(self):
        return self.drill.data["kubeadm_owner"], self.drill.data["kubeadm_epoch"]

    def test_c100_is_a_kubeadm_task_outside_every_pool_but_the_drill_pool(self):
        t = pool.BY_ID_QUESTION["c100"]
        self.assertEqual((t["cluster"], t["qid"], t["source"], t["node_dependent"]), ("kubeadm", "etcd-3", "question", False))
        self.assertNotIn("c100", {x["id"] for x in pool.ALL_TASKS})
        self.assertIn("ssh controlplane", t["text"])
        self.assertEqual([x["id"] for x in pool.QUESTION_TASKS if x.get("cluster") == "kubeadm"], ["c%d" % i for i in range(100, 116)])
        self.assertTrue(all(x.get("cluster") is None for x in pool.ALL_TASKS))

    def test_open_rolls_back_then_sets_up_once_and_becomes_the_owner(self):
        self.cluster.rollback_secs = 125
        p = self.drill.open("c100")
        self.assertEqual(self.cluster.klog, ["rollback", "setup:questions/etcd-3"])
        self.assertEqual(self.owner(), ("c100", 1))
        self.assertEqual(self.drill._rec("c100")["kubeadm_epoch"], 1)
        self.assertEqual(p["notice"], "Rolled the kubeadm cluster back to a clean snapshot (took 125s).")
        self.assertEqual((p["cluster"], p["namespace"], p["deployed"], p["opened"]), ("kubeadm", None, True, True))
        self.assertEqual((self.cluster.deploys, self.cluster.calls, self.cluster.deletes), ([], [], []))   # kind is not touched
        self.assertEqual(self.drill.busy, set())

    def test_reopening_the_same_task_does_not_roll_back_but_makes_sure_the_vms_are_up(self):
        self.drill.open("c100")
        self.drill.open("c100")
        self.assertEqual(self.cluster.klog, ["rollback", "setup:questions/etcd-3", "ensure_up"])
        self.assertEqual(self.owner(), ("c100", 1))

    def test_a_failing_ensure_up_is_an_error_and_keeps_the_ownership(self):
        self.drill.open("c100")
        self.cluster.fail["ensure_up"] = "timed out after 420s waiting for ssh to both VMs"
        with self.assertRaises(RuntimeError) as cm:
            self.drill.open("c100")
        self.assertIn("timed out after 420s", str(cm.exception))
        self.assertEqual(self.owner(), ("c100", 1))
        self.assertEqual(self.drill.busy, set())

    def test_opening_another_kubeadm_task_rolls_back_again_and_the_first_becomes_stale(self):
        self.drill.open("c100")
        self.drill.open("c999")
        self.assertEqual(self.cluster.klog.count("rollback"), 2)
        self.assertEqual(self.owner(), ("c999", 2))
        self.cluster.klog.clear()
        with self.assertRaises(Conflict) as cm:
            self.drill.check("c100")
        self.assertEqual(str(cm.exception), "The kubeadm cluster no longer holds this task's setup. Press Reset task, then redo it.")
        self.assertEqual(self.cluster.klog, [])                    # the validator was not run
        self.assertEqual(self.drill._rec("c100")["attempts"], 0)   # and the refusal is not an attempt
        self.assertEqual(self.drill.busy, set())
        self.drill.open("c100")                                    # opening it again rebuilds its setup
        self.assertEqual(self.owner(), ("c100", 3))
        self.assertEqual(self.drill.check("c100")["verdict"], "failed")

    def test_a_failed_check_keeps_ownership_and_a_pass_marks_the_cluster_dirty(self):
        self.drill.open("c100")
        r = self.drill.check("c100")
        self.assertEqual((r["verdict"], r["attempts"]), ("failed", 1))
        self.assertEqual(self.owner(), ("c100", 1))
        self.cluster.pass_kubeadm = True
        r = self.drill.check("c100")
        self.assertEqual((r["verdict"], r["solved"]), ("passed", True))
        self.assertEqual(self.owner(), ("?", 1))                   # no rollback now: the next kubeadm open does it
        self.assertEqual(self.cluster.klog.count("rollback"), 1)
        self.assertIn("rolled back before the next kubeadm task", r["notice"])
        with self.assertRaises(Conflict):
            self.drill.check("c100")                               # nobody owns the cluster any more
        self.drill.open("c100")
        self.assertEqual(self.cluster.klog.count("rollback"), 2)   # even the same task is rebuilt after a pass
        self.assertEqual(self.owner(), ("c100", 2))

    def test_showing_the_solution_marks_the_cluster_dirty_only_for_the_owner(self):
        self.drill.open("c100")
        self.drill.open("c999")
        for i in (1, 2, 3, 4):
            self.drill.hint("c100", i)                             # c100 is not the owner
        self.assertEqual(self.owner(), ("c999", 2))
        for i in (1, 2, 3, 4):
            p = self.drill.hint("c999", i)
        self.assertEqual(self.owner(), ("?", 2))
        self.assertIn("rolled back before the next kubeadm task", p["notice"])
        self.assertIn("etcdctl", p["solution"])

    def test_reset_always_rolls_back_even_when_the_cluster_holds_the_setup(self):
        self.drill.open("c100")
        self.drill.check("c100")
        p = self.drill.reset("c100")
        self.assertEqual(self.cluster.klog.count("rollback"), 2)
        self.assertEqual(self.owner(), ("c100", 2))
        self.assertEqual((p["attempts"], p["last_output"]), (1, None))       # attempts kept, output cleared
        self.assertIn("Rolled the kubeadm cluster back", p["notice"])

    def test_a_failed_rollback_leaves_the_cluster_unknown_and_the_task_closed(self):
        self.cluster.fail["rollback"] = "rollback of VM 111 failed: ERROR"
        with self.assertRaises(RuntimeError) as cm:
            self.drill.open("c100")
        self.assertIn("could not roll the kubeadm cluster back: rollback of VM 111 failed", str(cm.exception))
        self.assertEqual(self.owner(), ("?", 1))                   # persisted before the rollback was attempted
        self.assertEqual(json.loads((Path(self.tmp.name) / "drill.json").read_text())["kubeadm_owner"], "?")
        self.assertNotIn("setup:questions/etcd-3", self.cluster.klog)
        with self.assertRaises(ValueError):
            self.drill.check("c100")
        self.assertEqual(self.drill.busy, set())

    def test_a_failed_setup_leaves_the_cluster_unknown(self):
        self.cluster.fail["setup"] = "boom"
        with self.assertRaises(RuntimeError):
            self.drill.open("c100")
        self.assertEqual(self.owner()[0], "?")
        self.assertFalse(self.drill._rec("c100")["deployed"])

    def test_owner_and_epoch_persist(self):
        self.drill.open("c100")
        again = make(self.tmp.name, self.cluster)
        self.assertEqual((again.drill.data["kubeadm_owner"], again.drill.data["kubeadm_epoch"]), ("c100", 1))
        self.assertEqual(again.drill._rec("c100")["kubeadm_epoch"], 1)
        again.drill.cluster.klog.clear()
        again.drill.open("c100")
        self.assertEqual(again.drill.cluster.klog, ["ensure_up"])
        del again.drill.data["tasks"]["c100"]["kubeadm_epoch"]
        with self.assertRaises(Conflict):
            again.drill.check("c100")

    def test_kind_tasks_never_touch_the_kubeadm_cluster(self):
        self.drill.open("c100")
        self.cluster.klog.clear()
        self.drill.open("t03")
        self.drill.check("t03")
        self.assertEqual(self.cluster.klog, [])
        self.assertEqual(self.owner(), ("c100", 1))

    def test_the_picker_view_says_which_tasks_are_kubeadm(self):
        tasks = {t["id"]: t for t in self.drill.state()["tasks"]}
        self.assertEqual((tasks["c100"]["cluster"], tasks["t03"]["cluster"]), ("kubeadm", None))

    def test_an_exam_start_waits_for_a_rollback_in_flight_and_is_refused_if_it_takes_too_long(self):
        release, inside = threading.Event(), threading.Event()
        seen = {}

        def slow():
            seen["busy"] = "c100" in self.drill.busy
            inside.set()
            release.wait(5)
        self.cluster.on_rollback = slow
        out = {}

        def opener():
            try:
                self.drill.open("c100")
            except Locked as e:
                out["locked"] = e
        th = threading.Thread(target=opener)
        th.start()
        self.assertTrue(inside.wait(5))
        self.exam.drain_timeout = 0.2
        with self.assertRaises(Conflict) as cm:
            self.exam.start("weighted")                            # the existing 409 path
        self.assertIn("kubeadm cluster reset is in progress", str(cm.exception))
        self.assertIsNone(self.exam.session)
        self.exam.drain_timeout = 5
        threading.Timer(0.3, release.set).start()
        t0 = time.monotonic()
        self.exam.start("weighted")                                # waits for the rollback to end, then goes ahead
        self.assertGreaterEqual(time.monotonic() - t0, 0.25)
        th.join(5)
        self.assertTrue(seen["busy"])
        self.assertIn("locked", out)                               # the open noticed the exam before applying its setup
        self.assertEqual(self.cluster.klog, ["rollback"])
        self.assertEqual(self.owner(), ("?", 1))                   # so the cluster is marked unknown, never half-owned

    def test_an_exam_start_marks_the_kubeadm_cluster_dirty_without_rolling_back(self):
        self.drill.open("c100")
        self.cluster.klog.clear()
        self.exam.start("weighted")
        self.assertEqual(self.cluster.klog, [])                    # no rollback now
        self.assertTrue(self.drill._rec("c100")["deployed"])
        self.assertEqual(self.owner(), ("?", 1))                   # but the cluster is unknown: the next open rolls back
        persisted = json.loads((Path(self.tmp.name) / "drill.json").read_text())
        self.assertEqual(persisted["kubeadm_owner"], "?")
        self.exam.end()
        with self.assertRaises(Conflict):
            self.drill.check("c100")
        self.drill.open("c100")
        self.assertEqual(self.cluster.klog.count("rollback"), 1)

    def test_an_exam_that_goes_live_during_the_rollback_stops_the_setup(self):
        self.cluster.on_rollback = lambda: setattr(self.exam, "starting", True)
        with self.assertRaises(Locked):
            self.drill.open("c100")
        self.exam.starting = False
        self.assertEqual(self.cluster.klog, ["rollback"])
        self.assertEqual(self.owner()[0], "?")
        self.assertEqual(self.drill.busy, set())

    def test_the_generation_is_taken_from_the_rollback_not_read_again(self):
        self.drill.open("c100")
        self.assertEqual(self.cluster.gen_reads, 0)                   # no second call after the rollback
        self.assertEqual(self.drill._rec("c100")["kubeadm_gen"], self.cluster.gen)
        self.drill.check("c100")
        self.assertEqual(self.cluster.gen_reads, 1)                   # a check compares once

    def test_a_failed_rollback_still_changes_the_generation_so_old_owners_are_stale(self):
        self.drill.open("c100")
        self.cluster.fail["rollback"] = "boom"
        with self.assertRaises(RuntimeError):
            self.drill.reset("c100")
        self.assertNotEqual(self.drill._rec("c100")["kubeadm_gen"], self.cluster.gen)     # the recorded state is stale
        self.assertEqual(self.owner()[0], "?")

    def test_a_rollback_by_someone_else_makes_the_owned_task_stale(self):
        self.drill.open("c100")
        self.cluster.klog.clear()
        self.cluster.gen += 1                                         # e2e or another caller rolled the VMs back
        with self.assertRaises(Conflict):
            self.drill.check("c100")
        self.assertEqual(self.cluster.klog, [])                       # validator not run
        self.drill.open("c100")                                       # open rebuilds instead of trusting the owner
        self.assertEqual(self.cluster.klog, ["rollback", "setup:questions/etcd-3"])
        self.assertEqual(self.drill._rec("c100")["kubeadm_gen"], self.cluster.gen)
        self.assertEqual(self.drill.check("c100")["verdict"], "failed")

    def test_the_generation_is_stored_with_the_owner_and_survives_a_restart(self):
        self.drill.open("c100")
        again = make(self.tmp.name, self.cluster)
        self.cluster.klog.clear()
        again.drill.open("c100")
        self.assertEqual(self.cluster.klog, ["ensure_up"])            # same generation: no rollback

    def test_a_solution_shown_during_the_build_leaves_the_cluster_unowned(self):
        def reveal():
            self.drill._rec("c100")["hints_revealed"] = 4             # what hint(4) does while the build runs
        self.cluster.on_rollback = reveal
        self.drill.open("c100")
        self.assertEqual(self.owner()[0], "?")
        with self.assertRaises(Conflict):
            self.drill.check("c100")


class LevelsKubeadm(unittest.TestCase):
    def run_fake(self, results):
        calls = []

        def fake(args, timeout=120, cwd=None, input=None, env=None):
            calls.append({"args": list(args), "timeout": timeout, "cwd": cwd, "input": input, "env": env})
            return SimpleNamespace(returncode=results.pop(0) if results else 0, stdout="out", stderr="err")
        return calls, fake

    def question_dir(self, tmp, name, files):
        d = Path(tmp) / name
        d.mkdir()
        for f, text in files.items():
            (d / f).write_text(text)

    def test_rollback_and_ensure_up_call_the_helper_through_sudo(self):
        calls = []

        def fake(args, **k):
            calls.append((list(args), k.get("timeout")))
            ok = len(calls) != 3
            return SimpleNamespace(returncode=0 if ok else 1, stdout="GENERATION=0123456789abcdef\n" if args[-1] == "rollback" else "", stderr="err")
        with mock.patch.object(levels, "run", fake):
            self.assertEqual(levels.kubeadm_rollback(), (True, "err", "0123456789abcdef"))
            self.assertEqual(levels.kubeadm_ensure_up(), (True, "err"))
            self.assertEqual(levels.kubeadm_ensure_up(), (False, "err"))
        self.assertEqual(calls[0][0], ["sudo", "-n", "/usr/local/sbin/cka-kubeadm", "rollback"])
        self.assertEqual(calls[1][0], ["sudo", "-n", "/usr/local/sbin/cka-kubeadm", "ensure-up"])
        self.assertGreaterEqual(calls[0][1], 420 + 420)                  # lock wait + run, so the server never gives up first

    def test_the_generation_comes_from_the_rollbacks_own_stdout(self):
        res = SimpleNamespace(returncode=0, stdout="noise\nGENERATION=aaaaaaaaaaaaaaaa\n", stderr="progress lines")
        with mock.patch.object(levels, "run", lambda *a, **k: res):
            self.assertEqual(levels.kubeadm_rollback(), (True, "progress lines", "aaaaaaaaaaaaaaaa"))
        res = SimpleNamespace(returncode=0, stdout="", stderr="progress")
        with mock.patch.object(levels, "run", lambda *a, **k: res):
            ok, msg, gen = levels.kubeadm_rollback()
        self.assertEqual((ok, gen), (False, None))
        res = SimpleNamespace(returncode=1, stdout="GENERATION=aaaaaaaaaaaaaaaa\n", stderr="failed")
        with mock.patch.object(levels, "run", lambda *a, **k: res):
            self.assertEqual(levels.kubeadm_rollback(), (False, "failed", None))

    def test_timeouts_on_this_side_exceed_what_the_helper_can_take(self):
        self.assertGreater(levels.KUBEADM_STEP_TIMEOUT, 420 + 420)
        self.assertGreater(levels.KUBEADM_SCRIPT_TIMEOUT, 60 + levels.RUN_ON_SECONDS)
        self.assertGreater(levels.KUBEADM_VALIDATE_TIMEOUT, 60 + 150)          # validate.sh asks run-on for 150 s
        self.assertEqual((ck.RUN_ON_LOCK_WAIT, ck.RUN_ON_TIMEOUT), (60, levels.RUN_ON_SECONDS))

    def test_setup_goes_to_controlplane_unless_the_first_line_names_node01(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(levels, "QUESTIONS", Path(tmp)):
            self.question_dir(tmp, "a", {"setup.sh": "#!/bin/bash\nrm -f /opt/x\n", "solution.sh": "echo sol\n"})
            self.question_dir(tmp, "b", {"setup.sh": "# node: node01\nrm -f /opt/y\n"})
            self.question_dir(tmp, "c", {"validate.sh": "exit 0\n"})
            calls, fake = self.run_fake([])
            with mock.patch.object(levels, "run", fake):
                self.assertEqual(levels.kubeadm_setup("questions/a")[0], True)
                levels.kubeadm_setup("questions/b")
                self.assertEqual(levels.kubeadm_solution("questions/a")[0], True)
                self.assertEqual(levels.kubeadm_setup("questions/c"), (True, ""))       # no setup.sh: nothing to run
            self.assertEqual([c["args"][-4:] for c in calls], [["run-on", "--timeout", "240", n] for n in ("controlplane", "node01", "controlplane")])
            self.assertEqual(calls[0]["input"], "{\n#!/bin/bash\nrm -f /opt/x\n}\n")     # one brace group, see _kubeadm_run_file
            self.assertEqual(calls[2]["input"], "{\necho sol\n}\n")

    def test_timeout_directive_sets_run_on_and_the_server_side_timeout(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(levels, "QUESTIONS", Path(tmp)):
            self.question_dir(tmp, "a", {"setup.sh": "#!/bin/bash\n# timeout: 800\napt-get update\n", "solution.sh": "# timeout: 500\ntrue\n"})
            self.question_dir(tmp, "b", {"setup.sh": "#!/bin/bash\n# node: node01\n# timeout: 700\ntrue\n"})
            self.question_dir(tmp, "c", {"setup.sh": "#!/bin/bash\ntrue\n# timeout: 800\ntrue\n"})   # the directive may sit on line 3
            self.question_dir(tmp, "d", {"setup.sh": "#!/bin/bash\n# timeout: 901\ntrue\n"})
            self.question_dir(tmp, "e", {"setup.sh": "#!/bin/bash\ntrue\ntrue\n# timeout: 800\n"})   # line 4: ignored
            calls, fake = self.run_fake([])
            with mock.patch.object(levels, "run", fake):
                self.assertTrue(levels.kubeadm_setup("questions/a")[0])
                self.assertTrue(levels.kubeadm_solution("questions/a")[0])
                self.assertTrue(levels.kubeadm_setup("questions/b")[0])
                self.assertTrue(levels.kubeadm_setup("questions/c")[0])
                ok, msg = levels.kubeadm_setup("questions/d")
                self.assertFalse(ok)
                self.assertIn("outside 1..900", msg)
                self.assertTrue(levels.kubeadm_setup("questions/e")[0])
            self.assertEqual([(c["args"][-3], c["args"][-2], c["timeout"]) for c in calls],
                             [("--timeout", "800", 890), ("--timeout", "500", 590), ("--timeout", "700", 790), ("--timeout", "800", 890), ("--timeout", "240", 330)])
            self.assertEqual([c["args"][-1] for c in calls], ["controlplane", "controlplane", "node01", "controlplane", "controlplane"])
        for secs in (1, 240, 900):
            self.assertGreater(secs + levels.KUBEADM_SCRIPT_MARGIN, ck.RUN_ON_LOCK_WAIT + secs)      # the helper waits its lock, then runs

    def test_node01_and_cka1_pieces_run_first_and_cka1_runs_on_k8s_lab_as_cka1(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(levels, "QUESTIONS", Path(tmp)):
            self.question_dir(tmp, "a", {"setup.sh": "main\n", "setup-node01.sh": "# node: node01\nn1\n", "setup-cka1.sh": "# node: cka1\nc1\n",
                                         "solution.sh": "# node: cka1\nsolo\n"})
            calls, fake = self.run_fake([])
            with mock.patch.object(levels, "run", fake):
                self.assertEqual(levels.kubeadm_setup("questions/a")[0], True)
                self.assertEqual(levels.kubeadm_solution("questions/a")[0], True)
            self.assertEqual([c["input"].split("\n")[-3] for c in calls], ["n1", "c1", "main", "solo"])
            self.assertEqual(calls[0]["args"][-1], "node01")
            self.assertEqual(calls[1]["args"], levels.CKA1_STEP)
            self.assertEqual(calls[1]["cwd"], "/")
            self.assertEqual(calls[3]["args"], levels.CKA1_STEP)        # the directive in solution.sh itself
            self.assertEqual(calls[2]["args"][-1], "controlplane")
            self.assertGreater(calls[1]["timeout"], levels.RUN_ON_SECONDS)
            # a failing piece stops the sequence
            calls, fake = self.run_fake([1])
            with mock.patch.object(levels, "run", fake):
                self.assertFalse(levels.kubeadm_setup("questions/a")[0])
            self.assertEqual(len(calls), 1)

    def test_validate_runs_bash_in_the_materialized_dir_without_the_kind_pin(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(levels, "QUESTIONS", Path(tmp)):
            self.question_dir(tmp, "a", {"validate.sh": "exit 0\n"})
            calls, fake = self.run_fake([0])
            with mock.patch.object(levels, "run", fake):
                ok, out = levels.kubeadm_validate("questions/a")
            self.assertTrue(ok)
            self.assertEqual(calls[0]["args"], ["bash", "validate.sh"])
            self.assertTrue(calls[0]["cwd"].endswith("questions/a"))
            self.assertNotIn("K8SQUEST_CONTEXT", calls[0]["env"] or {})

    def test_the_etcd_3_files_use_the_helper_only(self):
        d = levels.level_dir("questions/etcd-3")
        self.assertFalse((d / "broken.yaml").exists())
        for f in ("setup.sh", "validate.sh", "solution.sh", "hint-1.txt", "hint-2.txt", "hint-3.txt", "debrief.md"):
            self.assertTrue((d / f).read_text().strip(), f)
        self.assertIn("etcdutl snapshot status", (d / "validate.sh").read_text())
        self.assertIn("cka-kubeadm run-on --timeout 150 controlplane", (d / "validate.sh").read_text())
        self.assertEqual((d / "setup.sh").read_text().count("rm -f /opt/backup.db"), 1)
        self.assertIn("snapshot save /opt/backup.db", (d / "solution.sh").read_text())


class E2eKubeadm(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        before = os.environ.get("EXAM_ALLOW_UNPROVEN")
        import e2e
        cls.e2e = e2e
        if before is None:
            os.environ.pop("EXAM_ALLOW_UNPROVEN", None)
        else:
            os.environ["EXAM_ALLOW_UNPROVEN"] = before

    def prove(self, validations, **fail):
        log = []
        vals = list(validations)

        def step(name):
            def f(*a):
                log.append(name)
                return (False, "boom") if name in fail else (True, "")
            return f

        def validate(rel, *a, **k):
            log.append("validate")
            return vals.pop(0) if vals else vals_last, "out"
        vals_last = validations[-1]
        with mock.patch.object(levels, "kubeadm_rollback", step("rollback")), \
                mock.patch.object(levels, "kubeadm_setup", step("setup")), \
                mock.patch.object(levels, "kubeadm_solution", step("solution")), \
                mock.patch.object(levels, "kubeadm_validate", validate):
            return self.e2e.prove_kubeadm("questions/etcd-3", poll=0), log

    def test_ok_means_rollback_setup_fail_solution_pass_in_that_order(self):
        r, log = self.prove([False, True])
        self.assertEqual((r["verdict"], log), ("OK", ["rollback", "setup", "validate", "solution", "validate"]))

    def test_a_validator_that_passes_before_the_solution_is_flagged(self):
        r, log = self.prove([True])
        self.assertEqual((r["verdict"], log[-1]), ("BROKEN-ALREADY-PASSES", "validate"))

    def test_a_solution_that_does_not_pass_is_flagged(self):
        r, _ = self.prove([False, False])
        self.assertEqual(r["verdict"], "SOLUTION-DOES-NOT-PASS")

    def test_a_failed_rollback_or_setup_is_a_deploy_failure(self):
        self.assertEqual(self.prove([False], rollback=1)[0]["verdict"], "DEPLOY-FAIL")
        r, log = self.prove([False], setup=1)
        self.assertEqual((r["verdict"], log), ("DEPLOY-FAIL", ["rollback", "setup"]))

    def test_write_status_is_allowed_for_the_kubeadm_task_but_not_for_exam_kind(self):
        self.assertIsNone(self.e2e.check_args("drill", True, {"c100"}, False))
        self.assertIn("drill-only", self.e2e.check_args("exam", False, {"c100"}, False))


class HelperHardening(unittest.TestCase):
    def setUp(self):
        real = ck.ssl.create_default_context          # the CA file does not exist on the dev machine: load no CA, keep the rest
        p = mock.patch.object(ck.ssl, "create_default_context", lambda cafile=None: real())
        p.start()
        self.addCleanup(p.stop)

    def test_a_malformed_token_file_is_refused_without_echoing_it(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "tok"
            for body in ("PVEAPIToken=a!b=SECRET1\nSECRET2\n", "PVEAPIToken=a b=SECRET3", "SECRET4", "Bearer SECRET5"):
                f.write_text(body)
                with self.assertRaises(ck.Failure) as cm:
                    ck.read_token(str(f))
                self.assertEqual(str(cm.exception), "token file malformed")
            f.write_text("PVEAPIToken=a!b=ok\n")
            self.assertEqual(ck.read_token(str(f)), "PVEAPIToken=a!b=ok")

    def test_a_two_line_token_file_exits_1_with_no_token_text_in_the_output(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "tok"
            f.write_text("PVEAPIToken=a!b=TOPSECRET\nTOPSECRET2\n")
            w = FakeWorld()
            err, out = io.StringIO(), io.StringIO()
            real = ck.read_token
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out), mock.patch.object(ck, "read_token", lambda: real(str(f))):
                rc = ck.main(["rollback"], ca=w.ca, http=w.http, run=w.run, sleep=w.sleep, clock=w.clock, gen_path=w.gen, lock=w.lock)
            self.assertEqual(rc, 1)
            self.assertIn("token file malformed", err.getvalue())
            self.assertNotIn("TOPSECRET", err.getvalue() + out.getvalue())
            self.assertEqual(w.http_calls, [])

    def test_a_library_error_that_quotes_the_header_never_reaches_the_output(self):
        def boom(method, url, token):
            raise ValueError("Invalid header value %r" % token)
        w = FakeWorld()
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = ck.main(["ensure-up"], token=TOKEN, ca=w.ca, http=boom, run=w.run, sleep=w.sleep, clock=w.clock, gen_path=w.gen, lock=w.lock)
        self.assertEqual(rc, 1)
        self.assertIn("ValueError", err.getvalue())
        self.assertNotIn("SECRET", err.getvalue())
        with mock.patch.object(ck.urllib.request.OpenerDirector, "open", side_effect=ValueError("bad %s" % TOKEN)):
            with self.assertRaises(ck.Failure) as cm:
                ck.real_http("GET", "https://x/", TOKEN)
        self.assertEqual(str(cm.exception), "PVE request failed: ValueError")

    def test_urlerror_names_the_reason_type_and_os_or_tls_text(self):
        import urllib.error
        for reason, want in ((ck.ssl.SSLCertVerificationError("certificate verify failed"), "certificate verify failed"),
                             (ConnectionRefusedError(111, "Connection refused"), "ConnectionRefusedError"),
                             ("some text " + TOKEN, "str")):
            with mock.patch.object(ck.urllib.request.OpenerDirector, "open", side_effect=urllib.error.URLError(reason)):
                with self.assertRaises(ck.Failure) as cm:
                    ck.real_http("GET", "https://x/", TOKEN)
            self.assertIn(want, str(cm.exception))
            self.assertNotIn("SECRET", str(cm.exception))

    def test_the_opener_gets_the_verified_context_a_timeout_and_never_follows_redirects(self):
        seen = {}

        class FakeOpener:
            def open(self, req, timeout=None):
                seen["timeout"], seen["req"] = timeout, req
                raise ck.Failure("stop")

        def build(*handlers):
            seen["handlers"] = handlers
            return FakeOpener()
        with mock.patch.object(ck.urllib.request, "build_opener", build):
            with self.assertRaises(ck.Failure):
                ck.real_http("GET", "https://x/", TOKEN)
        https = next(h for h in seen["handlers"] if isinstance(h, ck.urllib.request.HTTPSHandler))
        self.assertEqual((https._context.verify_mode, https._context.check_hostname), (ck.ssl.CERT_REQUIRED, False))
        self.assertEqual(seen["timeout"], 30)
        nr = next(h for h in seen["handlers"] if isinstance(h, ck._NoRedirect))
        self.assertIsNone(nr.redirect_request(seen["req"], None, 302, "Found", {}, "https://evil.example/"))
        self.assertFalse(ck.ssl.VERIFY_X509_STRICT & https._context.verify_flags)

    def test_a_3xx_is_an_error_not_a_followed_redirect(self):
        w = FakeWorld(fail_http=(("GET", "current"), 302, "Found"))
        w.vm = {111: "running", 112: "running"}
        rc, _, err = w.main(["ensure-up"])
        self.assertEqual(rc, 1)
        self.assertIn("HTTP 302", err)

    def test_wait_task_accepts_warnings_and_logs_it(self):
        w = FakeWorld(task_exit="WARNINGS: 1")
        rc, _, err = w.main(["rollback"])
        self.assertEqual(rc, 0, err)
        self.assertIn("finished with warnings", err)

    def test_ssh_always_has_connect_and_keepalive_timeouts(self):
        for opt in ("BatchMode=yes", "ConnectTimeout=10", "ServerAliveInterval=15", "ServerAliveCountMax=4"):
            self.assertIn(opt, ck.SSH_OPTS)
        w = FakeWorld()
        w.main(["ensure-up"])
        for r in w.runs:
            if "ssh" in r["argv"]:
                self.assertEqual(r["argv"][6:6 + len(ck.SSH_OPTS)], ck.SSH_OPTS)

    def test_run_on_timeout_option(self):
        w = FakeWorld()
        w.main(["run-on", "--timeout", "30", "node01"], stdin="x")
        self.assertEqual((w.runs[0]["timeout"], w.locks), (30, [60]))
        for bad in (["run-on", "--timeout", "x", "node01"], ["run-on", "--timeout", "0", "node01"], ["run-on", "--timeout"]):
            self.assertEqual(w.main(bad)[0], 2, bad)

    def test_run_on_reports_its_own_timeout(self):
        w = FakeWorld()
        w.run = lambda argv, **kw: (124, "", "timed out after 240s")
        rc, _, err = w.main(["run-on", "node01"], stdin="x")
        self.assertEqual(rc, 124)
        self.assertIn("run-on node01 timed out after 240s", err)

    def test_generation_is_a_random_token_written_atomically(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "sub", "generation")
            self.assertEqual(ck.read_generation(p), "none")
            a, b = ck.new_generation(p), ck.new_generation(p)
            self.assertRegex(a, r"^[0-9a-f]{16}$")
            self.assertNotEqual(a, b)
            self.assertEqual(ck.read_generation(p), b)
            self.assertEqual(os.listdir(os.path.dirname(p)), ["generation"])        # no temp file left behind
            Path(p).write_text("junk")
            with self.assertRaises(ck.Failure):
                ck.read_generation(p)

    def test_the_generation_changes_at_the_start_of_a_rollback_attempt_even_when_it_fails(self):
        w = FakeWorld(task_exit="ERROR: x")
        self.assertEqual(w.main(["generation"])[1].strip(), "none")
        self.assertEqual(w.main(["rollback"])[0], 1)
        g1 = w.main(["generation"])[1].strip()
        self.assertRegex(g1, r"^[0-9a-f]{16}$")
        w2 = FakeWorld(fail_http=(("GET", "resources"), 500, "boom"))            # fails on the very first Proxmox call
        w2.main(["rollback"])
        self.assertRegex(w2.main(["generation"])[1].strip(), r"^[0-9a-f]{16}$")

    def test_the_lock_serialises_and_a_second_caller_gives_up_after_the_timeout(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "lock")
            clock = FakeWorld()
            with ck.real_lock(5, clock.clock, clock.sleep, path):
                with self.assertRaises(ck.Failure) as cm:
                    with ck.real_lock(5, clock.clock, clock.sleep, path):
                        self.fail("entered a held lock")
                self.assertIn("gave up after 5s", str(cm.exception))
                self.assertGreaterEqual(clock.now, 5)
            with ck.real_lock(5, clock.clock, clock.sleep, path):             # free again once released
                pass

    def test_ensure_up_and_rollback_take_the_lock(self):
        w = FakeWorld()
        w.main(["ensure-up"])
        w.main(["rollback"])
        self.assertEqual(w.locks, [420, 420])


class LevelsHardening(unittest.TestCase):
    def test_helper_messages_are_redacted_before_they_can_reach_the_browser(self):
        res = SimpleNamespace(returncode=1, stdout="", stderr="boom PVEAPIToken=u@pve!id=SECRET123 trailing")
        with mock.patch.object(levels, "run", lambda *a, **k: res):
            ok, msg, _ = levels.kubeadm_rollback()
        self.assertFalse(ok)
        self.assertNotIn("SECRET123", msg)
        self.assertIn("<redacted>", msg)

    def test_generation_is_read_from_the_helper(self):
        calls = []

        def fake(args, **k):
            calls.append(args)
            return SimpleNamespace(returncode=0, stdout="0123456789abcdef\n", stderr="")
        with mock.patch.object(levels, "run", fake):
            self.assertEqual(levels.kubeadm_generation(), "0123456789abcdef")
        self.assertEqual(calls[0], ["sudo", "-n", "/usr/local/sbin/cka-kubeadm", "generation"])
        with mock.patch.object(levels, "run", lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="no")):
            with self.assertRaises(RuntimeError):
                levels.kubeadm_generation()

    def test_node_directive_on_line_two_after_a_shebang_and_empty_scripts(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(levels, "QUESTIONS", Path(tmp)):
            for name, text in (("a", "#!/bin/bash\n# node: node01\necho x\n"), ("b", "echo\n# node: node01\n"), ("c", "  \n"),
                               ("d", "#!/bin/bash"), ("e", "# node: node01")):
                d = Path(tmp) / name
                d.mkdir()
                (d / "setup.sh").write_text(text)
            calls = []

            def fake(args, **k):
                calls.append(args[-1])
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            with mock.patch.object(levels, "run", fake):
                self.assertTrue(levels.kubeadm_setup("questions/a")[0])
                self.assertTrue(levels.kubeadm_setup("questions/b")[0])
                self.assertEqual(levels.kubeadm_setup("questions/c"), (False, "setup.sh is empty"))
                self.assertTrue(levels.kubeadm_setup("questions/d")[0])         # a shebang and no newline: no line 2
                self.assertTrue(levels.kubeadm_setup("questions/e")[0])
            self.assertEqual(calls, ["node01", "controlplane", "controlplane", "node01"])

    def test_validate_runs_with_an_empty_kubeconfig(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(levels, "QUESTIONS", Path(tmp)):
            (Path(tmp) / "a").mkdir()
            (Path(tmp) / "a" / "validate.sh").write_text("exit 0\n")
            seen = {}

            def fake(args, **k):
                seen.update(k)
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            with mock.patch.object(levels, "run", fake):
                levels.kubeadm_validate("questions/a")
        self.assertEqual(seen["env"]["KUBECONFIG"], "/dev/null")

    def test_etcd_3_validator_demands_a_numeric_totalkey_and_a_save_file_size(self):
        v = (levels.level_dir("questions/etcd-3") / "validate.sh").read_text()
        self.assertIn("SZ % 512", v)
        self.assertIn("not an etcdctl snapshot save file", v)
        self.assertIn("TOTALKEY=\\([0-9][0-9]*\\)", v)
        self.assertIn("[ ! -L", v)


if __name__ == "__main__":
    unittest.main()
