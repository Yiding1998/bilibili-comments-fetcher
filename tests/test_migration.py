import sqlite3
import tempfile
import unittest
from pathlib import Path

from bili_stats.checkpoint import Repository
from bili_stats.migration import migrate_legacy_database
from bili_stats.models import Comment, Danmaku


class MigrationTest(unittest.TestCase):
    def seed(self, path):
        repo = Repository(path)
        repo.initialize()
        for number in (1, 2):
            work_key = "video:BV{}".format(number)
            episode_key = "cid:{}".format(number)
            repo.upsert_work(work_key, "video", "Video {}".format(number))
            repo.upsert_episode(work_key, episode_key, 1, "P1", "BV{}".format(number), number, number, None)
            repo.commit_danmaku_segment(
                episode_key,
                1,
                [Danmaku(str(number), episode_key, "dm{}".format(number), 1, 0, 25, 1, "h{}".format(number), 0)],
                True,
            )
            repo.commit_comment_page(
                work_key,
                number,
                [Comment(str(number), work_key, number, str(number), "u", "c")],
                "",
                True,
            )
        repo.close()

    def test_migrates_each_work_and_deletes_legacy_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "Results"
            legacy = root / "bilibili_stats.sqlite3"
            self.seed(legacy)
            paths = migrate_legacy_database(root)
            self.assertFalse(legacy.exists())
            self.assertEqual(set(path.parent.name for path in paths), {"Video 1", "Video 2"})
            for number in (1, 2):
                connection = sqlite3.connect(str(root / "Video {}".format(number) / "bilibili_stats.sqlite3"))
                self.assertEqual(connection.execute("SELECT count(*) FROM works").fetchone()[0], 1)
                self.assertEqual(connection.execute("SELECT count(*) FROM danmaku").fetchone()[0], 1)
                self.assertEqual(connection.execute("SELECT count(*) FROM comments").fetchone()[0], 1)
                connection.close()

    def test_migration_is_idempotent_when_targets_already_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "Results"
            legacy = root / "bilibili_stats.sqlite3"
            self.seed(legacy)
            target = root / "Video 1" / "bilibili_stats.sqlite3"
            target.parent.mkdir(parents=True)
            first = Repository(target)
            first.initialize()
            first.close()
            migrate_legacy_database(root)
            connection = sqlite3.connect(str(target))
            self.assertEqual(connection.execute("SELECT count(*) FROM danmaku").fetchone()[0], 1)
            connection.close()

    def test_failure_preserves_legacy_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "Results"
            legacy = root / "bilibili_stats.sqlite3"
            self.seed(legacy)
            with self.assertRaises(RuntimeError):
                migrate_legacy_database(root, verify=lambda *_: False)
            self.assertTrue(legacy.exists())


if __name__ == "__main__":
    unittest.main()
