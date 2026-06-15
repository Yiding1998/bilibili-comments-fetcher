import io
import unittest

from bili_stats.progress import ProgressReporter


class FakeTTY(io.StringIO):
    def isatty(self):
        return True


class FakeLog(io.StringIO):
    def isatty(self):
        return False


class ProgressReporterTest(unittest.TestCase):
    def test_tty_task_tracks_known_total_and_initial_value(self):
        reporter = ProgressReporter(stream=FakeTTY())
        task = reporter.task("弹幕", total=10, initial=3, unit="段")
        task.update(2)
        self.assertEqual(task.current, 5)
        self.assertEqual(task.total, 10)
        task.close()
        self.assertTrue(task.closed)

    def test_unknown_total_supports_postfix(self):
        reporter = ProgressReporter(stream=FakeTTY())
        task = reporter.task("主评论", unit="页")
        task.update(1, records=20)
        self.assertEqual(task.current, 1)
        self.assertEqual(task.postfix["records"], 20)
        task.close()

    def test_non_tty_logs_start_and_completion(self):
        stream = FakeLog()
        reporter = ProgressReporter(stream=stream)
        with reporter.task("导出 Excel", total=3, unit="文件") as task:
            task.update(3)
        output = stream.getvalue()
        self.assertIn("开始: 导出 Excel", output)
        self.assertIn("完成: 导出 Excel", output)
        self.assertIn("3/3", output)

    def test_silent_reporter_writes_nothing(self):
        stream = FakeLog()
        reporter = ProgressReporter(stream=stream, enabled=False, silent=True)
        with reporter.task("阶段", total=1) as task:
            task.update()
        self.assertEqual(stream.getvalue(), "")

    def test_disabled_reporter_does_not_create_dynamic_bar(self):
        stream = FakeTTY()
        reporter = ProgressReporter(stream=stream, enabled=False)
        with reporter.task("阶段", total=1) as task:
            task.update()
        self.assertFalse(task.dynamic)


if __name__ == "__main__":
    unittest.main()
