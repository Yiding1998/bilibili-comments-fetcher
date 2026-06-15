import unittest

from bili_stats.client import AdaptiveLimiter, encode_wbi


class ClientTest(unittest.TestCase):
    def test_wbi_is_deterministic_and_does_not_mutate(self):
        original = {"foo": "a!'()*b", "bar": 2}
        signed = encode_wbi(
            original,
            "7cd084941338484aae1ad9425b84077c",
            "4932caff0ff746eab6f01bf08b70ac45",
            1700000000,
        )
        self.assertEqual(original, {"foo": "a!'()*b", "bar": 2})
        self.assertEqual(signed["foo"], "ab")
        self.assertEqual(signed["wts"], 1700000000)
        self.assertRegex(signed["w_rid"], r"^[0-9a-f]{32}$")

    def test_limiter_reduces_and_recovers_concurrency(self):
        limiter = AdaptiveLimiter(initial_concurrency=6, max_concurrency=8, recovery_successes=3)
        limiter.record_throttle()
        self.assertEqual(limiter.concurrency, 3)
        for _ in range(3):
            limiter.record_success()
        self.assertEqual(limiter.concurrency, 4)


if __name__ == "__main__":
    unittest.main()
