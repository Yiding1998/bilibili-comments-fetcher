import tempfile
import unittest
from pathlib import Path

from bili_stats.checkpoint import Repository
from bili_stats.models import Comment, Danmaku


class RepositoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Repository(Path(self.tmp.name) / "state.sqlite3")
        self.repo.initialize()
        self.repo.upsert_work("video:BV1", "video", "demo")
        self.repo.upsert_episode("video:BV1", "cid:10", 1, "P1", "BV1", 1, 10, None)

    def tearDown(self):
        self.repo.close()
        self.tmp.cleanup()

    def test_replaying_segment_deduplicates_and_advances(self):
        item = Danmaku("100", "cid:10", "same", 1000, 1, 25, 0xFFFFFF, "hash", 1)
        self.repo.commit_danmaku_segment("cid:10", 1, [item], False)
        self.repo.commit_danmaku_segment("cid:10", 1, [item], False)
        self.assertEqual(self.repo.count_danmaku("cid:10"), 1)
        self.assertEqual(self.repo.get_danmaku_next_segment("cid:10"), 2)

    def test_comments_deduplicate_by_rpid(self):
        item = Comment("200", "video:BV1", 1, "42", "user", "text")
        self.repo.commit_comment_page("video:BV1", 1, [item], "next", False)
        self.repo.commit_comment_page("video:BV1", 1, [item], "", True)
        self.assertEqual(self.repo.count_comments("video:BV1"), 1)
        self.assertTrue(self.repo.get_comment_progress("video:BV1", 1)["complete"])

    def test_restart_deletes_only_target_work(self):
        self.repo.upsert_work("video:BV2", "video", "other")
        self.repo.restart_work("video:BV1")
        self.assertIsNone(self.repo.get_work("video:BV1"))
        self.assertIsNotNone(self.repo.get_work("video:BV2"))

