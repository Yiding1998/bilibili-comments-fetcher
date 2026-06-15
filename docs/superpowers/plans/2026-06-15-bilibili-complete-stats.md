# Bilibili Complete Statistics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the inaccurate single-file prototype with a resumable, tested collector for normal videos, multi-part videos, collections, and bangumi, producing per-episode and global Excel reports.

**Architecture:** A small `bili_stats` package separates input resolution, HTTP/WBI behavior, protobuf parsing, comment collection, SQLite persistence, export, and CLI orchestration. All network data is committed to SQLite before export, and stable Bilibili identifiers make retries and resume idempotent.

**Tech Stack:** Python 3.9+, `requests`, `protobuf`, `pandas`, `openpyxl`, standard-library `sqlite3` and `unittest`; `grpcio-tools` is used only to regenerate committed protobuf bindings.

---

## File Map

- Modify: `bilibili_stats.py` - compatibility launcher only.
- Modify: `README.md` - installation, supported inputs, resume semantics, and output documentation.
- Create: `.gitignore` - protect cookies, SQLite state, caches, and generated output.
- Create: `requirements.txt` - runtime dependency declarations.
- Create: `requirements-dev.txt` - protobuf generator dependency.
- Create: `bili_stats/__init__.py` - package metadata.
- Create: `bili_stats/models.py` - immutable normalized domain records.
- Create: `bili_stats/input.py` - pure input recognition and normalization.
- Create: `bili_stats/client.py` - HTTP session, WBI signing, validation, retry, and throttling.
- Create: `bili_stats/proto/dm.proto` - minimal documented danmaku message schema.
- Create: `bili_stats/proto/dm_pb2.py` - generated protobuf bindings.
- Create: `bili_stats/danmaku.py` - protobuf decoding and segment collection.
- Create: `bili_stats/checkpoint.py` - SQLite schema and transactional repository.
- Create: `bili_stats/resolver.py` - video, collection, and bangumi task resolution.
- Create: `bili_stats/comments.py` - main and child comment pagination.
- Create: `bili_stats/exporter.py` - episode and global Excel reports.
- Create: `bili_stats/service.py` - collection orchestration across works and episodes.
- Create: `bili_stats/cli.py` - CLI parsing and exit behavior.
- Create: `tests/` - offline unit and integration tests.

## Task 1: Package Skeleton And Safe Local Files

**Files:**
- Create: `.gitignore`
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `bili_stats/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_package.py`

- [ ] **Step 1: Write the failing package test**

```python
# tests/test_package.py
import unittest


class PackageTest(unittest.TestCase):
    def test_package_exposes_version(self):
        import bili_stats

        self.assertRegex(bili_stats.__version__, r"^\d+\.\d+\.\d+$")
```

- [ ] **Step 2: Run the test and verify RED**

Run: `python3 -m unittest tests.test_package -v`

Expected: `ModuleNotFoundError: No module named 'bili_stats'`.

- [ ] **Step 3: Add the minimal package and dependency files**

```python
# bili_stats/__init__.py
__version__ = "2.0.0"
```

```text
# requirements.txt
requests>=2.31,<3
pandas>=2.0,<3
openpyxl>=3.1,<4
protobuf>=5,<7
```

```text
# requirements-dev.txt
-r requirements.txt
grpcio-tools>=1.62,<2
```

```gitignore
# .gitignore
__pycache__/
*.py[cod]
.venv/
cookie.txt
*.sqlite
*.sqlite3
*.db
.pytest_cache/
```

- [ ] **Step 4: Run the test and verify GREEN**

Run: `python3 -m unittest tests.test_package -v`

Expected: one passing test.

- [ ] **Step 5: Commit when Git is available**

Run: `git add .gitignore requirements.txt requirements-dev.txt bili_stats/__init__.py tests && git commit -m "chore: initialize bili stats package"`

If the directory is still not a Git repository, record that and continue without initializing one implicitly.

## Task 2: Normalized Models And Input Recognition

**Files:**
- Create: `bili_stats/models.py`
- Create: `bili_stats/input.py`
- Create: `tests/test_input.py`

- [ ] **Step 1: Write failing recognition tests**

```python
# tests/test_input.py
import unittest

from bili_stats.input import InputKind, parse_input


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
        self.assertEqual(parse_input("https://www.bilibili.com/bangumi/play/ep123").identifier, "123")
        self.assertEqual(parse_input("ss456").kind, InputKind.SEASON)

    def test_recognizes_collection_identifiers_from_url(self):
        parsed = parse_input("https://space.bilibili.com/42/lists/777?type=season")
        self.assertEqual(parsed.kind, InputKind.COLLECTION)
        self.assertEqual(parsed.identifier, "777")
        self.assertEqual(parsed.owner_mid, "42")

    def test_rejects_unrecognized_input(self):
        with self.assertRaisesRegex(ValueError, "无法识别"):
            parse_input("not-a-bilibili-input")
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `python3 -m unittest tests.test_input -v`

Expected: import failure for the missing modules.

- [ ] **Step 3: Implement minimal typed records and parser**

Define in `models.py` frozen dataclasses `ParsedInput`, `Work`, `Episode`, `Danmaku`, and `Comment`. Define `InputKind` in `input.py` with `VIDEO`, `COLLECTION`, `EPISODE`, and `SEASON`. Use `urllib.parse.urlparse` and `parse_qs` for URLs, with anchored regular expressions for stable identifiers. Do not use substring-only matching for untrusted text.

Required parser contract:

```python
def parse_input(value: str) -> ParsedInput:
    """Return a normalized supported Bilibili input or raise ValueError."""
```

- [ ] **Step 4: Run tests and verify GREEN**

Run: `python3 -m unittest tests.test_input -v`

Expected: all input tests pass.

- [ ] **Step 5: Commit when Git is available**

Run: `git add bili_stats/models.py bili_stats/input.py tests/test_input.py && git commit -m "feat: normalize supported bilibili inputs"`

## Task 3: SQLite Schema, Idempotency, And Resume State

**Files:**
- Create: `bili_stats/checkpoint.py`
- Create: `tests/test_checkpoint.py`

- [ ] **Step 1: Write failing repository tests**

```python
# tests/test_checkpoint.py
import tempfile
import unittest
from pathlib import Path

from bili_stats.checkpoint import Repository
from bili_stats.models import Danmaku


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

    def test_replaying_segment_deduplicates_by_danmaku_id(self):
        item = Danmaku("100", "cid:10", "same", 1000, 1, 25, 16777215, "hash", 1)
        self.repo.commit_danmaku_segment("cid:10", 1, [item], complete=False)
        self.repo.commit_danmaku_segment("cid:10", 1, [item], complete=False)
        self.assertEqual(self.repo.count_danmaku("cid:10"), 1)
        self.assertEqual(self.repo.get_danmaku_next_segment("cid:10"), 2)

    def test_restart_deletes_only_target_work(self):
        self.repo.upsert_work("video:BV2", "video", "other")
        self.repo.restart_work("video:BV1")
        self.assertIsNone(self.repo.get_work("video:BV1"))
        self.assertIsNotNone(self.repo.get_work("video:BV2"))
```

- [ ] **Step 2: Run and verify RED**

Run: `python3 -m unittest tests.test_checkpoint -v`

Expected: import failure for `Repository`.

- [ ] **Step 3: Implement schema and transactional methods**

Create tables for `works`, `episodes`, `danmaku`, `comments`, `danmaku_progress`, `comment_progress`, `child_comment_progress`, and `failures`. Enable foreign keys and WAL mode. Use uniqueness constraints on `danmaku.danmaku_id` and `comments.rpid`.

Implement at minimum:

```python
class Repository:
    def initialize(self) -> None: ...
    def upsert_work(self, work_key, kind, title) -> None: ...
    def upsert_episode(self, work_key, episode_key, position, title, bvid, aid, cid, ep_id) -> None: ...
    def commit_danmaku_segment(self, episode_key, segment, items, complete) -> None: ...
    def get_danmaku_next_segment(self, episode_key) -> int: ...
    def commit_comment_page(self, work_key, aid, comments, next_cursor, complete) -> None: ...
    def commit_child_comment_page(self, work_key, root_rpid, comments, next_page, complete) -> None: ...
    def restart_work(self, work_key) -> None: ...
```

Each `commit_*` method inserts rows and advances progress in one transaction.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `python3 -m unittest tests.test_checkpoint -v`

Expected: repository tests pass.

- [ ] **Step 5: Commit when Git is available**

Run: `git add bili_stats/checkpoint.py tests/test_checkpoint.py && git commit -m "feat: add resumable sqlite repository"`

## Task 4: WBI Signing And Reliable HTTP Client

**Files:**
- Create: `bili_stats/client.py`
- Create: `tests/test_client.py`

- [ ] **Step 1: Write failing deterministic signing tests**

```python
# tests/test_client.py
import unittest

from bili_stats.client import encode_wbi


class WbiTest(unittest.TestCase):
    def test_signing_does_not_mutate_input_and_is_deterministic(self):
        original = {"foo": "a!'()*b", "bar": 2}
        signed = encode_wbi(original, "7cd084941338484aae1ad9425b84077c", "4932caff0ff746eab6f01bf08b70ac45", 1700000000)
        self.assertEqual(original, {"foo": "a!'()*b", "bar": 2})
        self.assertEqual(signed["wts"], 1700000000)
        self.assertRegex(signed["w_rid"], r"^[0-9a-f]{32}$")
        self.assertEqual(signed["foo"], "ab")
```

- [ ] **Step 2: Run and verify RED**

Run: `python3 -m unittest tests.test_client -v`

Expected: import failure for `encode_wbi`.

- [ ] **Step 3: Implement signing, response errors, and retry client**

Implement `encode_wbi` as a pure function taking an explicit timestamp. Add `BilibiliClient` around `requests.Session` with injectable `sleep`, `clock`, and random jitter for tests. Expose `get_json` and `get_bytes`; validate HTTP status, JSON `code`, and required data shape. Raise typed sanitized exceptions that never include request headers or Cookie values.

Retry only connection errors, timeouts, HTTP 429/5xx, and HTTP 412. Use bounded exponential backoff, a longer base for 412, and a maximum attempt count. Tests must prove concurrency decreases after throttling, successful requests slowly restore it, and waiting does not occur as a fixed multi-second delay after every successful page.

- [ ] **Step 4: Add and pass retry tests with a fake session**

Add tests proving that a timeout is retried, a successful response stops retries, a permanent API error is not retried, and exception strings do not contain a configured Cookie sentinel.

Run: `python3 -m unittest tests.test_client -v`

Expected: all client tests pass without real HTTP calls.

- [ ] **Step 5: Commit when Git is available**

Run: `git add bili_stats/client.py tests/test_client.py && git commit -m "feat: add signed resilient bilibili client"`

## Task 5: Structural Protobuf Danmaku Parsing

**Files:**
- Create: `bili_stats/proto/__init__.py`
- Create: `bili_stats/proto/dm.proto`
- Create: `bili_stats/proto/dm_pb2.py`
- Create: `bili_stats/danmaku.py`
- Create: `tests/test_danmaku.py`

- [ ] **Step 1: Write failing protobuf behavior tests**

```python
# tests/test_danmaku.py
import unittest

from bili_stats.danmaku import parse_segment
from bili_stats.proto.dm_pb2 import DmSegMobileReply


class DanmakuTest(unittest.TestCase):
    def test_parser_preserves_english_emoji_and_duplicate_text(self):
        reply = DmSegMobileReply()
        for danmaku_id, content in ((1, "hello"), (2, "hello"), (3, "你好😀")):
            elem = reply.elems.add()
            elem.id = danmaku_id
            elem.idStr = str(danmaku_id)
            elem.content = content
            elem.progress = 1200
            elem.mode = 1
            elem.fontsize = 25
            elem.color = 0xFFFFFF
            elem.midHash = "sender"
            elem.ctime = 1700000000

        parsed = parse_segment(reply.SerializeToString(), "cid:10")
        self.assertEqual([item.content for item in parsed], ["hello", "hello", "你好😀"])
        self.assertEqual([item.danmaku_id for item in parsed], ["1", "2", "3"])
```

- [ ] **Step 2: Run and verify RED**

Run: `python3 -m unittest tests.test_danmaku -v`

Expected: missing protobuf bindings or parser.

- [ ] **Step 3: Add the protobuf schema and generated binding**

Define `DanmakuElem` with the known wire fields `id`, `progress`, `mode`, `fontsize`, `color`, `midHash`, `content`, `ctime`, `weight`, `action`, `pool`, `idStr`, and `attr`; define `DmSegMobileReply` with repeated `elems` field number 1. Also define the minimal `DmSegConfig` and `DmWebViewReply` fields needed to read the authoritative segment total from `x/v2/dm/web/view`.

Generate and commit the binding:

Run: `python3 -m grpc_tools.protoc -I. --python_out=. bili_stats/proto/dm.proto`

Expected: `bili_stats/proto/dm_pb2.py` is generated successfully and imports with the installed runtime `protobuf` version.

- [ ] **Step 4: Implement parser and resumable segment collector**

```python
def parse_segment(payload: bytes, episode_key: str) -> list[Danmaku]:
    reply = DmSegMobileReply.FromString(payload)
    return [Danmaku.from_proto(episode_key, elem) for elem in reply.elems]
```

Add `DanmakuCollector.collect(episode)` that starts at `Repository.get_danmaku_next_segment`, downloads the unfinished segment range through a bounded worker pool, and marks completion only when authoritative segment metadata indicates the end. Completed out-of-order segments may be stored, but resume progress advances only through the highest contiguous completed segment so interruption cannot skip gaps. Do not use content length or repeated empty guesses as the primary end condition.

Before requesting segments, fetch `x/v2/dm/web/view?type=1&oid=<cid>`, parse `DmWebViewReply.dmSge.total`, and persist the expected segment count. Request exactly the unfinished range `next_segment..total`. A missing or unparsable segment total is a failure, not a successful empty result.

- [ ] **Step 5: Run and verify GREEN**

Run: `python3 -m unittest tests.test_danmaku -v`

Expected: all danmaku tests pass.

- [ ] **Step 6: Commit when Git is available**

Run: `git add bili_stats/proto bili_stats/danmaku.py tests/test_danmaku.py && git commit -m "feat: parse protobuf danmaku accurately"`

## Task 6: Video, Collection, And Bangumi Resolution

**Files:**
- Create: `bili_stats/resolver.py`
- Create: `tests/test_resolver.py`
- Create: `tests/fixtures/resolver/`

- [ ] **Step 1: Write failing resolver tests using fake client responses**

Create fixtures for:

- A normal video with one page.
- A multi-part video with two `pages` entries and distinct `cid` values.
- A collection with two member videos.
- A bangumi season with two episodes and stable `ep_id`, `aid`, `bvid`, and `cid` values.

Test the public contract:

```python
work = Resolver(fake_client).resolve(parse_input(source))
self.assertEqual([episode.position for episode in work.episodes], [1, 2])
self.assertEqual([episode.cid for episode in work.episodes], [101, 102])
```

Also verify that resolving an `ep` input returns its season work while marking the requested episode as the selected starting context, and that source order is preserved.

- [ ] **Step 2: Run and verify RED**

Run: `python3 -m unittest tests.test_resolver -v`

Expected: missing `Resolver`.

- [ ] **Step 3: Implement endpoint adapters and normalization**

Use separate private methods `_resolve_video`, `_resolve_collection`, and `_resolve_bangumi`. Convert all API-specific dictionaries immediately into `Work` and `Episode` records. Create stable keys such as `video:<bvid>`, `collection:<owner_mid>:<season_id>`, `season:<season_id>`, and `cid:<cid>`.

Do not silently collapse inaccessible members. Preserve a structured resolution failure so the overview report can show missing episodes.

- [ ] **Step 4: Run and verify GREEN**

Run: `python3 -m unittest tests.test_resolver -v`

Expected: all resolver tests pass offline.

- [ ] **Step 5: Commit when Git is available**

Run: `git add bili_stats/resolver.py tests/test_resolver.py tests/fixtures/resolver && git commit -m "feat: resolve videos collections and bangumi"`

## Task 7: Complete Main And Child Comment Pagination

**Files:**
- Create: `bili_stats/comments.py`
- Create: `tests/test_comments.py`

- [ ] **Step 1: Write failing pagination tests**

Use a fake client returning two top-level pages. The first page contains a root comment whose `rcount` exceeds the embedded child list; child endpoint pages return two further replies.

Assert that:

```python
collector.collect(work_key="video:BV1", aid=1)
self.assertEqual(repo.count_comments("video:BV1"), 4)
self.assertTrue(repo.get_comment_progress("video:BV1").complete)
self.assertTrue(repo.get_child_progress(root_rpid=100).complete)
```

Add an interruption test: fail on child page 2, reconstruct the collector, rerun, and assert it resumes at page 2 without duplicating rows or fetching main page 1 again.

- [ ] **Step 2: Run and verify RED**

Run: `python3 -m unittest tests.test_comments -v`

Expected: missing `CommentCollector`.

- [ ] **Step 3: Implement main pagination**

Use the signed main reply endpoint and persisted opaque cursor. Normalize every root and embedded child into `Comment` records with `rpid`, `root_rpid`, and `parent_rpid`. Commit the page and next cursor atomically. Treat `cursor.is_end` as completion; do not infer completion solely from an empty list.

- [ ] **Step 4: Implement full child pagination**

For every root with more replies than embedded, call the child reply endpoint page by page. Persist each root.s next page independently. Deduplicate embedded and separately fetched replies by `rpid`. Run different roots through a bounded worker pool governed by the shared adaptive limiter; keep pages for one root sequential.

- [ ] **Step 5: Run and verify GREEN**

Run: `python3 -m unittest tests.test_comments -v`

Expected: main pagination, child pagination, deduplication, and resume tests pass.

- [ ] **Step 6: Commit when Git is available**

Run: `git add bili_stats/comments.py tests/test_comments.py && git commit -m "feat: collect all accessible comment replies"`

## Task 8: Episode And Global Excel Export

**Files:**
- Create: `bili_stats/exporter.py`
- Create: `tests/test_exporter.py`

- [ ] **Step 1: Write failing exporter test**

Seed a temporary repository with two episodes, repeated danmaku text under distinct IDs, comments from the same user, and mixed completion states. Export to a temporary directory and assert these files exist:

```python
expected = {
    "全局弹幕统计.xlsx",
    "全局评论统计.xlsx",
    "分集概览.xlsx",
    "01-P1/弹幕明细.xlsx",
    "01-P1/弹幕统计.xlsx",
    "01-P1/完整评论.xlsx",
    "01-P1/评论用户统计.xlsx",
}
```

Read the generated workbooks with `pandas.read_excel` and assert duplicate text has count 2, the same user's comments aggregate correctly, and the overview labels an interrupted source `部分完成`.

- [ ] **Step 2: Run and verify RED**

Run: `python3 -m unittest tests.test_exporter -v`

Expected: missing `Exporter`.

- [ ] **Step 3: Implement database-driven export**

Query detail rows from `Repository`, construct deterministic DataFrames, clean only Excel-invalid control characters, and sanitize file names. Include source identifiers and status columns. For video comments stored once by `aid`, export them under the owning video/work and avoid cloning the same rows into every part; episode overview links the shared comment status.

- [ ] **Step 4: Run and verify GREEN**

Run: `python3 -m unittest tests.test_exporter -v`

Expected: workbook contents and status labels pass.

- [ ] **Step 5: Commit when Git is available**

Run: `git add bili_stats/exporter.py tests/test_exporter.py && git commit -m "feat: export episode and global excel reports"`

## Task 9: Orchestration, Failure Isolation, And Resume

**Files:**
- Create: `bili_stats/service.py`
- Create: `tests/test_service.py`

- [ ] **Step 1: Write failing orchestration test**

Construct a two-episode work with fake collectors. Make danmaku collection fail for episode 1 and succeed for episode 2; make work-scoped comment collection succeed. Assert that episode 2 still runs, episode 1 records a sanitized failure, exports run once, and the result reports partial completion.

- [ ] **Step 2: Run and verify RED**

Run: `python3 -m unittest tests.test_service -v`

Expected: missing `CollectionService`.

- [ ] **Step 3: Implement service orchestration**

`CollectionService.run(parsed_input, restart=False, export_only=False)` must:

1. Resolve or load the work.
2. Apply work-scoped restart when requested.
3. Upsert normalized metadata.
4. Skip completed danmaku tasks and continue unfinished ones.
5. Collect comments once per distinct `aid`.
6. Record failures and continue independent episodes.
7. Export current database state even after partial failures.
8. Return a result with `complete`, `partial`, and `failed` counts.

On `KeyboardInterrupt`, stop scheduling new work, leave committed state intact, export if possible, then re-raise or return an interrupted result for the CLI to map to exit code 130.

- [ ] **Step 4: Run and verify GREEN**

Run: `python3 -m unittest tests.test_service -v`

Expected: failure isolation and resume behavior pass.

- [ ] **Step 5: Commit when Git is available**

Run: `git add bili_stats/service.py tests/test_service.py && git commit -m "feat: orchestrate resumable collection"`

## Task 10: CLI And Compatibility Launcher

**Files:**
- Create: `bili_stats/cli.py`
- Modify: `bilibili_stats.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Patch `CollectionService` and verify:

- Bare BV and all URL forms are accepted.
- Cookie precedence is `--cookie` over `--cookie-file` over `BILIBILI_COOKIE`.
- Cookie content never appears in output or exception text.
- `--restart` and `--export-only` cannot be used together.
- Complete returns 0, partial returns 2, invalid input returns 64, and interruption returns 130.

- [ ] **Step 2: Run and verify RED**

Run: `python3 -m unittest tests.test_cli -v`

Expected: missing CLI module.

- [ ] **Step 3: Implement argparse CLI**

Expose:

```text
python3 bilibili_stats.py INPUT
  [--cookie COOKIE | --cookie-file FILE]
  [--database PATH]
  [--output-dir PATH]
  [--restart | --export-only]
  [--max-attempts N]
  [--request-delay SECONDS]
  [--concurrency N]
```

Read Cookie files with UTF-8, reject empty Cookie values, and never print them. Use `pathlib.Path`. Instantiate dependencies in one composition function so tests can replace the service cleanly.

Replace the old 600-line launcher with:

```python
#!/usr/bin/env python3
from bili_stats.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run and verify GREEN**

Run: `python3 -m unittest tests.test_cli -v`

Expected: all CLI tests pass.

- [ ] **Step 5: Commit when Git is available**

Run: `git add bilibili_stats.py bili_stats/cli.py tests/test_cli.py && git commit -m "feat: add secure resumable command line interface"`

## Task 11: Documentation And Migration Guidance

**Files:**
- Modify: `README.md`
- Create: `tests/test_docs.py`

- [ ] **Step 1: Write failing documentation assertions**

```python
# tests/test_docs.py
import unittest
from pathlib import Path


class DocumentationTest(unittest.TestCase):
    def test_readme_documents_required_operations(self):
        text = Path("README.md").read_text(encoding="utf-8")
        for term in ("多P", "合集", "番剧", "--restart", "--export-only", "BILIBILI_COOKIE", "SQLite"):
            self.assertIn(term, text)
```

- [ ] **Step 2: Run and verify RED**

Run: `python3 -m unittest tests.test_docs -v`

Expected: missing new operational terms.

- [ ] **Step 3: Rewrite README around the new behavior**

Document Python version, dependency installation, every supported input form, secure Cookie methods, resume/restart/export-only semantics, SQLite location, per-episode and global output, exit codes, platform access limitations, and migration from the old command. Remove inaccurate claims such as regex protobuf extraction being complete and the mismatched default comment limit.

- [ ] **Step 4: Run and verify GREEN**

Run: `python3 -m unittest tests.test_docs -v`

Expected: documentation assertions pass.

- [ ] **Step 5: Commit when Git is available**

Run: `git add README.md tests/test_docs.py && git commit -m "docs: document complete resumable collector"`

## Task 12: Full Verification And Live Smoke Test

**Files:**
- Modify only files required by failures found during verification.

- [ ] **Step 1: Run the complete offline suite**

Run: `python3 -m unittest discover -s tests -v`

Expected: all tests pass with no network access.

- [ ] **Step 2: Run syntax compilation**

Run: `python3 -m compileall -q bili_stats bilibili_stats.py tests`

Expected: exit code 0 and no output.

- [ ] **Step 3: Run CLI help and credential leak checks**

Run: `python3 bilibili_stats.py --help`

Expected: supported input types and operational flags are shown; no Cookie value is displayed.

Run: `rg -n "SESSDATA=|bili_jct=" --glob '*.py' --glob '*.md' --glob '!docs/superpowers/**' .`

Expected: no real credential values in source or documentation. Placeholder examples are acceptable only when clearly synthetic.

- [ ] **Step 4: Run an optional authenticated live smoke test**

Use the existing Cookie file without displaying it:

Run: `python3 bilibili_stats.py BV1nAJK6PEwh --cookie-file cookie.txt --database /tmp/bili-smoke.sqlite3 --output-dir /tmp/bili-smoke`

Expected: metadata resolves, at least one structurally parsed danmaku segment is committed, comment pagination starts, and interruption followed by the same command resumes from committed progress. If network access is unavailable, report the smoke test as not run rather than weakening offline tests.

- [ ] **Step 5: Inspect generated workbooks**

Open with `pandas.read_excel` in a short command and verify expected columns, nonzero detail counts where the API returned data, aggregate counts equal detail-row groupings, and overview completeness matches stored progress.

- [ ] **Step 6: Final commit when Git is available**

Run: `git add . && git commit -m "feat: complete resumable bilibili statistics collector"`

Do not add `cookie.txt`, SQLite files, generated spreadsheets, or unrelated existing output.
