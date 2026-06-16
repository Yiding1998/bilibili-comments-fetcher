#!/usr/bin/env python3
import argparse
import os
from pathlib import Path

from bili_stats.checkpoint import Repository
from bili_stats.client import AdaptiveLimiter, BilibiliClient
from bili_stats.comments import CommentCollector
from bili_stats.danmaku import DanmakuCollector
from bili_stats.database_paths import discover_work_database, resolve_database_path
from bili_stats.exporter import export
from bili_stats.input import InputKind, parse_input
from bili_stats.migration import migrate_legacy_database
from bili_stats.progress import ProgressReporter
from bili_stats.resolver import Resolver


def parser():
    value = argparse.ArgumentParser(description="B站弹幕与完整评论统计工具")
    value.add_argument("input")
    cookie = value.add_mutually_exclusive_group()
    cookie.add_argument("--cookie")
    cookie.add_argument("--cookie-file", type=Path)
    value.add_argument("--database", type=Path, default=None)
    value.add_argument("--output-dir", type=Path, default=Path("Results"))
    mode = value.add_mutually_exclusive_group()
    mode.add_argument("--restart", action="store_true")
    mode.add_argument("--export-only", action="store_true")
    value.add_argument("--max-attempts", type=int, default=5)
    value.add_argument("--request-delay", type=float, default=0.05)
    value.add_argument("--concurrency", type=int, default=6)
    value.add_argument("--no-progress", action="store_true", help="关闭动态进度条")
    return value


def work_key_for_input(parsed):
    if parsed.kind == InputKind.VIDEO:
        return "video:" + parsed.identifier
    if parsed.kind == InputKind.SEASON:
        return "season:" + parsed.identifier
    if parsed.kind == InputKind.COLLECTION:
        return "collection:{}:{}".format(parsed.owner_mid, parsed.identifier)
    raise ValueError("ep 输入无法离线确定季度，请使用 ss 输入导出")


def main(argv=None):
    args = parser().parse_args(argv)
    parsed = parse_input(args.input)
    progress = ProgressReporter(enabled=not args.no_progress)
    repository = None
    try:
        if args.database is None:
            migrated = migrate_legacy_database(args.output_dir)
            for path in migrated:
                print("已迁移数据库:", path)

        if args.export_only:
            key = work_key_for_input(parsed)
            database_path = args.database or discover_work_database(args.output_dir, key)
            repository = Repository(database_path)
            repository.initialize()
            print("数据库:", database_path)
            print("输出:", export(repository, key, args.output_dir, progress=progress))
            return 0

        cookie = args.cookie or (
            args.cookie_file.read_text(encoding="utf-8").strip()
            if args.cookie_file
            else os.environ.get("BILIBILI_COOKIE")
        )
        limiter = AdaptiveLimiter(args.concurrency, max(args.concurrency, 8), args.request_delay)
        client = BilibiliClient(cookie, args.max_attempts, limiter)
        work = Resolver(client).resolve(parsed)
        database_path = resolve_database_path(args.database, args.output_dir, work.title)
        repository = Repository(database_path)
        repository.initialize()
        print("数据库:", database_path)

        if args.restart:
            repository.restart_work(work.work_key)
        repository.upsert_work(work.work_key, work.kind, work.title, source=work.source)
        for episode in work.episodes:
            repository.upsert_episode(
                work.work_key,
                episode.episode_key,
                episode.position,
                episode.title,
                episode.bvid,
                episode.aid,
                episode.cid,
                episode.ep_id,
            )

        failures = 0
        danmaku = DanmakuCollector(client, repository, progress)
        comments = CommentCollector(client, repository, progress)
        for episode in work.episodes:
            try:
                print("弹幕:", episode.title, flush=True)
                danmaku.collect(episode)
            except Exception as error:
                failures += 1
                repository.record_failure(work.work_key, episode.episode_key, "danmaku", error)
                print("失败:", error)

        for aid in dict.fromkeys(episode.aid for episode in work.episodes):
            try:
                print("评论:", aid, flush=True)
                comments.collect(work.work_key, aid)
            except Exception as error:
                failures += 1
                repository.record_failure(work.work_key, None, "comments", error)
                print("失败:", error)

        print("输出:", export(repository, work.work_key, args.output_dir, progress=progress))
        return 0 if failures == 0 else 2
    except KeyboardInterrupt:
        print("已中断，进度已保存")
        return 130
    finally:
        if repository is not None:
            repository.close()


if __name__ == "__main__":
    raise SystemExit(main())
