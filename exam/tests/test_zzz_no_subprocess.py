"""Runs last: the unit suite must not have started a real subprocess (no kubectl, no ssh, no bash)."""
import subprocess
import unittest

import tests._path as guard


class NoSubprocess(unittest.TestCase):
    def test_1_nothing_was_started_by_the_suite(self):
        self.assertEqual(guard.SUBPROCESS_CALLS, [])

    def test_2_the_guard_itself_refuses_and_records(self):
        with self.assertRaises(AssertionError):
            subprocess.run(["kubectl", "delete", "namespace", "exam-t01"])
        with self.assertRaises(AssertionError):
            subprocess.Popen(["true"])
        self.assertEqual(len(guard.SUBPROCESS_CALLS), 2)
        guard.SUBPROCESS_CALLS.clear()


if __name__ == "__main__":
    unittest.main()
