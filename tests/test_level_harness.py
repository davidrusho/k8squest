#!/usr/bin/env python3
"""Tests for the wrong-fix-*.sh / alt-fix-*.sh support in tests/level_harness.py.

No cluster is needed: reset(), validate() and the script run are replaced by stubs, and the
clock is fake, so the polling loops finish instantly.

Run: python3 tests/test_level_harness.py   (or python3 -m unittest tests.test_level_harness)
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent
sys.path.insert(0, str(TESTS))
import level_harness as h  # noqa: E402


class FakeClock:
    """time.time()/time.sleep() that advance together, so deadlines pass without waiting."""
    def __init__(self):
        self.t = 1000.0

    def time(self):
        return self.t

    def sleep(self, n):
        self.t += n


def completed(rc=0, out=""):
    return subprocess.CompletedProcess([], rc, out, "")


class VariantDiscovery(unittest.TestCase):
    def test_finds_both_kinds_sorted_and_ignores_others(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            for name in ("wrong-fix-b.sh", "wrong-fix-a.sh", "alt-fix-x.sh", "solution.sh",
                         "validate.sh", "wrong-fix-notes.txt", "my-wrong-fix-a.sh"):
                (d / name).write_text("# x\n")
            got = [(k, p.name) for k, p in h.variant_scripts(d)]
            self.assertEqual(got, [("wrong-fix", "wrong-fix-a.sh"), ("wrong-fix", "wrong-fix-b.sh"),
                                   ("alt-fix", "alt-fix-x.sh")])

    def test_level_without_variants(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(h.variant_scripts(Path(d)), [])

    def test_shipped_scripts_are_well_formed(self):
        """Every wrong-fix/alt-fix in the tree parses, is executable, and names what it
        represents in a comment on the line after the shebang."""
        scripts = [p for k in h.VARIANT_KINDS for p in ROOT.glob(f"worlds/*/level-*/{k}-*.sh")]
        self.assertTrue(scripts, "positive control: the tree has at least one variant script")
        for p in scripts:
            lines = p.read_text().splitlines()
            self.assertEqual(lines[0], "#!/bin/bash", p)
            self.assertTrue(lines[1].startswith("# ") and len(lines[1]) > 12, f"{p}: line 2 must describe the bypass")
            self.assertTrue(p.stat().st_mode & 0o111, f"{p} is not executable")
            self.assertEqual(subprocess.run(["bash", "-n", str(p)]).returncode, 0, p)


class RunVariant(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.level = SimpleNamespace(name="level-x", path=Path("/nonexistent/level-x"))
        self.patches = [
            mock.patch.object(h, "time", self.clock),
            mock.patch.object(h, "reset", return_value=(True, "")),
            mock.patch.object(h, "level_env", return_value={}),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def run_variant(self, kind, script_rc, validate_results):
        """validate_results: list of exit codes handed out per validate() call, the last one repeating."""
        calls = []

        def fake_validate(_):
            calls.append(self.clock.t)
            return completed(validate_results[min(len(calls), len(validate_results)) - 1])

        with mock.patch.object(h, "run", return_value=completed(script_rc)), \
             mock.patch.object(h, "validate", side_effect=fake_validate):
            res, note, _ = h.run_variant(self.level, kind, Path(f"{kind}-demo.sh"))
        return res, note, calls

    def test_wrong_fix_rejected_for_the_whole_wait_is_ok(self):
        res, _, calls = self.run_variant("wrong-fix", 0, [1])
        self.assertEqual(res, "ok")
        self.assertGreater(calls[-1] - 1000.0, h.WRONG_FIX_WAIT)   # polled past the wait, not once

    def test_wrong_fix_that_passes_is_a_failure(self):
        res, _, _ = self.run_variant("wrong-fix", 0, [0])
        self.assertEqual(res, "FAIL(passes wrong fix)")

    def test_slow_converging_wrong_fix_is_caught(self):
        res, _, calls = self.run_variant("wrong-fix", 0, [1, 1, 1, 1, 0])
        self.assertEqual(res, "FAIL(passes wrong fix)")
        self.assertEqual(len(calls), 5)

    def test_validate_that_errors_is_not_a_rejection(self):
        for rc in (2, 124, 127):
            res, note, calls = self.run_variant("wrong-fix", 0, [rc])
            self.assertEqual(res, "ERR", rc)
            self.assertIn(f"exited {rc}", note)
            self.assertEqual(len(calls), 1, "stops at the first errored validate")

    def test_validate_that_errors_after_rejecting_is_err(self):
        res, _, _ = self.run_variant("wrong-fix", 0, [1, 1, 127])
        self.assertEqual(res, "ERR")

    def test_validate_that_rejects_with_exit_1_is_ok(self):
        res, _, _ = self.run_variant("wrong-fix", 0, [1, 1, 1])
        self.assertEqual(res, "ok")

    def test_alt_fix_that_passes_is_ok(self):
        res, _, _ = self.run_variant("alt-fix", 0, [1, 1, 0])
        self.assertEqual(res, "ok")

    def test_alt_fix_that_never_passes_fails(self):
        res, _, calls = self.run_variant("alt-fix", 0, [1])
        self.assertEqual(res, "FAIL")
        self.assertGreater(calls[-1] - 1000.0, h.FIX_TIMEOUT)

    def test_script_error_is_not_a_pass(self):
        for kind in h.VARIANT_KINDS:
            res, note, calls = self.run_variant(kind, 3, [1])
            self.assertEqual(res, "ERR", kind)
            self.assertIn("rc=3", note)
            self.assertEqual(calls, [], "validate must not run after a script that failed")

    def test_reset_failure_is_reported(self):
        with mock.patch.object(h, "reset", return_value=(False, "ns apply: boom")):
            res, note, _ = h.run_variant(self.level, "wrong-fix", Path("wrong-fix-demo.sh"))
        self.assertEqual((res, note), ("ERR", "ns apply: boom"))


if __name__ == "__main__":
    unittest.main()
