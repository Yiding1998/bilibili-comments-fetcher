import sqlite3
from pathlib import Path

from .checkpoint import Repository
from .database_paths import work_database_path


TABLE_QUERIES = {
    "works": ("SELECT * FROM works WHERE work_key=?", lambda work_key: (work_key,)),
    "episodes": ("SELECT * FROM episodes WHERE work_key=?", lambda work_key: (work_key,)),
    "danmaku": (
        "SELECT d.* FROM danmaku d JOIN episodes e ON e.episode_key=d.episode_key WHERE e.work_key=?",
        lambda work_key: (work_key,),
    ),
    "danmaku_segments": (
        "SELECT s.* FROM danmaku_segments s JOIN episodes e ON e.episode_key=s.episode_key WHERE e.work_key=?",
        lambda work_key: (work_key,),
    ),
    "danmaku_progress": (
        "SELECT p.* FROM danmaku_progress p JOIN episodes e ON e.episode_key=p.episode_key WHERE e.work_key=?",
        lambda work_key: (work_key,),
    ),
    "comments": ("SELECT * FROM comments WHERE work_key=?", lambda work_key: (work_key,)),
    "comment_progress": ("SELECT * FROM comment_progress WHERE work_key=?", lambda work_key: (work_key,)),
    "child_comment_progress": (
        "SELECT * FROM child_comment_progress WHERE work_key=?", lambda work_key: (work_key,)
    ),
    "failures": ("SELECT * FROM failures WHERE work_key=?", lambda work_key: (work_key,)),
}


def _rows(connection, table, work_key):
    query, params = TABLE_QUERIES[table]
    return connection.execute(query, params(work_key)).fetchall()


def _columns(connection, table):
    return [row[1] for row in connection.execute("PRAGMA table_info({})".format(table))]


def _copy_work(source, target, work_key):
    with target:
        for table in TABLE_QUERIES:
            rows = _rows(source, table, work_key)
            if not rows:
                continue
            columns = _columns(source, table)
            placeholders = ",".join("?" for _ in columns)
            target.executemany(
                "INSERT OR REPLACE INTO {} ({}) VALUES ({})".format(
                    table, ",".join(columns), placeholders
                ),
                [tuple(row[column] for column in columns) for row in rows],
            )


def _default_verify(source, target, work_key):
    return all(
        len(_rows(source, table, work_key)) == len(_rows(target, table, work_key))
        for table in TABLE_QUERIES
    )


def migrate_legacy_database(output_root, verify=None):
    root = Path(output_root)
    legacy = root / "bilibili_stats.sqlite3"
    if not legacy.exists():
        return []
    verify = verify or _default_verify
    source = sqlite3.connect(str(legacy))
    source.row_factory = sqlite3.Row
    targets = []
    try:
        works = source.execute("SELECT work_key,title FROM works ORDER BY work_key").fetchall()
        for work in works:
            target_path = work_database_path(root, work["title"])
            repository = Repository(target_path)
            repository.initialize()
            target = repository.connection
            try:
                _copy_work(source, target, work["work_key"])
                if not verify(source, target, work["work_key"]):
                    raise RuntimeError("迁移验证失败: {}".format(work["work_key"]))
            finally:
                repository.close()
            targets.append(target_path)
    finally:
        source.close()
    for suffix in ("", "-wal", "-shm"):
        path = Path(str(legacy) + suffix)
        if path.exists():
            path.unlink()
    return targets
