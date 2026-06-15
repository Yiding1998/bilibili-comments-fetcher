import sqlite3
from pathlib import Path

from .exporter import safe_name


class DatabaseNotFound(RuntimeError):
    pass


class MultipleDatabasesFound(RuntimeError):
    pass


def work_database_path(output_root, title):
    return Path(output_root) / safe_name(title) / "bilibili_stats.sqlite3"


def resolve_database_path(explicit_path, output_root, title):
    if explicit_path is not None:
        return Path(explicit_path)
    return work_database_path(output_root, title)


def _contains_work(path, work_key):
    try:
        connection = sqlite3.connect("file:{}?mode=ro".format(path.resolve()), uri=True)
        try:
            return connection.execute(
                "SELECT 1 FROM works WHERE work_key=?", (work_key,)
            ).fetchone() is not None
        finally:
            connection.close()
    except sqlite3.Error:
        return False


def discover_work_database(output_root, work_key):
    matches = [
        path
        for path in sorted(Path(output_root).glob("*/bilibili_stats.sqlite3"))
        if _contains_work(path, work_key)
    ]
    if not matches:
        raise DatabaseNotFound("未找到作品 {} 的数据库".format(work_key))
    if len(matches) > 1:
        raise MultipleDatabasesFound(
            "作品 {} 匹配多个数据库: {}".format(
                work_key, ", ".join(str(path) for path in matches)
            )
        )
    return matches[0]
