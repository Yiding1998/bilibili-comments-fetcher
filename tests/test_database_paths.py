import sqlite3
import tempfile
import unittest
from pathlib import Path

from bili_stats.database_paths import (
    DatabaseNotFound,
    MultipleDatabasesFound,
    discover_work_database,
    resolve_database_path,
    work_database_path,
)


def make_database(path, work_key):
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path))
    connection.execute("CREATE TABLE works(work_key TEXT PRIMARY KEY)")
    connection.execute("INSERT INTO works VALUES(?)", (work_key,))
    connection.commit()
    connection.close()


class DatabasePathTest(unittest.TestCase):
    def test_work_database_uses_sanitized_title(self):
        self.assertEqual(
            work_database_path(Path("Results"), 'a/b:*?"<>|'),
            Path("Results/a_b_______/bilibili_stats.sqlite3"),
        )

    def test_explicit_path_wins(self):
        self.assertEqual(
            resolve_database_path(Path("custom.sqlite3"), Path("Results"), "Title"),
            Path("custom.sqlite3"),
        )

    def test_discovery_finds_unique_matching_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wanted = root / "A" / "bilibili_stats.sqlite3"
            make_database(wanted, "video:BV1")
            make_database(root / "B" / "bilibili_stats.sqlite3", "video:BV2")
            self.assertEqual(discover_work_database(root, "video:BV1"), wanted)

    def test_discovery_reports_missing_and_duplicate_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(DatabaseNotFound):
                discover_work_database(root, "video:BV1")
            make_database(root / "A" / "bilibili_stats.sqlite3", "video:BV1")
            make_database(root / "B" / "bilibili_stats.sqlite3", "video:BV1")
            with self.assertRaises(MultipleDatabasesFound):
                discover_work_database(root, "video:BV1")


if __name__ == "__main__":
    unittest.main()
