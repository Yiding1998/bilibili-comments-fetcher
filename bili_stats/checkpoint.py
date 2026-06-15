import json
import sqlite3
import threading
from pathlib import Path


class Repository:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(self.path), check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._lock = threading.RLock()

    def initialize(self):
        self.connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            PRAGMA journal_mode = WAL;
            CREATE TABLE IF NOT EXISTS works (
              work_key TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL,
              source_json TEXT NOT NULL DEFAULT '{}', status TEXT NOT NULL DEFAULT 'pending'
            );
            CREATE TABLE IF NOT EXISTS episodes (
              episode_key TEXT PRIMARY KEY, work_key TEXT NOT NULL REFERENCES works(work_key) ON DELETE CASCADE,
              position INTEGER NOT NULL, title TEXT NOT NULL, bvid TEXT, aid INTEGER, cid INTEGER,
              ep_id INTEGER, danmaku_status TEXT NOT NULL DEFAULT 'pending'
            );
            CREATE TABLE IF NOT EXISTS danmaku (
              danmaku_id TEXT PRIMARY KEY, episode_key TEXT NOT NULL REFERENCES episodes(episode_key) ON DELETE CASCADE,
              content TEXT NOT NULL, ctime INTEGER, progress INTEGER, mode INTEGER, fontsize INTEGER,
              color INTEGER, sender_hash TEXT, pool INTEGER, weight INTEGER, action TEXT, attr INTEGER
            );
            CREATE TABLE IF NOT EXISTS danmaku_segments (
              episode_key TEXT NOT NULL REFERENCES episodes(episode_key) ON DELETE CASCADE,
              segment INTEGER NOT NULL, complete INTEGER NOT NULL DEFAULT 0,
              PRIMARY KEY (episode_key, segment)
            );
            CREATE TABLE IF NOT EXISTS danmaku_progress (
              episode_key TEXT PRIMARY KEY REFERENCES episodes(episode_key) ON DELETE CASCADE,
              next_segment INTEGER NOT NULL DEFAULT 1, total_segments INTEGER, complete INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS comments (
              rpid TEXT PRIMARY KEY, work_key TEXT NOT NULL REFERENCES works(work_key) ON DELETE CASCADE,
              aid INTEGER NOT NULL, user_mid TEXT, user_name TEXT, content TEXT,
              root_rpid TEXT, parent_rpid TEXT, ctime INTEGER, likes INTEGER
            );
            CREATE TABLE IF NOT EXISTS comment_progress (
              work_key TEXT NOT NULL REFERENCES works(work_key) ON DELETE CASCADE, aid INTEGER NOT NULL,
              next_cursor TEXT NOT NULL DEFAULT '', complete INTEGER NOT NULL DEFAULT 0,
              PRIMARY KEY (work_key, aid)
            );
            CREATE TABLE IF NOT EXISTS child_comment_progress (
              work_key TEXT NOT NULL REFERENCES works(work_key) ON DELETE CASCADE, root_rpid TEXT NOT NULL,
              next_page INTEGER NOT NULL DEFAULT 1, complete INTEGER NOT NULL DEFAULT 0,
              PRIMARY KEY (work_key, root_rpid)
            );
            CREATE TABLE IF NOT EXISTS failures (
              id INTEGER PRIMARY KEY AUTOINCREMENT, work_key TEXT, episode_key TEXT,
              operation TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        self.connection.commit()

    def close(self):
        self.connection.close()

    def upsert_work(self, work_key, kind, title, source=None):
        with self.connection:
            values = (getattr(kind, "value", kind), title, json.dumps(source or {}, ensure_ascii=False), work_key)
            cursor = self.connection.execute("UPDATE works SET kind=?,title=?,source_json=? WHERE work_key=?", values)
            if cursor.rowcount == 0:
                self.connection.execute("INSERT INTO works(work_key,kind,title,source_json) VALUES(?,?,?,?)", (work_key, values[0], values[1], values[2]))

    def get_work(self, work_key):
        row = self.connection.execute("SELECT * FROM works WHERE work_key=?", (work_key,)).fetchone()
        return dict(row) if row else None

    def upsert_episode(self, work_key, episode_key, position, title, bvid, aid, cid, ep_id):
        with self.connection:
            values = (work_key, position, title, bvid, aid, cid, ep_id, episode_key)
            cursor = self.connection.execute("UPDATE episodes SET work_key=?,position=?,title=?,bvid=?,aid=?,cid=?,ep_id=? WHERE episode_key=?", values)
            if cursor.rowcount == 0:
                self.connection.execute("INSERT INTO episodes(episode_key,work_key,position,title,bvid,aid,cid,ep_id) VALUES(?,?,?,?,?,?,?,?)", (episode_key, work_key, position, title, bvid, aid, cid, ep_id))
            self.connection.execute("INSERT OR IGNORE INTO danmaku_progress(episode_key) VALUES(?)", (episode_key,))

    def set_danmaku_total(self, episode_key, total):
        with self.connection:
            self.connection.execute(
                "UPDATE danmaku_progress SET total_segments=? WHERE episode_key=?", (total, episode_key)
            )

    def commit_danmaku_segment(self, episode_key, segment, items, complete=False):
        with self._lock, self.connection:
            for item in items:
                self.connection.execute(
                    "INSERT OR IGNORE INTO danmaku VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (item.danmaku_id, item.episode_key, item.content, item.ctime, item.progress,
                     item.mode, item.fontsize, item.color, item.sender_hash, item.pool,
                     item.weight, item.action, item.attr),
                )
            self.connection.execute("INSERT OR REPLACE INTO danmaku_segments(episode_key,segment,complete) VALUES(?,?,1)", (episode_key, segment))
            next_segment = 1
            for row in self.connection.execute(
                "SELECT segment FROM danmaku_segments WHERE episode_key=? AND complete=1 ORDER BY segment", (episode_key,)
            ):
                if row[0] != next_segment:
                    break
                next_segment += 1
            total_row = self.connection.execute("SELECT total_segments FROM danmaku_progress WHERE episode_key=?", (episode_key,)).fetchone()
            is_complete = bool(total_row and total_row[0] and next_segment > total_row[0])
            self.connection.execute(
                "UPDATE danmaku_progress SET next_segment=?,complete=? WHERE episode_key=?",
                (next_segment, int(is_complete), episode_key),
            )

    def get_danmaku_next_segment(self, episode_key):
        row = self.connection.execute(
            "SELECT next_segment FROM danmaku_progress WHERE episode_key=?", (episode_key,)
        ).fetchone()
        return row[0] if row else 1

    def count_danmaku(self, episode_key):
        return self.connection.execute("SELECT count(*) FROM danmaku WHERE episode_key=?", (episode_key,)).fetchone()[0]

    def commit_comment_page(self, work_key, aid, comments, next_cursor, complete):
        with self._lock, self.connection:
            self._insert_comments(comments)
            self.connection.execute("INSERT OR REPLACE INTO comment_progress(work_key,aid,next_cursor,complete) VALUES(?,?,?,?)", (work_key, aid, next_cursor or "", int(complete)))

    def commit_child_comment_page(self, work_key, root_rpid, comments, next_page, complete):
        with self._lock, self.connection:
            self._insert_comments(comments)
            self.connection.execute("INSERT OR REPLACE INTO child_comment_progress(work_key,root_rpid,next_page,complete) VALUES(?,?,?,?)", (work_key, str(root_rpid), next_page, int(complete)))

    def _insert_comments(self, comments):
        for item in comments:
            self.connection.execute(
                "INSERT OR IGNORE INTO comments VALUES(?,?,?,?,?,?,?,?,?,?)",
                (item.rpid, item.work_key, item.aid, item.user_mid, item.user_name, item.content,
                 item.root_rpid, item.parent_rpid, item.ctime, item.likes),
            )

    def get_comment_progress(self, work_key, aid):
        row = self.connection.execute(
            "SELECT next_cursor,complete FROM comment_progress WHERE work_key=? AND aid=?", (work_key, aid)
        ).fetchone()
        return dict(row) if row else {"next_cursor": "", "complete": False}

    def get_child_progress(self, work_key, root_rpid):
        row = self.connection.execute(
            "SELECT next_page,complete FROM child_comment_progress WHERE work_key=? AND root_rpid=?",
            (work_key, str(root_rpid)),
        ).fetchone()
        return dict(row) if row else {"next_page": 1, "complete": False}

    def count_comments(self, work_key):
        return self.connection.execute("SELECT count(*) FROM comments WHERE work_key=?", (work_key,)).fetchone()[0]

    def restart_work(self, work_key):
        with self.connection:
            self.connection.execute("DELETE FROM works WHERE work_key=?", (work_key,))

    def record_failure(self, work_key, episode_key, operation, message):
        with self.connection:
            self.connection.execute(
                "INSERT INTO failures(work_key,episode_key,operation,message) VALUES(?,?,?,?)",
                (work_key, episode_key, operation, str(message)),
            )

    def list_episodes(self, work_key):
        return [dict(row) for row in self.connection.execute(
            "SELECT * FROM episodes WHERE work_key=? ORDER BY position", (work_key,)
        )]

    def list_danmaku(self, work_key, episode_key=None):
        sql = "SELECT d.*,e.title AS episode_title,e.position FROM danmaku d JOIN episodes e ON e.episode_key=d.episode_key WHERE e.work_key=?"
        params = [work_key]
        if episode_key:
            sql += " AND d.episode_key=?"
            params.append(episode_key)
        return [dict(row) for row in self.connection.execute(sql, params)]

    def list_pending_child_roots(self, work_key, aid):
        return [row[0] for row in self.connection.execute(
            "SELECT p.root_rpid FROM child_comment_progress p JOIN comments c ON c.rpid=p.root_rpid WHERE p.work_key=? AND p.complete=0 AND c.aid=?",
            (work_key, aid),
        )]

    def list_comments(self, work_key):
        return [dict(row) for row in self.connection.execute(
            "SELECT * FROM comments WHERE work_key=? ORDER BY ctime,rpid", (work_key,)
        )]

