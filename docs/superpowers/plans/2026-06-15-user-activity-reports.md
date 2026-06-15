# User Activity Reports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add danmaku/comment user rankings with newline-joined content and make `Results/` the default location for both SQLite and Excel output.

**Architecture:** Move export aggregation into a focused `bili_stats/exporter.py` module with pure helper functions. The CLI imports it and changes only default paths; existing collection and persistence formats remain compatible.

**Tech Stack:** Python 3.8+, pandas, openpyxl, unittest.

---

### Task 1: Activity Aggregation Helpers

**Files:**
- Create: `bili_stats/exporter.py`
- Create: `tests/test_exporter.py`

- [ ] Write failing tests that call `build_danmaku_user_rows` and `build_comment_user_rows`, asserting descending counts, identity tie sorting, duplicate content retention, MID grouping, latest username, unknown labels, newline joining, and length at most 32,767.
- [ ] Run `python3 -m unittest tests.test_exporter -v`; expect import failure.
- [ ] Implement `excel_text`, `build_danmaku_user_rows`, and `build_comment_user_rows`. Preserve input content order and append `\n...[内容已截断]` when truncation is required.
- [ ] Re-run `python3 -m unittest tests.test_exporter -v`; expect all tests to pass.

### Task 2: Export Integration And Defaults

**Files:**
- Modify: `bilibili_stats.py`
- Extend: `tests/test_exporter.py`

- [ ] Add a failing integration test that seeds a temporary repository, invokes `export`, and expects per-episode `弹幕用户排行.xlsx`, work-level `全局弹幕用户排行.xlsx`, and `评论用户排行.xlsx`.
- [ ] Add a failing parser test asserting default database `Results/bilibili_stats.sqlite3` and output directory `Results`.
- [ ] Move the current export implementation into `bili_stats/exporter.py`, generate the three new files, import `export` from the launcher, and update parser defaults.
- [ ] Run `python3 -m unittest tests.test_exporter -v`; expect all tests to pass.

### Task 3: Documentation And Verification

**Files:**
- Modify: `README.md`

- [ ] Document `Results/` defaults, new ranking files, identity rules, columns, newline content, and the fixed live-test BV.
- [ ] Run `python3 -m unittest discover -s tests -v` and `python3 -m compileall -q bili_stats bilibili_stats.py tests`.
- [ ] Run `python3 bilibili_stats.py BV1Q9Vh6CEcC --cookie-file cookie.txt` and verify database/reports are under `Results/`; interrupt and resume if a full run is too long.
- [ ] Inspect the new workbooks with pandas and verify count order and content columns.
