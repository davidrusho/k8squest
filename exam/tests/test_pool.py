import json
import tempfile
import unittest
from pathlib import Path

import tests._path  # noqa: F401
import pool


class StatusFile(unittest.TestCase):
    def test_missing_file_fails_closed_with_a_clear_error(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(RuntimeError) as cm:
                pool.load_status(Path(d) / "nope.json")
        self.assertIn("e2e.py --write-status", str(cm.exception))

    def test_corrupt_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "s.json"
            for bad in ("{not json", "[]", '"x"', ""):
                f.write_text(bad)
                with self.assertRaises(RuntimeError, msg=bad):
                    pool.load_status(f)

    def test_only_tasks_with_an_ok_verdict_are_admitted(self):
        tasks = pool.ALL_TASKS[:4]
        status = {tasks[0]["id"]: {"verdict": "OK"}, tasks[1]["id"]: {"verdict": "SOLUTION-DOES-NOT-PASS"},
                  tasks[2]["id"]: "OK"}                         # tasks[3] has no entry at all
        self.assertEqual([t["id"] for t in pool.select_pool(status, tasks)], [tasks[0]["id"]])

    def test_the_shipped_status_proves_every_task(self):
        status = pool.load_status()
        self.assertEqual({t["id"] for t in pool.select_pool(status)}, {t["id"] for t in pool.ALL_TASKS})


if __name__ == "__main__":
    unittest.main()
