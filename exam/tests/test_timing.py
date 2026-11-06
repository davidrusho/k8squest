import unittest

import tests._path  # noqa: F401
from timing import BUDGET_SECONDS, GRACE_SECONDS, SessionClocks, TaskClock, in_time


class Budget(unittest.TestCase):
    def test_budget_is_120_minutes_over_16_tasks(self):
        self.assertEqual(BUDGET_SECONDS, 450.0)

    def test_pass_at_449_counts_at_451_does_not(self):
        self.assertTrue(in_time(449))
        self.assertTrue(in_time(450))
        self.assertFalse(in_time(451))


class Clocks(unittest.TestCase):
    def beat_through(self, c, start, end, step=10):
        t = start
        while t < end:
            t = min(end, t + step)
            c.beat(t)

    def test_single_visit_elapsed(self):
        c = TaskClock()
        c.start(1000.0)
        self.beat_through(c, 1000.0, 1449.0)
        self.assertEqual(c.elapsed(1449.0), 449.0)
        self.assertTrue(in_time(c.elapsed(1449.0)))

    def test_single_visit_over_time(self):
        c = TaskClock()
        c.start(1000.0)
        self.beat_through(c, 1000.0, 1451.0)
        self.assertEqual(c.elapsed(1451.0), 451.0)
        self.assertFalse(in_time(c.elapsed(1451.0)))

    def test_time_accumulates_across_two_visits(self):
        s = SessionClocks()
        s.show("a", 0.0)
        s.clock("a").beat(20.0)
        s.show("b", 200.0)             # leave a after 200 s... but only 20 s + grace were heard
        s.clock("b").beat(210.0)
        s.show("a", 300.0)             # second visit to a
        for t in range(310, 620, 10):
            s.beat("a", float(t))
        a = s.elapsed("a", 619.0)
        # first visit: heartbeat at 20 + grace 30 caps it at 50 s; second visit: 300 -> 619
        self.assertEqual(a, GRACE_SECONDS + 20.0 + (619.0 - 300.0))

    def test_two_visits_with_steady_heartbeats_sum_exactly(self):
        s = SessionClocks()
        s.show("a", 0.0)
        for t in range(10, 250, 10):
            s.beat("a", float(t))
        s.hide(240.0)                  # 240 s on the first visit
        s.show("a", 1000.0)
        for t in range(1010, 1220, 10):
            s.beat("a", float(t))
        self.assertEqual(s.elapsed("a", 1210.0), 240.0 + 210.0)
        self.assertFalse(in_time(s.elapsed("a", 1211.0) + 1))   # 451 s -> over

    def test_only_the_shown_task_runs(self):
        s = SessionClocks()
        s.show("a", 0.0)
        s.beat("a", 10.0)
        s.show("b", 10.0)
        s.beat("b", 20.0)
        self.assertFalse(s.clock("a").running)
        self.assertEqual(s.elapsed("a", 500.0), 10.0)
        self.assertEqual(s.elapsed("b", 20.0), 10.0)

    def test_silent_ui_stops_charging(self):
        c = TaskClock()
        c.start(0.0)
        c.beat(10.0)
        self.assertEqual(c.elapsed(10_000.0), 10.0 + GRACE_SECONDS)

    def test_hidden_page_does_not_run(self):
        s = SessionClocks()
        s.show("a", 0.0)
        s.beat("a", 5.0)
        s.hide(5.0)
        self.assertEqual(s.elapsed("a", 9999.0), 5.0)


class GapCharging(unittest.TestCase):
    def beat_through(self, c, start, end, step=10):
        t = start
        while t < end:
            t = min(end, t + step)
            c.beat(t)

    def test_beat_after_long_silence_charges_only_the_grace(self):
        c = TaskClock()
        c.start(0.0)
        self.beat_through(c, 0.0, 100.0)
        c.beat(7200.0)                      # laptop slept for two hours
        self.assertEqual(c.elapsed(7200.0), 100.0 + GRACE_SECONDS)

    def test_start_after_long_silence_charges_only_the_grace(self):
        c = TaskClock()
        c.start(0.0)
        self.beat_through(c, 0.0, 100.0)
        c.start(7200.0)                     # show event after the gap, clock never stopped
        self.assertEqual(c.elapsed(7200.0), 100.0 + GRACE_SECONDS)

    def test_clock_keeps_counting_after_the_gap(self):
        c = TaskClock()
        c.start(0.0)
        self.beat_through(c, 0.0, 100.0)
        c.beat(7200.0)
        self.beat_through(c, 7200.0, 7260.0)
        self.assertEqual(c.elapsed(7260.0), 100.0 + GRACE_SECONDS + 60.0)

    def test_hide_for_another_task_does_not_stop_the_shown_one(self):
        s = SessionClocks()
        s.show("a", 0.0)
        s.hide(5.0, "b")
        self.assertTrue(s.clock("a").running)

    def test_stopped_clock_resumes_on_beat_unless_hidden(self):
        s = SessionClocks()
        s.show("a", 0.0)
        s.beat("a", 10.0)
        s.clock("a").stop(10.0)             # what a server restart does
        s.beat("a", 20.0)
        self.assertTrue(s.clock("a").running)
        s.hide(25.0)
        s.beat("a", 26.0)                   # late beat after an explicit hide
        self.assertFalse(s.clock("a").running)


if __name__ == "__main__":
    unittest.main()
