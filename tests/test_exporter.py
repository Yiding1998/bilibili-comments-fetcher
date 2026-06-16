import tempfile
import unittest
from pathlib import Path

import pandas as pd

from bili_stats.checkpoint import Repository
from bili_stats.exporter import (
    EXCEL_CELL_LIMIT,
    build_comment_user_rows,
    build_danmaku_user_rows,
    build_video_info_rows,
    export,
)
from bili_stats.models import Comment, Danmaku


class RecordingTask:
    def __init__(self, description, total, unit):
        self.description = description
        self.total = total
        self.unit = unit
        self.current = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def update(self, amount=1, **postfix):
        self.current += amount


class RecordingReporter:
    def __init__(self):
        self.tasks = []

    def task(self, description, total=None, initial=0, unit="项"):
        task = RecordingTask(description, total, unit)
        task.current = initial
        self.tasks.append(task)
        return task


class AggregationTest(unittest.TestCase):
    def test_danmaku_users_sort_and_keep_duplicate_content(self):
        rows = [
            {"sender_hash": "b", "content": "one"},
            {"sender_hash": "a", "content": "same"},
            {"sender_hash": "a", "content": "same"},
            {"sender_hash": "", "content": "unknown"},
        ]
        result = build_danmaku_user_rows(rows)
        self.assertEqual([row["发送者标识"] for row in result], ["a", "(未知)", "b"])
        self.assertEqual(result[0]["弹幕次数"], 2)
        self.assertEqual(result[0]["弹幕内容"], "same\nsame")

    def test_video_info_prefers_source_metadata_and_falls_back_to_local_counts(self):
        work = {
            "title": "Demo",
            "source_json": (
                "{\"bvid\":\"BV1\",\"aid\":1,\"desc\":\"intro\","
                "\"owner\":{\"mid\":42,\"name\":\"UP\"},"
                "\"stat\":{\"view\":100,\"like\":20,\"coin\":3,\"favorite\":4,"
                "\"share\":5,\"danmaku\":6,\"reply\":7}}"
            ),
        }

        result = build_video_info_rows(work, [{"aid": 1, "bvid": "BV1"}], [{}], [{}, {}])

        self.assertEqual(result[0]["视频标题"], "Demo")
        self.assertEqual(result[0]["作者名称"], "UP")
        self.assertEqual(result[0]["播放量"], 100)
        self.assertEqual(result[0]["点赞数"], 20)
        self.assertEqual(result[0]["弹幕数"], 6)
        self.assertEqual(result[0]["评论数"], 7)
        self.assertEqual(result[0]["视频简介"], "intro")

    def test_comment_users_group_by_mid_and_use_latest_name(self):
        rows = [
            {"user_mid": "42", "user_name": "old", "content": "first", "ctime": 1},
            {"user_mid": "7", "user_name": "seven", "content": "only", "ctime": 3},
            {"user_mid": "42", "user_name": "new", "content": "second", "ctime": 2},
            {"user_mid": "", "user_name": "guest", "content": "anon", "ctime": 4},
        ]
        result = build_comment_user_rows(rows)
        self.assertEqual(result[0]["用户MID"], "42")
        self.assertEqual(result[0]["用户名"], "new")
        self.assertEqual(result[0]["评论内容"], "first\nsecond")
        self.assertEqual(result[0]["评论次数"], 2)

    def test_long_content_is_truncated_to_excel_limit(self):
        result = build_danmaku_user_rows([{"sender_hash": "a", "content": "x" * 40000}])
        self.assertLessEqual(len(result[0]["弹幕内容"]), EXCEL_CELL_LIMIT)
        self.assertTrue(result[0]["弹幕内容"].endswith("...[内容已截断]"))


class ExportIntegrationTest(unittest.TestCase):
    def test_export_creates_user_activity_workbooks(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Repository(Path(tmp) / "state.sqlite3")
            repo.initialize()
            repo.upsert_work("video:BV1", "video", "Demo")
            repo.upsert_episode("video:BV1", "cid:10", 1, "P1", "BV1", 1, 10, None)
            repo.commit_danmaku_segment(
                "cid:10",
                1,
                [Danmaku("1", "cid:10", "hello", 1, 0, 25, 0xFFFFFF, "hash", 0)],
                True,
            )
            repo.commit_comment_page(
                "video:BV1",
                1,
                [Comment("2", "video:BV1", 1, "42", "user", "before\x00after")],
                "",
                True,
            )
            output = export(repo, "video:BV1", Path(tmp) / "Results")
            expected = [
                output / "01-P1" / "弹幕用户排行.xlsx",
                output / "全局弹幕用户排行.xlsx",
                output / "评论用户排行.xlsx",
            ]
            for path in expected:
                self.assertTrue(path.exists(), str(path))
            ranking = pd.read_excel(expected[1])
            self.assertEqual(ranking.loc[0, "发送者标识"], "hash")
            self.assertEqual(ranking.loc[0, "发送者哈希"], "hash")
            comments = pd.read_excel(output / "评论用户排行.xlsx")
            self.assertEqual(comments.loc[0, "评论内容"], "beforeafter")
            info = pd.read_excel(output / "视频信息.xlsx")
            self.assertEqual(info.loc[0, "视频标题"], "Demo")
            repo.close()

    def test_export_reports_each_created_workbook(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Repository(Path(tmp) / "state.sqlite3")
            repo.initialize()
            repo.upsert_work("video:BV1", "video", "Demo")
            repo.upsert_episode("video:BV1", "cid:10", 1, "P1", "BV1", 1, 10, None)
            progress = RecordingReporter()

            export(repo, "video:BV1", Path(tmp) / "Results", progress=progress)

            self.assertEqual(len(progress.tasks), 1)
            self.assertEqual(progress.tasks[0].description, "导出 Excel")
            self.assertEqual(progress.tasks[0].total, 11)
            self.assertEqual(progress.tasks[0].current, 11)
            repo.close()


class DefaultPathTest(unittest.TestCase):
    def test_cli_defaults_put_database_and_output_under_results(self):
        from bilibili_stats import parser

        args = parser().parse_args(["BV1Q9Vh6CEcC"])
        self.assertEqual(args.output_dir, Path("Results"))
        self.assertIsNone(args.database)

    def test_cli_accepts_no_progress(self):
        from bilibili_stats import parser

        args = parser().parse_args(["BV1Q9Vh6CEcC", "--no-progress"])
        self.assertTrue(args.no_progress)


if __name__ == "__main__":
    unittest.main()
