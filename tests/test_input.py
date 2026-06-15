import unittest
from dataclasses import FrozenInstanceError

from bili_stats.input import InputKind, parse_input
from bili_stats.models import Comment, Danmaku, Episode, Work


class InputTest(unittest.TestCase):
    def test_recognizes_bare_bvid(self):
        parsed = parse_input("BV1nAJK6PEwh")
        self.assertEqual(parsed.kind, InputKind.VIDEO)
        self.assertEqual(parsed.identifier, "BV1nAJK6PEwh")

    def test_recognizes_video_url_and_page(self):
        parsed = parse_input("https://www.bilibili.com/video/BV1nAJK6PEwh?p=3")
        self.assertEqual(parsed.kind, InputKind.VIDEO)
        self.assertEqual(parsed.identifier, "BV1nAJK6PEwh")
        self.assertEqual(parsed.page, 3)

    def test_recognizes_bangumi_episode_and_season(self):
        episode = parse_input("https://www.bilibili.com/bangumi/play/ep123")
        season = parse_input("ss456")
        self.assertEqual(episode.kind, InputKind.EPISODE)
        self.assertEqual(episode.identifier, "123")
        self.assertEqual(season.kind, InputKind.SEASON)
        self.assertEqual(season.identifier, "456")

    def test_recognizes_collection_identifiers_from_url(self):
        parsed = parse_input("https://space.bilibili.com/42/lists/777?type=season")
        self.assertEqual(parsed.kind, InputKind.COLLECTION)
        self.assertEqual(parsed.identifier, "777")
        self.assertEqual(parsed.owner_mid, "42")

    def test_rejects_unrecognized_input(self):
        with self.assertRaisesRegex(ValueError, "无法识别"):
            parse_input("not-a-bilibili-input")

    def test_normalizes_surrounding_whitespace(self):
        parsed = parse_input("  ep123\n")
        self.assertEqual(parsed.kind, InputKind.EPISODE)
        self.assertEqual(parsed.identifier, "123")
        self.assertEqual(parsed.original, "ep123")

    def test_rejects_invalid_video_page(self):
        for page in ("0", "-1", "abc", "1.5", ""):
            with self.subTest(page=page):
                with self.assertRaisesRegex(ValueError, "无法识别"):
                    parse_input(
                        "https://www.bilibili.com/video/BV1nAJK6PEwh?p=" + page
                    )

    def test_rejects_misleading_bvid_substring(self):
        with self.assertRaisesRegex(ValueError, "无法识别"):
            parse_input("prefix-BV1nAJK6PEwh-suffix")

    def test_rejects_unsupported_domain(self):
        with self.assertRaisesRegex(ValueError, "无法识别"):
            parse_input("https://example.com/video/BV1nAJK6PEwh?p=3")


class ModelTest(unittest.TestCase):
    def test_work_normalizes_episodes_to_tuple_and_is_frozen(self):
        episode = Episode("cid:10", 1, "P1", "BV1", 1, 10)
        work = Work("video:BV1", InputKind.VIDEO, "Demo", [episode])
        self.assertEqual(work.episodes, (episode,))
        with self.assertRaises(FrozenInstanceError):
            work.title = "Changed"

    def test_danmaku_supports_planned_constructor(self):
        item = Danmaku("100", "cid:10", "same", 1000, 1, 25, 16777215, "hash", 1)
        self.assertEqual(item.danmaku_id, "100")
        self.assertEqual(item.episode_key, "cid:10")
        self.assertEqual(item.pool, 1)

    def test_comment_defaults_relationships_and_metrics(self):
        item = Comment("200", "video:BV1", 1, "42", "User", "Text")
        self.assertIsNone(item.root_rpid)
        self.assertIsNone(item.parent_rpid)
        self.assertEqual(item.ctime, 0)
        self.assertEqual(item.likes, 0)


if __name__ == "__main__":
    unittest.main()
