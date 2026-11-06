import random
import unittest

import tests._path  # noqa: F401
from selection import DOMAIN_WEIGHTS, SESSION_SIZE, allocate, select_session

D = list(DOMAIN_WEIGHTS)


def fake_pool(per_domain):
    pool = []
    for d, n in zip(D, per_domain):
        pool += [{"id": f"{d[:3]}{i}", "domain": d} for i in range(n)]
    return pool


def by_domain(tasks):
    out = {d: 0 for d in D}
    for t in tasks:
        out[t["domain"]] += 1
    return out


class Weighted(unittest.TestCase):
    def test_sixteen_split_follows_weights(self):
        got = allocate({d: 99 for d in D}, 16)
        self.assertEqual(sum(got.values()), 16)
        self.assertEqual(list(got.values()), [2, 2, 3, 5, 4])   # 10/15/20/30/25 % of 16

    def test_capped_domain_gives_its_slots_away(self):
        got = allocate({D[0]: 99, D[1]: 99, D[2]: 99, D[3]: 99, D[4]: 1}, 16)
        self.assertEqual(got[D[4]], 1)
        self.assertEqual(sum(got.values()), 16)
        self.assertGreater(got[D[3]], got[D[2]])    # weights still order the rest

    def test_session_has_sixteen_distinct_tasks(self):
        pool = fake_pool([8, 17, 9, 11, 2])
        s = select_session(pool, rng=random.Random(1))
        self.assertEqual(len(s), SESSION_SIZE)
        self.assertEqual(len({t["id"] for t in s}), SESSION_SIZE)
        # Cluster Architecture has only 2 tasks; the other 14 slots are split 10:15:20:30
        self.assertEqual(by_domain(s), {D[0]: 2, D[1]: 3, D[2]: 4, D[3]: 5, D[4]: 2})

    def test_small_pool_returns_everything(self):
        pool = fake_pool([1, 1, 1, 1, 1])
        self.assertEqual(len(select_session(pool, rng=random.Random(0))), 5)


class MissedFirst(unittest.TestCase):
    def test_never_counted_tasks_come_first(self):
        pool = fake_pool([8, 17, 9, 11, 2])
        counted = {t["id"] for t in pool if int(t["id"][3:]) % 2 == 0}      # half counted
        missed = {t["id"] for t in pool} - counted
        self.assertGreaterEqual(len(missed), SESSION_SIZE)
        s = select_session(pool, counted, mode="missed", rng=random.Random(3))
        self.assertEqual(len(s), SESSION_SIZE)
        self.assertTrue(all(t["id"] in missed for t in s))

    def test_fills_from_counted_only_when_missed_runs_out(self):
        pool = fake_pool([8, 17, 9, 11, 2])
        missed = {pool[0]["id"], pool[1]["id"], pool[20]["id"]}
        counted = {t["id"] for t in pool} - missed
        s = select_session(pool, counted, mode="missed", rng=random.Random(4))
        ids = {t["id"] for t in s}
        self.assertEqual(len(s), SESSION_SIZE)
        self.assertTrue(missed <= ids)

    def test_weighted_mode_ignores_counted(self):
        pool = fake_pool([8, 17, 9, 11, 2])
        counted = {t["id"] for t in pool}
        self.assertEqual(len(select_session(pool, counted, mode="weighted", rng=random.Random(5))), SESSION_SIZE)


if __name__ == "__main__":
    unittest.main()
